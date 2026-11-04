-- Design v1 only. Apply to NEW databases after an approved migration.
-- Every application connection must enable foreign_keys and busy_timeout.
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
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

CREATE TABLE tax_categories (
  code TEXT NOT NULL PRIMARY KEY, name TEXT NOT NULL
);
INSERT INTO tax_categories VALUES
 ('PBB-P2','Pajak Bumi dan Bangunan Perdesaan dan Perkotaan'),
 ('PBJT','Pajak Barang dan Jasa Tertentu'),('BPHTB','Bea Perolehan Hak atas Tanah dan Bangunan'),
 ('REKLAME','Pajak Reklame'),('PAT','Pajak Air Tanah');
CREATE TABLE documents (
  id TEXT NOT NULL PRIMARY KEY, code TEXT UNIQUE, title TEXT NOT NULL,
  document_type TEXT NOT NULL CHECK(document_type IN ('regulation','table','case','guide','other')),
  issuer TEXT, jurisdiction TEXT, instrument_type TEXT,
  document_number TEXT, document_year INTEGER CHECK(document_year>0 AND document_year<10000),
  official_source_url TEXT,
  access_scope TEXT NOT NULL DEFAULT 'restricted' CHECK(access_scope IN ('public','authenticated','restricted')),
  lifecycle TEXT NOT NULL DEFAULT 'draft' CHECK(lifecycle IN ('draft','published','deleting','deleted')),
  revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
  created_by TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, deleted_at INTEGER
);
CREATE TABLE document_access_grants (
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  principal_type TEXT NOT NULL CHECK(principal_type IN ('user','role')),
  principal_id TEXT NOT NULL, granted_at INTEGER NOT NULL, granted_by TEXT NOT NULL,
  PRIMARY KEY(document_id,principal_type,principal_id)
);
CREATE TABLE files (
  id TEXT NOT NULL PRIMARY KEY,
  storage_key TEXT NOT NULL UNIQUE,
  original_name TEXT NOT NULL, mime_type TEXT NOT NULL,
  sha256 TEXT NOT NULL CHECK(length(sha256)=64), size_bytes INTEGER NOT NULL CHECK(size_bytes>=0),
  state TEXT NOT NULL CHECK(state IN ('staged','available','deleting','deleted')),
  created_at INTEGER NOT NULL, deleted_at INTEGER
);
CREATE INDEX idx_files_hash ON files(sha256);
CREATE TABLE document_versions (
  id TEXT NOT NULL PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  version_label TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'staged' CHECK(state IN ('staged','extracting','extracted','indexing','ready','active','superseded','rejected','failed','deleting','deleted')),
  publication_date TEXT, effective_from TEXT, effective_to TEXT,
  legal_status TEXT NOT NULL DEFAULT 'unknown' CHECK(legal_status IN ('unknown','draft','effective','amended','repealed','not_applicable')),
  parser_name TEXT, parser_version TEXT, chunking_profile TEXT,
  extraction_quality TEXT NOT NULL DEFAULT 'unchecked' CHECK(extraction_quality IN ('unchecked','passed','needs_attention','failed')),
  revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
  created_by TEXT NOT NULL, created_at INTEGER NOT NULL, activated_at INTEGER,
  deleted_at INTEGER,
  UNIQUE(document_id,version_label),
  CHECK(effective_to IS NULL OR effective_from IS NULL OR effective_to>=effective_from)
);
CREATE INDEX idx_versions_lookup ON document_versions(document_id,state,effective_from,effective_to);
CREATE TABLE document_version_files (
  version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  file_id TEXT NOT NULL REFERENCES files(id),
  purpose TEXT NOT NULL CHECK(purpose IN ('original','extracted','preview')),
  PRIMARY KEY(version_id,file_id,purpose)
);
CREATE UNIQUE INDEX idx_one_original ON document_version_files(version_id) WHERE purpose='original';
CREATE TABLE version_tax_categories (
  version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  tax_code TEXT NOT NULL REFERENCES tax_categories(code),
  assigned_by TEXT NOT NULL, PRIMARY KEY(version_id,tax_code)
);
CREATE TABLE document_pages (
  version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  physical_page INTEGER NOT NULL CHECK(physical_page>0), printed_label TEXT,
  extracted_text TEXT NOT NULL DEFAULT '',
  extraction_method TEXT NOT NULL CHECK(extraction_method IN ('text','ocr','manual')),
  quality_state TEXT NOT NULL CHECK(quality_state IN ('unchecked','passed','needs_attention','failed')),
  PRIMARY KEY(version_id,physical_page)
);
CREATE TABLE document_sections (
  id TEXT NOT NULL PRIMARY KEY,
  version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  parent_id TEXT,
  heading TEXT NOT NULL, section_code TEXT,
  kind TEXT NOT NULL CHECK(kind IN ('chapter','article','paragraph','table','annex','other')),
  physical_page_start INTEGER CHECK(physical_page_start>0), physical_page_end INTEGER,
  UNIQUE(version_id,id),
  FOREIGN KEY(version_id,parent_id) REFERENCES document_sections(version_id,id),
  CHECK(physical_page_end IS NULL OR physical_page_end>=physical_page_start)
);
CREATE TABLE document_chunks (
  id TEXT NOT NULL PRIMARY KEY,
  version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  section_id TEXT, sequence_no INTEGER NOT NULL CHECK(sequence_no>0),
  text TEXT NOT NULL CHECK(length(trim(text))>0),
  content_sha256 TEXT NOT NULL CHECK(length(content_sha256)=64),
  physical_page_start INTEGER CHECK(physical_page_start>0), physical_page_end INTEGER,
  sheet_name TEXT, row_start INTEGER, row_end INTEGER,
  locator_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(locator_json)),
  token_estimate INTEGER CHECK(token_estimate>=0),
  state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','ready','invalidated','deleted')),
  revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
  UNIQUE(version_id,sequence_no), UNIQUE(version_id,id),
  FOREIGN KEY(version_id,section_id) REFERENCES document_sections(version_id,id),
  CHECK(physical_page_end IS NULL OR physical_page_end>=physical_page_start),
  CHECK(row_end IS NULL OR row_start IS NULL OR row_end>=row_start)
);
CREATE INDEX idx_chunks_version ON document_chunks(version_id,state,sequence_no);
CREATE TABLE chunk_tax_categories (
  version_id TEXT NOT NULL, chunk_id TEXT NOT NULL,
  tax_code TEXT NOT NULL,
  PRIMARY KEY(chunk_id,tax_code),
  FOREIGN KEY(version_id,chunk_id) REFERENCES document_chunks(version_id,id) ON DELETE CASCADE,
  FOREIGN KEY(version_id,tax_code) REFERENCES version_tax_categories(version_id,tax_code)
);
CREATE INDEX idx_chunks_category ON chunk_tax_categories(tax_code,chunk_id);
CREATE TABLE chunk_relations (
  version_id TEXT NOT NULL, source_chunk_id TEXT NOT NULL, target_chunk_id TEXT NOT NULL,
  relation_type TEXT NOT NULL CHECK(relation_type IN ('requires','exception','table_header','continues','example')),
  PRIMARY KEY(source_chunk_id,target_chunk_id,relation_type),
  FOREIGN KEY(version_id,source_chunk_id) REFERENCES document_chunks(version_id,id) ON DELETE CASCADE,
  FOREIGN KEY(version_id,target_chunk_id) REFERENCES document_chunks(version_id,id) ON DELETE CASCADE,
  CHECK(source_chunk_id<>target_chunk_id)
);
CREATE TABLE embedding_profiles (
  id TEXT NOT NULL PRIMARY KEY, model_name TEXT NOT NULL, model_revision TEXT NOT NULL,
  dimension INTEGER NOT NULL CHECK(dimension>0),
  distance_metric TEXT NOT NULL CHECK(distance_metric IN ('cosine','dot','euclidean')),
  normalization TEXT NOT NULL, configuration_json TEXT NOT NULL CHECK(json_valid(configuration_json)),
  created_at INTEGER NOT NULL,
  UNIQUE(model_name,model_revision,dimension,normalization,configuration_json)
);
CREATE TABLE index_generations (
  id TEXT NOT NULL PRIMARY KEY,
  embedding_profile_id TEXT NOT NULL REFERENCES embedding_profiles(id),
  collection_name TEXT NOT NULL UNIQUE,
  state TEXT NOT NULL CHECK(state IN ('building','validated','active','retired','failed')),
  created_at INTEGER NOT NULL, activated_at INTEGER
);
CREATE UNIQUE INDEX idx_one_active_generation ON index_generations(embedding_profile_id) WHERE state='active';
CREATE TABLE chunk_index_records (
  chunk_id TEXT NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
  generation_id TEXT NOT NULL REFERENCES index_generations(id),
  point_id TEXT NOT NULL, indexed_revision INTEGER NOT NULL CHECK(indexed_revision>0),
  state TEXT NOT NULL CHECK(state IN ('pending','ready','deleting','failed')),
  updated_at INTEGER NOT NULL,
  PRIMARY KEY(chunk_id,generation_id), UNIQUE(generation_id,point_id)
);
CREATE TABLE ingestion_jobs (
  id TEXT NOT NULL PRIMARY KEY, version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  dedupe_key TEXT NOT NULL UNIQUE,
  step TEXT NOT NULL CHECK(step IN ('extract','ocr','chunk','embed','activate','delete','reconcile')),
  state TEXT NOT NULL CHECK(state IN ('pending','running','done','failed','cancelled')),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts>=0),
  available_at INTEGER NOT NULL, lease_until INTEGER,
  progress_current INTEGER NOT NULL DEFAULT 0 CHECK(progress_current>=0), progress_total INTEGER CHECK(progress_total>=0),
  created_at INTEGER NOT NULL, completed_at INTEGER, last_error TEXT,
  CHECK(progress_total IS NULL OR progress_current<=progress_total)
);
CREATE INDEX idx_ingestion_pending ON ingestion_jobs(state,available_at);
CREATE TABLE document_events (
  id TEXT NOT NULL PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
  version_id TEXT REFERENCES document_versions(id), actor_user_id TEXT NOT NULL,
  event_type TEXT NOT NULL, occurred_at INTEGER NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(details_json))
);
CREATE TABLE evaluation_datasets (
  id TEXT NOT NULL PRIMARY KEY, name TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
  created_by TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE evaluation_cases (
  id TEXT NOT NULL PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES evaluation_datasets(id) ON DELETE CASCADE,
  tax_code TEXT NOT NULL REFERENCES tax_categories(code), question TEXT NOT NULL,
  expected_answer TEXT NOT NULL, expected_sources_json TEXT NOT NULL CHECK(json_valid(expected_sources_json))
);
CREATE TABLE evaluation_runs (
  id TEXT NOT NULL PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES evaluation_datasets(id),
  generation_id TEXT NOT NULL REFERENCES index_generations(id),
  dataset_revision INTEGER NOT NULL CHECK(dataset_revision>0),
  model_name TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('running','completed','failed','cancelled')),
  started_at INTEGER NOT NULL, completed_at INTEGER, triggered_by TEXT NOT NULL
);
CREATE TABLE evaluation_results (
  run_id TEXT NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
  case_id TEXT NOT NULL REFERENCES evaluation_cases(id),
  answer TEXT, source_ids_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(source_ids_json)),
  metrics_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metrics_json)),
  duration_ms INTEGER CHECK(duration_ms>=0), PRIMARY KEY(run_id,case_id)
);

