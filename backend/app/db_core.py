"""Versioned SQLite connections. No dependency on FastAPI, Ollama or Qdrant."""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import sqlite3
import time

SCHEMA_ROOT=Path(__file__).resolve().parent/'schemas'


@contextmanager
def connect(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=10)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    try:
        with db:yield db
    finally:db.close()


def initialize(path,kind):
    sql_path=next(SCHEMA_ROOT.glob(f'*_{kind}.sql'))
    sql=sql_path.read_text(encoding='utf-8');checksum=hashlib.sha256(sql.encode()).hexdigest()
    with connect(path) as db:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations' AND type='table'").fetchone()
        if exists:
            row=db.execute('SELECT checksum FROM schema_migrations WHERE version=1').fetchone()
            if row is None or row['checksum']!=checksum:raise RuntimeError(f'Unsupported {kind} database schema; explicit migration required')
            return
        # Only initialize an empty destination; never overwrite an old schema.
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone():
            raise RuntimeError(f'{kind} destination is not empty')
        db.executescript(sql)
        db.execute('INSERT INTO schema_migrations VALUES(?,?,?)',(1,checksum,int(time.time()*1000)))


def backup(source,destination):
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    with connect(source) as db:
        target = sqlite3.connect(destination)
        try:
            db.backup(target)
        finally:
            target.close()
