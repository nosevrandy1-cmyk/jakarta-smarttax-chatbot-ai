"""Document catalog, original-file registry, pages and tax-scoped chunks."""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
import mimetypes
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from .db_core import backup, connect, initialize

STATUS = {'pending':'staged','approved':'active','rejected':'rejected','failed':'failed'}
API_STATUS = {v:k for k,v in STATUS.items()}
TAX_CODES = {'PBB-P2','PBJT','BPHTB','REKLAME','PAT'}


class SourceArchive:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'knowledge.sqlite'
        self.lock = threading.RLock()
        initialize(self.path, 'knowledge')
        self._migrate()

    def connect(self):
        return connect(self.path)

    def _migrate(self):
        legacy = self.root / 'sources.sqlite'
        if not legacy.is_file():
            return
        with self.connect() as db:
            if db.execute("SELECT 1 FROM legacy_imports WHERE key='sources-v1'").fetchone():
                return
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup(legacy, self.root / '.migration-backups' / stamp / 'sources-before.sqlite')
        with closing(sqlite3.connect(legacy)) as old:
            old.row_factory = sqlite3.Row
            rows = [dict(r) for r in old.execute('SELECT * FROM sources ORDER BY rowid')]
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for row in rows:
                self._insert(db, row['id'], json.loads(row['metadata']), json.loads(row['payload']), row)
            db.execute('INSERT INTO legacy_imports VALUES(?,?)', ('sources-v1', int(time.time()*1000)))
            for row in rows:
                result = self._get(db, row['id'])
                if json.loads(result['payload']) != json.loads(row['payload']) or json.loads(result['metadata']) != json.loads(row['metadata']):
                    raise RuntimeError('Document migration mismatch; original retained')

    def _insert(self, db, source_id, meta, payload, review=None):
        review = review or {}
        now = int(time.time()*1000)
        state = STATUS[review.get('status', 'pending')]
        actor = str(meta.get('uploaded_by') or meta.get('contributor') or 'legacy-import')
        source_type = meta.get('source_type', '')
        kind = 'regulation' if source_type == 'pdf_regulasi' else 'case' if 'kasus' in source_type else 'table' if 'excel' in source_type else 'other'
        db.execute('''INSERT INTO documents(id,title,document_type,access_scope,lifecycle,created_by,created_at,updated_at)
            VALUES(?,?,?,'authenticated',?,?,?,?)''', (source_id, meta.get('doc_name', 'Dokumen'), kind, 'published' if state == 'active' else 'draft', actor, now, now))
        db.execute('''INSERT INTO document_versions(id,document_id,version_label,state,created_by,created_at,extraction_quality)
            VALUES(?,?,'1',?,?,?,?)''', (source_id, source_id, state, actor, now, 'needs_attention' if meta.get('warnings') else 'passed'))
        db.execute('INSERT INTO archive_attributes VALUES(?,?,?,?,?)', (source_id,json.dumps(meta,ensure_ascii=False),review.get('reviewed_by'),review.get('reviewed_at'),review.get('note')))
        key = meta['stored_name']
        path = (self.root / key).resolve()
        if path.parent != self.root.resolve():
            raise ValueError('Invalid archived path')
        content = path.read_bytes() if path.is_file() else b''
        digest = meta.get('content_sha256') or hashlib.sha256(content).hexdigest()
        db.execute('INSERT INTO files(id,storage_key,original_name,mime_type,sha256,size_bytes,state,created_at) VALUES(?,?,?,?,?,?,?,?)',
            (source_id,key,meta.get('doc_name','Dokumen'),mimetypes.guess_type(key)[0] or 'application/octet-stream',digest,len(content),'available' if path.is_file() else 'staged',now))
        db.execute('INSERT INTO document_version_files VALUES(?,?,?)', (source_id, source_id, 'original' if meta.get('has_file') else 'extracted'))
        pages = {}
        for index, (chunk_id,text,m) in enumerate(zip(payload['ids'], payload['documents'], payload['metadatas']), 1):
            code = str(m.get('tema_pajak') or m.get('domain') or '').upper()
            code = 'PBB-P2' if code == 'JPB' else code
            if code not in TAX_CODES:
                raise ValueError('Kategori pajak sumber tidak valid.')
            db.execute('INSERT OR IGNORE INTO version_tax_categories VALUES(?,?,?)',(source_id,code,actor))
            page = m.get('page_number')
            if page is not None:
                page = int(page)
                pages.setdefault(page,[]).append(text)
            row = m.get('row_index')
            db.execute('''INSERT INTO document_chunks(id,version_id,sequence_no,text,content_sha256,physical_page_start,physical_page_end,
                sheet_name,row_start,row_end,locator_json,state) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                (chunk_id,source_id,index,text,hashlib.sha256(text.encode()).hexdigest(),page,page,m.get('sheet_name'),row,row,json.dumps(m,ensure_ascii=False),'ready' if state == 'active' else 'pending'))
            db.execute('INSERT INTO chunk_tax_categories VALUES(?,?,?)',(source_id,chunk_id,code))
        for page,texts in pages.items():
            db.execute("INSERT INTO document_pages VALUES(?,?,NULL,?,'text','passed')",(source_id,page,'\n\n'.join(texts)))

    def stage(self, documents, metadatas, original, filename, warnings=None):
        if not documents or len(documents) != len(metadatas) or any(not t.strip() for t in documents):
            raise ValueError('Potongan sumber kosong atau tidak konsisten.')
        source_id = uuid.uuid4().hex
        suffix = Path(filename).suffix.lower() if original is not None else '.json'
        content = original if original is not None else json.dumps(documents,ensure_ascii=False).encode()
        stored_name = source_id + suffix
        path = self.root / stored_name
        path.write_bytes(content)
        metas = [{**m,'document_id':source_id,'content_sha256':hashlib.sha256(content).hexdigest()} for m in metadatas]
        meta = {**metas[0],'id':source_id,'status':'pending','chunk_count':len(documents),'stored_name':stored_name,'warnings':warnings or [],'has_file':original is not None}
        payload = {'ids':[f'{source_id}-{i:05d}' for i in range(len(documents))],'documents':documents,'metadatas':metas}
        try:
            with self.lock,self.connect() as db:
                self._insert(db,source_id,meta,payload)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return source_id

    def _get(self, db, source_id):
        row = db.execute('''SELECT a.*,v.state FROM archive_attributes a JOIN document_versions v ON v.id=a.version_id
            JOIN documents d ON d.id=v.document_id WHERE v.id=? AND d.deleted_at IS NULL AND v.deleted_at IS NULL''',(source_id,)).fetchone()
        if row is None:
            raise KeyError(source_id)
        chunks = list(db.execute('SELECT id,text,locator_json FROM document_chunks WHERE version_id=? ORDER BY sequence_no',(source_id,)))
        payload = {'ids':[r['id'] for r in chunks],'documents':[r['text'] for r in chunks],'metadatas':[json.loads(r['locator_json']) for r in chunks]}
        return {'id':source_id,'status':API_STATUS.get(row['state'],'pending'),'metadata':row['metadata_json'],'payload':json.dumps(payload,ensure_ascii=False),
                'reviewed_by':row['reviewed_by'],'reviewed_at':row['reviewed_at'],'note':row['note']}

    def get(self, source_id):
        with self.connect() as db:
            return self._get(db,source_id)

    def export(self):
        with self.connect() as db:
            ids = [r[0] for r in db.execute('SELECT version_id FROM archive_attributes ORDER BY rowid')]
            return [self._get(db,i) for i in ids]

    def list(self):
        with self.connect() as db:
            rows = db.execute('''SELECT a.*,v.state FROM archive_attributes a JOIN document_versions v ON v.id=a.version_id
                JOIN documents d ON d.id=v.document_id WHERE d.deleted_at IS NULL AND v.deleted_at IS NULL ORDER BY a.rowid DESC''').fetchall()
        return [{**{k:v for k,v in json.loads(r['metadata_json']).items() if k!='stored_name'},
                 'status':API_STATUS.get(r['state'],'pending'),'reviewed_at':r['reviewed_at'],'note':r['note']} for r in rows]

    def detail(self, source_id):
        row = self.get(source_id)
        meta = json.loads(row['metadata']);meta.pop('stored_name',None)
        payload = json.loads(row['payload'])
        return {**meta,'status':row['status'],'note':row['note'],'chunks':[
            {'text':text,'page':m.get('page_number'),'sheet':m.get('sheet_name'),'row':m.get('row_index')}
            for text,m in zip(payload['documents'],payload['metadatas'])]}

    def file(self, source_id):
        meta = json.loads(self.get(source_id)['metadata'])
        path = (self.root / meta['stored_name']).resolve()
        if not meta['has_file'] or path.parent != self.root.resolve() or not path.is_file():
            raise KeyError(source_id)
        return path, meta['doc_name']

    def activate(self, source_id, uploader, collection, embedder):
        with self.lock:
            row = self.get(source_id)
            if row['status'] not in {'pending','failed'}:
                raise ValueError('Sumber sudah aktif atau tidak dapat diproses ulang.')
            meta = json.loads(row['metadata'])
            meta.setdefault('uploaded_by',uploader);meta['activation_mode']='automatic'
            with self.connect() as db:
                db.execute('UPDATE archive_attributes SET metadata_json=? WHERE version_id=?',(json.dumps(meta),source_id))
            try:
                if meta.get('warnings'):
                    raise ValueError('Ada halaman tanpa teks. Gunakan PDF dengan teks lengkap; OCR belum tersedia.')
                return self.review(source_id,'approve',uploader,'Aktif otomatis setelah pemeriksaan teknis.',collection,embedder)
            except Exception:
                with self.connect() as db:
                    db.execute("UPDATE document_versions SET state='failed' WHERE id=?",(source_id,))
                raise

    def review(self, source_id, action, reviewer, note, collection, embedder):
        if action not in {'approve','reject'} or action=='reject' and not note.strip():
            raise ValueError('Keputusan atau alasan pemeriksaan tidak valid.')
        with self.lock:
            row = self.get(source_id)
            if row['status'] not in {'pending','failed'}:
                raise ValueError('Sumber ini sudah diperiksa. Muat ulang daftar.')
            payload = json.loads(row['payload'])
            # Never hold a SQLite write transaction while embedding or calling Qdrant.
            if action == 'approve':
                try:
                    for start in range(0,len(payload['ids']),100):
                        texts=payload['documents'][start:start+100]
                        collection.upsert(ids=payload['ids'][start:start+100],documents=texts,
                            metadatas=payload['metadatas'][start:start+100],embeddings=embedder.embed_texts(texts))
                    with self.connect() as db:
                        self._activate_index(db,source_id,collection)
                        db.execute("UPDATE document_versions SET state='active',activated_at=? WHERE id=?",(int(time.time()*1000),source_id))
                        db.execute("UPDATE documents SET lifecycle='published' WHERE id=?",(source_id,))
                        db.execute("UPDATE document_chunks SET state='ready' WHERE version_id=?",(source_id,))
                        self._review_record(db,source_id,reviewer,note,action)
                except Exception:
                    collection.delete(ids=payload['ids'])
                    raise
            else:
                with self.connect() as db:
                    db.execute("UPDATE document_versions SET state='rejected' WHERE id=?",(source_id,))
                    self._review_record(db,source_id,reviewer,note,action)
        return self.detail(source_id)

    @staticmethod
    def _review_record(db,source,actor,note,action):
        now = int(time.time()*1000)
        db.execute('UPDATE archive_attributes SET reviewed_by=?,reviewed_at=?,note=? WHERE version_id=?',(actor,datetime.now(timezone.utc).isoformat(),note,source))
        db.execute('INSERT INTO document_events VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,source,source,actor,action,now,'{}'))

    @staticmethod
    def _activate_index(db,source,collection):
        now = int(time.time()*1000)
        dimension = getattr(collection,'dimension',384)
        name = getattr(collection,'name','jakarta_smarttax_knowledge')
        profile = f'jst-hashing-{dimension}'
        generation = str(uuid.uuid5(uuid.NAMESPACE_URL,'jst:'+name+':'+profile))
        db.execute('INSERT OR IGNORE INTO embedding_profiles VALUES(?,?,?,?,?,?,?,?)',(profile,'jst-hashing','1',dimension,'cosine','l2','{}',now))
        db.execute('INSERT OR IGNORE INTO index_generations VALUES(?,?,?,?,?,?)',(generation,profile,name,'active',now,now))
        for r in db.execute('SELECT id,revision FROM document_chunks WHERE version_id=?',(source,)):
            point = collection.point_id(r['id']) if hasattr(collection,'point_id') else r['id']
            db.execute('INSERT OR REPLACE INTO chunk_index_records VALUES(?,?,?,?,?,?)',(r['id'],generation,point,r['revision'],'ready',now))
        db.execute('INSERT INTO corpus_state VALUES(1,1,?,?) ON CONFLICT(singleton) DO UPDATE SET epoch=epoch+1,active_generation_id=excluded.active_generation_id,updated_at=excluded.updated_at',(generation,now))

    def clear(self):
        with self.connect() as db:
            for table in ['retrieval_requests','document_events','document_version_relations','documents','files']:
                db.execute(f'DELETE FROM {table}')
            db.execute('UPDATE corpus_state SET epoch=epoch+1')

    def valid_hits(self, ids, tax_code=None):
        """Recheck the catalog after vector search; orphan/stale points are denied."""
        return set(self.validated_records(ids, tax_code))

    def validated_records(self, ids, tax_code=None):
        with self.connect() as db:
            result = {}
            for chunk in ids:
                row = db.execute('''SELECT c.text,c.locator_json FROM document_chunks c JOIN document_versions v ON v.id=c.version_id
                    JOIN documents d ON d.id=v.document_id JOIN chunk_tax_categories t ON t.chunk_id=c.id
                    WHERE c.id=? AND c.state='ready' AND v.state='active' AND d.lifecycle='published'
                    AND d.access_scope IN ('public','authenticated')
                    AND d.deleted_at IS NULL AND v.deleted_at IS NULL AND (? IS NULL OR t.tax_code=?)''',(chunk,tax_code,tax_code)).fetchone()
                if row:
                    result[chunk] = {'text':row['text'],'metadata':json.loads(row['locator_json'])}
            return result
