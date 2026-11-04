-- Design v1 only. Apply to NEW databases after an approved migration.
-- Every application connection must enable foreign_keys and busy_timeout.
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;
PRAGMA busy_timeout = 10000;
CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY, checksum TEXT NOT NULL, applied_at INTEGER NOT NULL
);
CREATE TABLE outbox_events (
  id TEXT NOT NULL PRIMARY KEY,
  event_key TEXT NOT NULL UNIQUE,
  event_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  owner_user_id TEXT,
  aggregate_revision INTEGER NOT NULL CHECK(aggregate_revision >= 0),
  payload_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(payload_json)),
  state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','processing','done','failed')),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
  available_at INTEGER NOT NULL, lease_until INTEGER, last_error TEXT,
  created_at INTEGER NOT NULL, completed_at INTEGER
);
CREATE INDEX idx_outbox_pending ON outbox_events(state,available_at);


CREATE TABLE history_states(user_id TEXT PRIMARY KEY, revision INTEGER NOT NULL CHECK(revision>=0), active_session_id TEXT);
CREATE TABLE conversations(
 user_id TEXT NOT NULL,id TEXT NOT NULL,title TEXT NOT NULL,tax_category TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 0,pinned INTEGER NOT NULL DEFAULT 0,saved INTEGER NOT NULL DEFAULT 0,
 title_edited INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,deleted_at INTEGER,
 extra_json TEXT NOT NULL CHECK(json_valid(extra_json)),display_order INTEGER NOT NULL,
 PRIMARY KEY(user_id,id),CHECK(tax_category IN ('PBB-P2','JPB','PBJT','BPHTB','REKLAME','PAT')));
CREATE INDEX idx_room_owner ON conversations(user_id,pinned DESC,updated_at DESC);
CREATE TABLE messages(
 user_id TEXT NOT NULL,conversation_id TEXT NOT NULL,id TEXT NOT NULL,sequence_no INTEGER NOT NULL CHECK(sequence_no>0),
 role TEXT NOT NULL CHECK(role IN ('user','assistant')),content TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('completed','failed','cancelled')),revision INTEGER NOT NULL CHECK(revision>0),
 created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,deleted_at INTEGER,
 extra_json TEXT NOT NULL CHECK(json_valid(extra_json)),has_references INTEGER NOT NULL,has_followups INTEGER NOT NULL,
 PRIMARY KEY(user_id,conversation_id,id),UNIQUE(user_id,conversation_id,sequence_no),
 FOREIGN KEY(user_id,conversation_id) REFERENCES conversations(user_id,id) ON DELETE CASCADE);
CREATE TABLE message_references(
 user_id TEXT NOT NULL,conversation_id TEXT NOT NULL,message_id TEXT NOT NULL,position INTEGER NOT NULL,
 citation_no INTEGER,document_version_id TEXT,chunk_id TEXT,document_title_snapshot TEXT,
 reference_json TEXT NOT NULL CHECK(json_valid(reference_json)),PRIMARY KEY(user_id,conversation_id,message_id,position),
 FOREIGN KEY(user_id,conversation_id,message_id) REFERENCES messages(user_id,conversation_id,id) ON DELETE CASCADE);
CREATE TABLE message_followups(
 user_id TEXT NOT NULL,conversation_id TEXT NOT NULL,message_id TEXT NOT NULL,position INTEGER NOT NULL,prompt TEXT NOT NULL,
 PRIMARY KEY(user_id,conversation_id,message_id,position),
 FOREIGN KEY(user_id,conversation_id,message_id) REFERENCES messages(user_id,conversation_id,id) ON DELETE CASCADE);
CREATE TABLE conversation_links(user_id TEXT NOT NULL,parent_id TEXT NOT NULL,child_id TEXT NOT NULL,created_at INTEGER NOT NULL,
 PRIMARY KEY(user_id,child_id),CHECK(parent_id<>child_id),
 FOREIGN KEY(user_id,parent_id) REFERENCES conversations(user_id,id) ON DELETE CASCADE,
 FOREIGN KEY(user_id,child_id) REFERENCES conversations(user_id,id) ON DELETE CASCADE);
CREATE VIRTUAL TABLE messages_fts USING fts5(content,content='messages',content_rowid='rowid',tokenize='unicode61');
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN INSERT INTO messages_fts(rowid,content) VALUES(new.rowid,new.content); END;
CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN INSERT INTO messages_fts(messages_fts,rowid,content) VALUES('delete',old.rowid,old.content); END;
CREATE TRIGGER messages_au AFTER UPDATE OF content ON messages BEGIN
 INSERT INTO messages_fts(messages_fts,rowid,content) VALUES('delete',old.rowid,old.content);
 INSERT INTO messages_fts(rowid,content) VALUES(new.rowid,new.content); END;
