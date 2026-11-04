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

-- Source room/message/user IDs below belong to other SQLite files. Validate
-- ownership, deletion and source revision again at retrieval time.
CREATE TABLE memories (
  id TEXT NOT NULL PRIMARY KEY, user_id TEXT NOT NULL,
  scope TEXT NOT NULL CHECK(scope IN ('continuation','cross_chat','user_preference')),
  kind TEXT NOT NULL CHECK(kind IN ('summary','fact','decision','preference')),
  conversation_id TEXT NOT NULL,
  entity_key TEXT, fact_key TEXT,
  content TEXT NOT NULL,
  value_json TEXT CHECK(value_json IS NULL OR json_valid(value_json)),
  authority TEXT NOT NULL CHECK(authority IN ('user_statement','generated_summary')),
  state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','active','superseded','invalidated','deleted')),
  revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
  supersedes_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
  created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, deleted_at INTEGER,
  UNIQUE(user_id,id),
  CHECK(kind<>'fact' OR (entity_key IS NOT NULL AND fact_key IS NOT NULL))
);
CREATE UNIQUE INDEX idx_current_fact ON memories(user_id,conversation_id,entity_key,fact_key)
  WHERE kind='fact' AND state='active' AND deleted_at IS NULL;
CREATE INDEX idx_memory_owner ON memories(user_id,scope,state,deleted_at,updated_at DESC);
CREATE TABLE memory_provenance (
  memory_id TEXT NOT NULL, user_id TEXT NOT NULL,
  source_conversation_id TEXT NOT NULL, source_message_id TEXT NOT NULL,
  source_revision INTEGER NOT NULL CHECK(source_revision>0),
  source_role TEXT NOT NULL CHECK(source_role IN ('user','assistant')),
  source_sequence INTEGER NOT NULL CHECK(source_sequence>0),
  PRIMARY KEY(memory_id,source_message_id),
  FOREIGN KEY(user_id,memory_id) REFERENCES memories(user_id,id) ON DELETE CASCADE
);
CREATE INDEX idx_provenance_source ON memory_provenance(user_id,source_message_id);
CREATE TABLE memory_checkpoints (
  user_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
  source_revision INTEGER NOT NULL CHECK(source_revision>=0),
  through_sequence INTEGER NOT NULL CHECK(through_sequence>=0),
  algorithm_version TEXT NOT NULL, fingerprint TEXT NOT NULL,
  summary TEXT NOT NULL, updated_at INTEGER NOT NULL,
  PRIMARY KEY(user_id,conversation_id)
);
CREATE TABLE memory_jobs (
  id TEXT NOT NULL PRIMARY KEY, user_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
  job_type TEXT NOT NULL CHECK(job_type IN ('summarize','extract_facts','index','purge')),
  dedupe_key TEXT NOT NULL UNIQUE,
  source_revision INTEGER NOT NULL CHECK(source_revision>=0),
  state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','running','done','failed','cancelled')),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts>=0),
  available_at INTEGER NOT NULL, lease_until INTEGER,
  created_at INTEGER NOT NULL, completed_at INTEGER, last_error TEXT
);
CREATE INDEX idx_memory_jobs ON memory_jobs(state,available_at);
CREATE TABLE memory_index_records (
  memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  embedding_profile_id TEXT NOT NULL,
  collection_name TEXT NOT NULL, point_id TEXT NOT NULL,
  indexed_revision INTEGER NOT NULL CHECK(indexed_revision>0),
  state TEXT NOT NULL CHECK(state IN ('pending','ready','deleting','failed')),
  updated_at INTEGER NOT NULL,
  PRIMARY KEY(memory_id,embedding_profile_id), UNIQUE(collection_name,point_id)
);
CREATE TABLE recall_requests (
  id TEXT NOT NULL PRIMARY KEY, user_id TEXT NOT NULL,
  target_conversation_id TEXT NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('explicit','continuation')),
  state TEXT NOT NULL CHECK(state IN ('success','no_match','denied','failed')),
  created_at INTEGER NOT NULL
);
CREATE TABLE recall_evidence (
  request_id TEXT NOT NULL REFERENCES recall_requests(id) ON DELETE CASCADE,
  position INTEGER NOT NULL CHECK(position>=0),
  memory_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
  source_conversation_id TEXT NOT NULL, source_message_id TEXT,
  source_revision INTEGER NOT NULL CHECK(source_revision>=0),
  score REAL, PRIMARY KEY(request_id,position)
);

CREATE TABLE memory_dependencies (
  user_id TEXT NOT NULL, memory_id TEXT NOT NULL, source_memory_id TEXT NOT NULL,
  source_revision INTEGER NOT NULL CHECK(source_revision>0),
  PRIMARY KEY(memory_id,source_memory_id), CHECK(memory_id<>source_memory_id),
  FOREIGN KEY(user_id,memory_id) REFERENCES memories(user_id,id) ON DELETE CASCADE,
  FOREIGN KEY(user_id,source_memory_id) REFERENCES memories(user_id,id) ON DELETE CASCADE
);
CREATE INDEX idx_memory_dependents ON memory_dependencies(user_id,source_memory_id);

CREATE TABLE continuation_details(memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,parent_id TEXT NOT NULL,fingerprint TEXT NOT NULL);
CREATE VIEW room_memories AS SELECT m.user_id,m.conversation_id AS room_id,d.parent_id,m.content AS summary,d.fingerprint,m.created_at
 FROM memories m JOIN continuation_details d ON d.memory_id=m.id WHERE m.state='active' AND m.deleted_at IS NULL;
CREATE TRIGGER room_memory_insert INSTEAD OF INSERT ON room_memories BEGIN
 INSERT INTO memories(id,user_id,scope,kind,conversation_id,content,authority,state,created_at,updated_at)
 VALUES(lower(hex(randomblob(16))),new.user_id,'continuation','summary',new.room_id,new.summary,'generated_summary','active',new.created_at,new.created_at);
 INSERT INTO continuation_details VALUES((SELECT id FROM memories WHERE user_id=new.user_id AND conversation_id=new.room_id ORDER BY rowid DESC LIMIT 1),new.parent_id,new.fingerprint); END;
CREATE UNIQUE INDEX idx_continuation_owner ON memories(user_id,conversation_id) WHERE scope='continuation' AND state='active';
CREATE TRIGGER room_memory_delete INSTEAD OF DELETE ON room_memories BEGIN
 DELETE FROM memories WHERE user_id=old.user_id AND conversation_id=old.room_id AND scope='continuation'; END;
CREATE VIEW room_checkpoints AS SELECT user_id,conversation_id AS room_id,fingerprint,summary,updated_at FROM memory_checkpoints;
CREATE TRIGGER room_checkpoint_insert INSTEAD OF INSERT ON room_checkpoints BEGIN
 INSERT INTO memory_checkpoints VALUES(new.user_id,new.room_id,0,0,'2',new.fingerprint,new.summary,new.updated_at)
 ON CONFLICT(user_id,conversation_id) DO UPDATE SET fingerprint=excluded.fingerprint,summary=excluded.summary,updated_at=excluded.updated_at; END;
CREATE TRIGGER room_checkpoint_delete INSTEAD OF DELETE ON room_checkpoints BEGIN
 DELETE FROM memory_checkpoints WHERE user_id=old.user_id AND conversation_id=old.room_id; END;
