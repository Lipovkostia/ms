"""Account/user-scoped records, with SQLite or external PostgreSQL."""
from pathlib import Path
import os
import json
import pandas as pd
import sqlite3
from contextlib import contextmanager

class StoreError(RuntimeError):
    """Sanitized persistence failure; connection secrets never enter UI errors."""
    pass

class Store:
    def __init__(self,path,scope='legacy',database_url=None):
        self.scope=scope
        self.path=str(path)
        self.driver=None
        self.url=None
        url=database_url or os.environ.get('DATABASE_URL')
        self.persistent=bool(url)
        if url:
            url=url.replace('postgresql+psycopg://','postgresql://',1).replace('postgres://','postgresql://',1)
            if not url.startswith('postgresql://'): raise ValueError('DATABASE_URL должен указывать PostgreSQL.')
            try:
                import psycopg
            except ImportError:
                raise StoreError('Драйвер PostgreSQL не установлен. В Streamlit Cloud выполните Manage app → Reboot app, чтобы установить requirements.txt.') from None
            self.driver=psycopg
            self.url=url
        else:
            Path(path).parent.mkdir(parents=True,exist_ok=True)
        pk='BIGSERIAL PRIMARY KEY' if self.persistent else 'INTEGER PRIMARY KEY'
        with self.connect() as db:
            for sql in [f'''CREATE TABLE IF NOT EXISTS tasks (id {pk},client_id BIGINT NOT NULL,title TEXT NOT NULL,due TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Запланирована',note TEXT NOT NULL DEFAULT '',recommendation_id TEXT,scope TEXT NOT NULL DEFAULT 'legacy')''',
                '''CREATE TABLE IF NOT EXISTS processed (recommendation_id TEXT NOT NULL,processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,scope TEXT NOT NULL DEFAULT 'legacy',PRIMARY KEY(scope,recommendation_id))''',
                '''CREATE TABLE IF NOT EXISTS records (scope TEXT NOT NULL,kind TEXT NOT NULL,record_key TEXT NOT NULL,value TEXT NOT NULL,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(scope,kind,record_key))''']:
                self.execute(db,sql)
            # Preserve old databases without assigning anonymous records to employees.
            for table in ['tasks','processed']:
                if self.persistent:
                    columns=self.execute(db,"SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?",(table,)).fetchall()
                    names={c[0] for c in columns}
                else:
                    names={c[1] for c in self.execute(db,f'PRAGMA table_info({table})').fetchall()}
                if 'scope' not in names:
                    self.execute(db,f"ALTER TABLE {table} ADD COLUMN scope TEXT NOT NULL DEFAULT 'legacy'")

    @contextmanager
    def connect(self):
        db=None
        errors=(sqlite3.Error, self.driver.Error) if self.driver else (sqlite3.Error,)
        try:
            db=self.driver.connect(self.url,connect_timeout=10) if self.persistent else sqlite3.connect(self.path,timeout=10)
            yield db
            db.commit()
        except errors:
            if db is not None: db.rollback()
            raise StoreError('Не удалось выполнить операцию с базой. Проверьте доступ и настройки подключения.') from None
        finally:
            if db is not None: db.close()

    def execute(self,db,sql,args=()):
        return db.execute(sql.replace('?', '%s') if self.persistent else sql,tuple(args))

    @staticmethod
    def columns(cursor):
        return [column[0] for column in cursor.description]

    def tasks(self):
        with self.connect() as db:
            r=self.execute(db,'SELECT * FROM tasks WHERE scope=? ORDER BY due,id',(self.scope,))
            return pd.DataFrame(r.fetchall(),columns=self.columns(r))
    def add(self,client_id,title,due,note='',recommendation_id=None,status='Запланирована'):
        if not title.strip(): raise ValueError('Укажите название задачи.')
        if status not in ['Запланирована','В работе']: raise ValueError('Неизвестный статус новой задачи.')
        with self.connect() as db:
            self.execute(db,'INSERT INTO tasks(client_id,title,due,note,recommendation_id,scope,status) VALUES(?,?,?,?,?,?,?)',(int(client_id),title.strip(),str(due),note,recommendation_id,self.scope,status))
    def update(self,task_id,status,note):
        if status not in ['Запланирована','В работе','Выполнена','Отменена']: raise ValueError('Неизвестный статус.')
        with self.connect() as db:
            self.execute(db,'UPDATE tasks SET status=?,note=? WHERE id=? AND scope=?',(status,note,int(task_id),self.scope))
    def process(self,recommendation_id):
        with self.connect() as db:
            # Legacy databases may retain the old global PK: namespaced IDs keep isolation.
            self.execute(db,'INSERT INTO processed(recommendation_id,scope) VALUES(?,?) ON CONFLICT DO NOTHING',(self.scope+'|'+recommendation_id,self.scope))
    def processed(self):
        with self.connect() as db:
            r=self.execute(db,'SELECT * FROM processed WHERE scope=?',(self.scope,))
            f=pd.DataFrame(r.fetchall(),columns=self.columns(r))
        f['recommendation_id']=f.recommendation_id.astype(str).str.removeprefix(self.scope+'|')
        return f
    def put(self,kind,key,value):
        with self.connect() as db:
            self.execute(db,'''INSERT INTO records(scope,kind,record_key,value) VALUES(?,?,?,?) ON CONFLICT(scope,kind,record_key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP''',(self.scope,kind,str(key),json.dumps(value,ensure_ascii=False)))
    def get(self,kind,key,default=None):
        with self.connect() as db:
            r=self.execute(db,'SELECT value FROM records WHERE scope=? AND kind=? AND record_key=?',(self.scope,kind,str(key))).fetchone()
        return json.loads(r[0]) if r else default
    def export(self):
        with self.connect() as db:
            r=self.execute(db,'SELECT kind,record_key,value,updated_at FROM records WHERE scope=?',(self.scope,))
            records=[dict(zip(self.columns(r),row)) for row in r.fetchall()]
        return json.dumps({'tasks':self.tasks().to_dict('records'),'records':records},ensure_ascii=False,default=str,indent=2)
