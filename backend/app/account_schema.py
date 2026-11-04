"""Separate JST accounts from external provider identities, preserving old callers."""
from datetime import datetime, timezone
from contextlib import closing
import sqlite3

from .db_core import backup


def normalize_accounts(path):
    with closing(sqlite3.connect(path, timeout=10)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        row = db.execute("SELECT type FROM sqlite_master WHERE name='auth_users'").fetchone()
        if row is None or row['type'] == 'view':
            return
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup(path, path.parent / '.migration-backups' / stamp / 'auth-before-identities.sqlite')
        # All DDL below belongs to a single transaction. Existing provider subjects,
        # user IDs, session hashes, expiration and CSRF secrets are retained.
        db.executescript('''BEGIN IMMEDIATE;
            CREATE TABLE users(id TEXT PRIMARY KEY,display_name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active','disabled','deleted')),created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,deleted_at INTEGER);
            CREATE TABLE user_identities(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,provider_subject TEXT NOT NULL,email TEXT NOT NULL,email_verified INTEGER NOT NULL DEFAULT 0,
                google_authoritative INTEGER NOT NULL DEFAULT 0,UNIQUE(provider,provider_subject));
            CREATE INDEX idx_identity_owner ON user_identities(user_id);
            CREATE TABLE roles(code TEXT PRIMARY KEY);
            INSERT INTO roles VALUES('user'),('developer');
            CREATE TABLE user_roles(user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,role_code TEXT NOT NULL REFERENCES roles(code),
                granted_at INTEGER NOT NULL,PRIMARY KEY(user_id,role_code));
            CREATE TABLE user_consents(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                purpose TEXT NOT NULL,policy_version TEXT NOT NULL,granted_at INTEGER NOT NULL,revoked_at INTEGER);
            CREATE TABLE security_events(id TEXT PRIMARY KEY,user_id TEXT,event_type TEXT NOT NULL,occurred_at INTEGER NOT NULL);
            INSERT INTO users(id,display_name,created_at,updated_at) SELECT id,name,created_at,updated_at FROM auth_users;
            INSERT INTO user_identities SELECT id,id,provider,subject,email,google_authoritative,google_authoritative FROM auth_users;
            INSERT INTO user_roles SELECT id,'user',created_at FROM auth_users;
            DROP TABLE auth_users;
            ALTER TABLE auth_sessions RENAME TO legacy_auth_sessions;
            CREATE TABLE auth_sessions(session_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                csrf TEXT NOT NULL,created_at INTEGER NOT NULL,last_seen INTEGER NOT NULL,expires_at INTEGER NOT NULL);
            INSERT INTO auth_sessions SELECT * FROM legacy_auth_sessions;
            DROP TABLE legacy_auth_sessions;
            CREATE VIEW auth_users AS SELECT u.id,i.provider,i.provider_subject AS subject,i.email,u.display_name AS name,u.created_at,u.updated_at,i.google_authoritative
                FROM users u JOIN user_identities i ON i.user_id=u.id WHERE u.status='active' AND u.deleted_at IS NULL;
            CREATE TRIGGER auth_users_insert INSTEAD OF INSERT ON auth_users BEGIN
                INSERT OR IGNORE INTO users(id,display_name,created_at,updated_at) VALUES(new.id,new.name,new.created_at,new.updated_at);
                INSERT OR IGNORE INTO user_identities VALUES(new.id,new.id,new.provider,new.subject,new.email,new.google_authoritative,new.google_authoritative);
                INSERT OR IGNORE INTO user_roles VALUES(new.id,'user',new.created_at); END;
            CREATE TRIGGER auth_users_update INSTEAD OF UPDATE ON auth_users BEGIN
                UPDATE users SET display_name=new.name,updated_at=new.updated_at WHERE id=old.id;
                UPDATE user_identities SET email=new.email,google_authoritative=new.google_authoritative WHERE user_id=old.id AND provider=old.provider; END;
            CREATE TRIGGER auth_users_delete INSTEAD OF DELETE ON auth_users BEGIN DELETE FROM users WHERE id=old.id; END;
            CREATE INDEX IF NOT EXISTS idx_sessions_owner ON auth_sessions(user_id);
            CREATE TRIGGER delete_sessions AFTER DELETE ON users BEGIN DELETE FROM auth_sessions WHERE user_id=old.id; END;
            COMMIT;''')
