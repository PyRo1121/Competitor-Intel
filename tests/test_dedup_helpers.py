import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import connection as db_connection
from db.ingest import (
    canonical_url_for_dedup,
    get_company_id,
    insert_raw_signal_dedup,
    raw_signal_exists,
    url_dedup_key,
)


class DedupHelperTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "dedup_test.db"
        self._old_override = db_connection._test_db_override
        db_connection._test_db_override = self.db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            """
            CREATE TABLE raw_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                source TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                data_json TEXT NOT NULL,
                detected_at TEXT,
                processed INTEGER DEFAULT 0
            )
            """
        )
        self.conn.execute(
            "CREATE UNIQUE INDEX idx_raw_signals_dedup ON raw_signals(source, signal_type)"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        db_connection._test_db_override = self._old_override
        self._tmp.cleanup()

    def test_url_dedup_key_is_stable(self):
        url = "https://example.com/article"
        self.assertEqual(url_dedup_key(url), url_dedup_key(url))
        # Trailing slash is normalized away for dedup (6-A06).
        self.assertEqual(url_dedup_key(url), url_dedup_key(url + "/"))
        self.assertNotEqual(url_dedup_key(url), url_dedup_key(url + "/other"))

    def test_url_dedup_key_ignores_fragment(self):
        base = "https://example.com/article"
        self.assertEqual(url_dedup_key(f"{base}#rs1"), url_dedup_key(f"{base}#rs99"))
        self.assertEqual(
            canonical_url_for_dedup(f"{base}#rs1"),
            canonical_url_for_dedup(base),
        )

    def test_insert_raw_signal_dedup(self):
        cursor = self.conn.cursor()
        self.assertTrue(
            insert_raw_signal_dedup(
                cursor,
                "test_source",
                "https://example.com/x",
                {"title": "Hello", "kind": "news"},
            )
        )
        self.conn.commit()
        key = url_dedup_key("https://example.com/x")
        self.assertTrue(raw_signal_exists(cursor, "test_source", key))
        self.assertFalse(
            insert_raw_signal_dedup(
                cursor,
                "test_source",
                "https://example.com/x",
                {"title": "Duplicate"},
            )
        )
        count = cursor.execute("SELECT COUNT(*) FROM raw_signals").fetchone()[0]
        self.assertEqual(count, 1)
        payload = json.loads(
            cursor.execute(
                "SELECT data_json FROM raw_signals WHERE source = ?", ("test_source",)
            ).fetchone()[0]
        )
        self.assertEqual(payload["title"], "Hello")
        self.assertEqual(payload["kind"], "news")

    def test_get_company_id_case_insensitive(self):
        self.conn.execute(
            """
            CREATE TABLE companies (
                id INTEGER PRIMARY KEY,
                name TEXT,
                slug TEXT,
                x_handle TEXT
            )
            """
        )
        self.conn.execute(
            "INSERT INTO companies (id, name, slug, x_handle) "
            "VALUES (1, 'Anthropic', 'anthropic', NULL)"
        )
        self.conn.commit()
        self.assertEqual(get_company_id("anthropic"), 1)
        self.assertEqual(get_company_id("ANTHROPIC"), 1)
        self.assertIsNone(get_company_id("Unknown Corp XYZ"))


def test_url_dedup_key_is_stable_pytest():
    DedupHelperTests().test_url_dedup_key_is_stable()


def test_insert_raw_signal_dedup_pytest():
    t = DedupHelperTests()
    t.setUp()
    try:
        t.test_insert_raw_signal_dedup()
    finally:
        t.tearDown()


if __name__ == "__main__":
    unittest.main()