CREATE TABLE corpus_state (
  singleton INTEGER NOT NULL PRIMARY KEY CHECK(singleton=1),
  epoch INTEGER NOT NULL CHECK(epoch>=0),
  active_generation_id TEXT REFERENCES index_generations(id),
  updated_at INTEGER NOT NULL
);
CREATE TABLE retrieval_requests (
  id TEXT NOT NULL PRIMARY KEY, requesting_user_id TEXT NOT NULL,
  tax_code TEXT NOT NULL REFERENCES tax_categories(code),
  generation_id TEXT REFERENCES index_generations(id),
  corpus_epoch INTEGER NOT NULL CHECK(corpus_epoch>=0),
  query_hash TEXT NOT NULL,
  requested_effective_date TEXT,
  state TEXT NOT NULL CHECK(state IN ('success','no_match','denied','failed')),
  duration_ms INTEGER CHECK(duration_ms>=0), created_at INTEGER NOT NULL
);
CREATE TABLE retrieval_evidence (
  request_id TEXT NOT NULL REFERENCES retrieval_requests(id) ON DELETE CASCADE,
  position INTEGER NOT NULL CHECK(position>=0),
  chunk_id TEXT NOT NULL REFERENCES document_chunks(id),
  chunk_revision INTEGER NOT NULL CHECK(chunk_revision>0), score REAL,
  PRIMARY KEY(request_id,position)
);

