"""Local SQLite tasks, notes and recommendation processing; no secrets."""
from pathlib import Path
import sqlite3
import pandas as pd

class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL, title TEXT NOT NULL,
                due TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Запланирована',
                note TEXT NOT NULL DEFAULT '', recommendation_id TEXT);
                CREATE TABLE IF NOT EXISTS processed (
                recommendation_id TEXT PRIMARY KEY, processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);''')
    def connect(self):
        return sqlite3.connect(self.path, timeout=10)
    def tasks(self):
        with self.connect() as db:
            return pd.read_sql_query('SELECT * FROM tasks ORDER BY due, id', db)
    def add(self, client_id, title, due, note='', recommendation_id=None):
        if not title.strip():
            raise ValueError('Укажите название задачи.')
        with self.connect() as db:
            db.execute('INSERT INTO tasks(client_id,title,due,note,recommendation_id) VALUES(?,?,?,?,?)',
                       (int(client_id), title.strip(), str(due), note, recommendation_id))
    def update(self, task_id, status, note):
        if status not in ['Запланирована', 'В работе', 'Выполнена', 'Отменена']:
            raise ValueError('Неизвестный статус задачи.')
        with self.connect() as db:
            db.execute('UPDATE tasks SET status=?,note=? WHERE id=?', (status,note,int(task_id)))
    def process(self, recommendation_id):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO processed(recommendation_id) VALUES(?)', (recommendation_id,))
    def processed(self):
        with self.connect() as db:
            return pd.read_sql_query('SELECT * FROM processed', db)
