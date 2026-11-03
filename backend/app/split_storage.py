"""Recoverable migration and atomic transactions across private SQLite files."""
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from .conversation_store import ConversationStore
from .db_core import backup, initialize


def attach_private(db, history_path, memory_path):
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    db.execute('ATTACH DATABASE ? AS chat', (str(history_path),))
    db.execute('ATTACH DATABASE ? AS memory', (str(memory_path),))
    # TEMP triggers may cross attached files. An account deletion through any
    # application connection removes private children in the same transaction.
    account_table = 'users' if db.execute("SELECT 1 FROM main.sqlite_master WHERE type='table' AND name='users'").fetchone() else 'auth_users'
    db.executescript(f'''CREATE TEMP TRIGGER IF NOT EXISTS delete_private_account AFTER DELETE ON main.{account_table} BEGIN
        DELETE FROM conversations WHERE user_id=old.id;
        DELETE FROM history_states WHERE user_id=old.id;
        DELETE FROM memories WHERE user_id=old.id;
        DELETE FROM memory_checkpoints WHERE user_id=old.id;
        DELETE FROM memory_jobs WHERE user_id=old.id;
        DELETE FROM recall_requests WHERE user_id=old.id;
        DELETE FROM auth_sessions WHERE user_id=old.id;
        DELETE FROM outbox_events WHERE owner_user_id=old.id;
    END;''')


def setup_private(store):
    history_path = store.path.parent / 'conversations.sqlite'
    memory_path = store.path.parent / 'memory.sqlite'
    history = ConversationStore(history_path)
    initialize(memory_path, 'memory')
    raw = sqlite3.connect(store.path, timeout=10)
    raw.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        legacy = tables & {'account_chat_history', 'room_memories', 'room_checkpoints'}
        if legacy:
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            destination = store.path.parent / '.migration-backups' / stamp
            backup(store.path, destination / 'auth-before-split.sqlite')
            backup(history_path, destination / 'conversations-before.sqlite')
            backup(memory_path, destination / 'memory-before.sqlite')
            raw.execute('PRAGMA journal_mode=DELETE')
            # Capture legacy rows before attaching names that have compatibility views.
            snapshots = list(raw.execute('SELECT * FROM account_chat_history')) if 'account_chat_history' in legacy else []
            memories = list(raw.execute('SELECT * FROM room_memories')) if 'room_memories' in legacy else []
            checkpoints = list(raw.execute('SELECT * FROM room_checkpoints')) if 'room_checkpoints' in legacy else []
            attach_private(raw, history_path, memory_path)
            raw.execute('BEGIN IMMEDIATE')
            raw.execute('DROP TRIGGER IF EXISTS main.delete_private_room_memory')
            # Rename legacy tables inside the transaction so unqualified names
            # below resolve only to the normalized databases.
            for name in legacy:
                raw.execute(f'ALTER TABLE main.{name} RENAME TO legacy_{name}')
            for row in snapshots:
                payload = json.loads(row['payload'])
                history.save(row['user_id'], payload, 0, raw)
                raw.execute('UPDATE history_states SET revision=? WHERE user_id=?', (row['revision'], row['user_id']))
                migrated = history.load(row['user_id'], raw)
                original = {**payload, 'revision': row['revision']}
                original.setdefault('activeSessionId', None)
                if migrated != original:
                    raise RuntimeError('History migration mismatch; original database retained')
            for row in memories:
                raw.execute('INSERT INTO memory.room_memories VALUES(?,?,?,?,?,?)', tuple(row))
            for row in checkpoints:
                raw.execute('INSERT INTO memory.room_checkpoints VALUES(?,?,?,?,?)', tuple(row))
            for name in legacy:
                raw.execute(f'DROP TABLE main.legacy_{name}')
            raw.execute('PRAGMA main.user_version=4')
            raw.commit()
            (destination / 'migration.json').write_text(json.dumps({'history_accounts': len(snapshots), 'memories': len(memories), 'checkpoints': len(checkpoints)}, indent=2))
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    store.history = history
    store.memory_path = memory_path


def invalidate_memory(db):
    """Consume deletion/edit events in the SAME attached transaction as history."""
    events = list(db.execute("SELECT * FROM chat.outbox_events WHERE state='pending' ORDER BY created_at"))
    for event in events:
        user, source = event['owner_user_id'], event['aggregate_id']
        affected = {source}
        links = list(db.execute('SELECT room_id,parent_id FROM room_memories WHERE user_id=?', (user,)))
        while True:
            descendants = {r['room_id'] for r in links if r['parent_id'] in affected}
            added = descendants - affected
            if not added:
                break
            affected.update(added)
        for room in affected:
            # A room's own inherited memory describes its parent, so changing a
            # message invalidates descendants rather than erasing that inheritance.
            if room != source or event['event_type'] == 'room_deleted':
                db.execute('DELETE FROM memories WHERE user_id=? AND conversation_id=?', (user, room))
            db.execute('DELETE FROM memory_checkpoints WHERE user_id=? AND conversation_id=?', (user, room))
            db.execute("UPDATE memory_jobs SET state='cancelled' WHERE user_id=? AND conversation_id=? AND state IN ('pending','running')", (user, room))
        db.execute("UPDATE chat.outbox_events SET state='done',completed_at=strftime('%s','now')*1000 WHERE id=?", (event['id'],))
