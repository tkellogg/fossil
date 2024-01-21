"""
Migration scripts to update the SQLite schema that are run at the last possible moment.
There's no version numbers, so each script is responsible for "knowing" when it needs
to run itself.

Typically you should have a @lru_cache on each function to prevent unnecessary invocations,
but also know that it'll get re-invoked every time the server restarts.
"""
import functools
import os
import random
import sqlite3
import string

from fossil_mastodon import config


@functools.cache
def create_database():
    if os.path.exists(config.ConfigHandler.DATABASE_PATH):
        return

    with sqlite3.connect(config.ConfigHandler.DATABASE_PATH) as conn:
        c = conn.cursor()

        # Create the toots table if it doesn't exist
        c.execute('''
            CREATE TABLE IF NOT EXISTS toots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                author TEXT,
                url TEXT,
                created_at DATETIME,
                embedding BLOB,
                orig_json TEXT,
                cluster TEXT  -- Added cluster column
            )
        ''')

        conn.commit()


@functools.lru_cache()
def create_session_table():
    create_database()
    with sqlite3.connect(config.ConfigHandler.DATABASE_PATH) as conn:
        c = conn.cursor()

        # Create the toots table if it doesn't exist
        c.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                algorithm_spec TEXT,
                algorithm BLOB,
                ui_settings TEXT
            )
        ''')

        try:
            c.execute('''
                ALTER TABLE sessions ADD COLUMN settings TEXT
            ''')
        except sqlite3.OperationalError:
            pass

        # Add session name
        try:
            c.execute('''
                ALTER TABLE sessions ADD COLUMN name TEXT
            ''')
        except sqlite3.OperationalError:
            pass

        c.execute("DELETE FROM sessions WHERE name IS NULL")

        c2 = conn.cursor()
        c2.execute("SELECT COUNT(*) FROM sessions")
        row_count = c2.fetchone()[0]
        if row_count == 0:
            rand_str = "".join(random.choice(string.ascii_lowercase) for _ in range(32))
            c2.execute("""
            INSERT INTO sessions (id, name, settings)
                VALUES (?, ?, '{}')
            """, (rand_str, "Main"))

        conn.commit()