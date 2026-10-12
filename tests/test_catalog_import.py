"""Regression: a Cloud worker may retain live_data from before catalogue support."""
import subprocess
import sys
import unittest


class CatalogueImportTests(unittest.TestCase):
    def test_catalogue_import_with_previous_live_module(self):
        script = '''
import sales_center.live_data as old
for name in ('load_catalog', 'normalize_catalog'):
    delattr(old, name)
from sales_center.price_catalog import load_catalog, normalize_catalog
assert callable(load_catalog)
assert normalize_catalog([], []).empty
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
