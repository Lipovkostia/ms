"""Reproduce a host with optional database packages missing."""
import subprocess
import sys
import unittest
from pathlib import Path

class DependencyTests(unittest.TestCase):
    def test_sqlite_and_app_start_without_optional_database_drivers(self):
        script='''
import importlib.abc
import sys
import tempfile
from pathlib import Path
class BlockDrivers(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'sqlalchemy', 'psycopg'}:
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, BlockDrivers())
from sales_center.storage import Store, StoreError
from streamlit.testing.v1 import AppTest
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'db.sqlite'
    store=Store(path, database_url=None)
    store.add(1,'Контакт','2026-10-12')
    store.put('draft',1,'Текст')
    assert len(store.tasks()) == 1
    assert store.get('draft',1) == 'Текст'
    try:
        Store(path, database_url='postgresql://placeholder/placeholder')
    except StoreError as exc:
        assert 'Драйвер PostgreSQL' in str(exc)
    else:
        raise AssertionError('Missing driver must show actionable error')
at=AppTest.from_file('app.py',default_timeout=30).run()
assert not at.exception, [e.message for e in at.exception]
assert any('Подключите Мой Склад' in item.value for item in at.info)
'''
        import os
        env=os.environ.copy();env.pop('DATABASE_URL',None)
        result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,0,result.stderr)