CREATE TABLE document_version_relations (
  source_version_id TEXT NOT NULL REFERENCES document_versions(id),
  target_version_id TEXT NOT NULL REFERENCES document_versions(id),
  relation_type TEXT NOT NULL CHECK(relation_type IN ('amends','repeals','implements','references')),
  effective_from TEXT, note TEXT, recorded_by TEXT NOT NULL, recorded_at INTEGER NOT NULL,
  PRIMARY KEY(source_version_id,target_version_id,relation_type),
  CHECK(source_version_id<>target_version_id)
);

CREATE TABLE archive_attributes(version_id TEXT PRIMARY KEY REFERENCES document_versions(id) ON DELETE CASCADE,
 metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),reviewed_by TEXT,reviewed_at TEXT,note TEXT);
CREATE TABLE legacy_imports(key TEXT PRIMARY KEY,completed_at INTEGER NOT NULL);
CREATE TABLE evaluation_snapshots(id TEXT PRIMARY KEY,position INTEGER NOT NULL,metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)));
CREATE TABLE evaluation_snapshot_items(snapshot_id TEXT NOT NULL REFERENCES evaluation_snapshots(id) ON DELETE CASCADE,
 position INTEGER NOT NULL,item_json TEXT NOT NULL CHECK(json_valid(item_json)),PRIMARY KEY(snapshot_id,position));
CREATE TABLE golden_items(id TEXT PRIMARY KEY,position INTEGER NOT NULL,item_json TEXT NOT NULL CHECK(json_valid(item_json)));
