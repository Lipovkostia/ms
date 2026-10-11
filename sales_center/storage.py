"""Account/user-scoped records, with SQLite or external PostgreSQL."""
from pathlib import Path
import os
import json
import pandas as pd
from sqlalchemy import create_engine, inspect

class Store:
    def __init__(self,path,scope='legacy',database_url=None):
        self.scope=scope
        url=database_url or os.environ.get('DATABASE_URL')
        self.persistent=bool(url)
        if url:
            if url.startswith('postgres://'): url=url.replace('postgres://','postgresql+psycopg://',1)
            if url.startswith('postgresql://'): url=url.replace('postgresql://','postgresql+psycopg://',1)
            if not url.startswith('postgresql+psycopg://'): raise ValueError('DATABASE_URL должен указывать PostgreSQL.')
            self.engine=create_engine(url,pool_pre_ping=True,connect_args={'connect_timeout':10})
        else:
            Path(path).parent.mkdir(parents=True,exist_ok=True)
            self.engine=create_engine('sqlite:///'+str(path),connect_args={'timeout':10})
        pk='BIGSERIAL PRIMARY KEY' if self.persistent else 'INTEGER PRIMARY KEY'
        with self.connect() as db:
            for sql in [f'''CREATE TABLE IF NOT EXISTS tasks (id {pk},client_id BIGINT NOT NULL,title TEXT NOT NULL,due TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Запланирована',note TEXT NOT NULL DEFAULT '',recommendation_id TEXT,scope TEXT NOT NULL DEFAULT 'legacy')''',
                '''CREATE TABLE IF NOT EXISTS processed (recommendation_id TEXT NOT NULL,processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,scope TEXT NOT NULL DEFAULT 'legacy',PRIMARY KEY(scope,recommendation_id))''',
                '''CREATE TABLE IF NOT EXISTS records (scope TEXT NOT NULL,kind TEXT NOT NULL,record_key TEXT NOT NULL,value TEXT NOT NULL,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(scope,kind,record_key))''']:
                db.exec_driver_sql(sql)
            # Preserve existing records; old anonymous tasks stay in legacy scope.
            if 'scope' not in {c['name'] for c in inspect(db).get_columns('tasks')}:
                db.exec_driver_sql("ALTER TABLE tasks ADD COLUMN scope TEXT NOT NULL DEFAULT 'legacy'")
            if 'scope' not in {c['name'] for c in inspect(db).get_columns('processed')}:
                db.exec_driver_sql("ALTER TABLE processed ADD COLUMN scope TEXT NOT NULL DEFAULT 'legacy'")
    def connect(self): return self.engine.begin()
    def execute(self,db,sql,args=()):
        return db.exec_driver_sql(sql.replace('?', '%s') if self.persistent else sql,tuple(args))
    def tasks(self):
        with self.connect() as db:
            r=self.execute(db,'SELECT * FROM tasks WHERE scope=? ORDER BY due,id',(self.scope,))
            return pd.DataFrame(r.fetchall(),columns=r.keys())
    def add(self,client_id,title,due,note='',recommendation_id=None):
        if not title.strip(): raise ValueError('Укажите название задачи.')
        with self.connect() as db:
            self.execute(db,'INSERT INTO tasks(client_id,title,due,note,recommendation_id,scope) VALUES(?,?,?,?,?,?)',(int(client_id),title.strip(),str(due),note,recommendation_id,self.scope))
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
            f=pd.DataFrame(r.fetchall(),columns=r.keys())
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
            records=[dict(row._mapping) for row in r]
        return json.dumps({'tasks':self.tasks().to_dict('records'),'records':records},ensure_ascii=False,default=str,indent=2)
