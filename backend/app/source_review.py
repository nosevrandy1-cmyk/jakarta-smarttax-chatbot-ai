"""Document catalog, original-file registry, pages and tax-scoped chunks."""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
import mimetypes
import re
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from .db_core import backup, connect, initialize
from .retrieval_text import document_matches, passage_score, passage_body, document_title_pattern, lexical_expansions, legal_queries

STATUS = {'pending':'staged','approved':'active','rejected':'rejected','failed':'failed'}
API_STATUS = {v:k for k,v in STATUS.items()}
TAX_CODES = {'PBB-P2','PBJT','BPHTB','REKLAME','PAT'}


def text_query_scope(query):
    text=query.casefold()
    years=re.findall(r'\btahun\s+(\d{4})\b',text)
    codes=re.findall(r'\bkode\s+(\d{3})\b',text)
    street=re.search(r'\b(?:jalan|jl\.?)\s+(.+?)(?=\s+(?:tahun|kode|kelas|berapa|yang|termasuk)\b|[?!.]|$)',text)
    classes=re.findall(r'\bkelas\s+([a-z]{1,3})(?:\s+dan\s+([a-z]{1,3}))?\b',text)
    return {'year':years[-1] if years else None,'code':codes[-1] if codes else None,
        'street':street[1].strip()[:80] if street else None,
        'classes':[c for c in classes[-1] if c] if classes else []}


class SourceArchive:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'knowledge.sqlite'
        self.lock = threading.RLock()
        initialize(self.path, 'knowledge')
        self._migrate()
        self._ensure_text_search()

    def _ensure_text_search(self):
        """Add a local text index without changing existing document IDs or vectors."""
        with self.connect() as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='document_chunks_fts'").fetchone()
            db.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(text, content='document_chunks', content_rowid='rowid', tokenize='unicode61');
                CREATE TRIGGER IF NOT EXISTS document_chunks_search_insert AFTER INSERT ON document_chunks BEGIN
                    INSERT INTO document_chunks_fts(rowid,text) VALUES(new.rowid,new.text); END;
                CREATE TRIGGER IF NOT EXISTS document_chunks_search_delete AFTER DELETE ON document_chunks BEGIN
                    INSERT INTO document_chunks_fts(document_chunks_fts,rowid,text) VALUES('delete',old.rowid,old.text); END;
                CREATE TRIGGER IF NOT EXISTS document_chunks_search_update AFTER UPDATE OF text ON document_chunks BEGIN
                    INSERT INTO document_chunks_fts(document_chunks_fts,rowid,text) VALUES('delete',old.rowid,old.text);
                    INSERT INTO document_chunks_fts(rowid,text) VALUES(new.rowid,new.text); END;
            """)
            if not exists:
                db.execute("INSERT INTO document_chunks_fts(document_chunks_fts) VALUES('rebuild')")

    def search_text(self, query, tax_code=None, source_type=None, limit=24):
        import re
        ignored = {'apa','yang','di','dan','atau','untuk','dari','dalam','ada','saja','aja','sebutkan','jelaskan','tolong','bagaimana','tentang','berapa','saya','aku','minta'}
        terms = list(dict.fromkeys(t for t in re.findall(r'[^\W_]+', query.casefold()) if len(t)>1 and t not in ignored))[:24]
        if not terms:
            return []
        expression = '(' + ' OR '.join('"'+term+'"' for term in terms) + ')'
        # Expand lexical vocabulary only; no model call or factual answer is injected.
        additions = lexical_expansions(query)
        if additions:
            expression = '(' + expression + ' OR ' + ' OR '.join(chr(34)+term+chr(34) for term in additions) + ')'
        scope=text_query_scope(query)
        for key in ('code','street'):
            if scope[key]:expression += ' AND "'+scope[key].replace('"','')+'"'
        if scope['classes']:
            expression += ' AND ('+' OR '.join('"'+c+'"' for c in scope['classes'])+')'
        with self.connect() as db:
            rows = db.execute("""SELECT c.id,c.text,d.title FROM document_chunks_fts
                JOIN document_chunks c ON c.rowid=document_chunks_fts.rowid
                JOIN document_versions v ON v.id=c.version_id JOIN documents d ON d.id=v.document_id
                JOIN archive_attributes a ON a.version_id=v.id
                WHERE document_chunks_fts MATCH ? AND c.state='ready' AND v.state='active'
                AND d.lifecycle='published' AND d.deleted_at IS NULL AND v.deleted_at IS NULL
                AND d.access_scope IN ('public','authenticated')
                AND (? IS NULL OR EXISTS(SELECT 1 FROM chunk_tax_categories t WHERE t.chunk_id=c.id AND t.tax_code=?))
                AND (? IS NULL OR json_extract(a.metadata_json,'$.source_type')=?)
                AND (? IS NULL OR instr(d.title,?)>0)
                AND (? IS NULL OR lower(d.title) LIKE ?)
                ORDER BY bm25(document_chunks_fts),c.id LIMIT ?""",
                (expression,tax_code,tax_code,source_type,source_type,scope['year'],scope['year'],document_title_pattern(query),document_title_pattern(query),240)).fetchall()
        ranked = [(passage_score(query, row['text'], row['title']), index, row['id'])
                  for index, row in enumerate(rows) if document_matches(query, row['title'])]
        ranked = [row for row in ranked if row[0] >= 0]
        ranked.sort(key=lambda row: (-row[0], row[1]))
        return [row[2] for row in ranked[:max(1, min(limit, 40))]]

    def page_context(self, chunk_id):
        """Recover column labels and location headings from the same physical page."""
        with self.connect() as db:
            row=db.execute("""SELECT first.text FROM document_chunks seed
                JOIN document_chunks first ON first.version_id=seed.version_id
                AND first.physical_page_start=seed.physical_page_start
                WHERE seed.id=? ORDER BY first.sequence_no LIMIT 1""",(chunk_id,)).fetchone()
        if not row:return ''
        text=row['text']
        if not all(word in text.casefold() for word in ('penggolongan','nilai jual')):return ''
        header=re.split(r'(?m)^\d{3}\s+(?:JL|GG|KP)\b',text,maxsplit=1)[0]
        return header[:1200]

    def legal_context(self, chunk_id, tax_code=None):
        """Expand one article and its explicit cross-references within the same version.

        All IDs are revalidated against active state, tax scope and access controls.
        One hop, 12 chunks and 9000 characters bound the work and context size.
        """
        with self.connect() as db:
            seed = db.execute('SELECT version_id,text,locator_json FROM document_chunks WHERE id=?', (chunk_id,)).fetchone()
            if not seed:
                return {}
            section = json.loads(seed['locator_json']).get('section', '')
            match = re.fullmatch(r'#{0,6}\s*Pasal\s+(\d+[A-Za-z]?)\s*', section, re.I)
            if not match:
                match = re.search(r'(?m)^#{1,6}\s+Pasal\s+(\d+[A-Za-z]?)\s*$', seed['text'], re.I)
            if not match:
                return {}
            article = match[1].casefold()
            candidates = db.execute('SELECT id,text,locator_json FROM document_chunks WHERE version_id=? ORDER BY sequence_no LIMIT 1200', (seed['version_id'],)).fetchall()
        def article_of(row):
            section = json.loads(row['locator_json']).get('section', '')
            m = re.fullmatch(r'#{0,6}\s*Pasal\s+(\d+[A-Za-z]?)\s*', section, re.I)
            if not m:
                m = re.search(r'(?m)^#{1,6}\s+Pasal\s+(\d+[A-Za-z]?)\s*$', row['text'], re.I)
            return m[1].casefold() if m else None
        own = [row for row in candidates if article_of(row) == article]
        cited = set(re.findall(r'\bPasal\s+(\d+[A-Za-z]?)', '\n'.join(row['text'] for row in own), re.I))
        cited = {item.casefold() for item in cited} - {article}
        related = [row for row in candidates if article_of(row) in cited]
        ids, size = [], 0
        for row in own + related:
            if row['id'] == chunk_id or not re.search(r'[^\W\d_]{2,}', passage_body(row['text'])):
                continue
            if len(ids) >= 12 or size + len(row['text']) > 9000:
                break
            ids.append(row['id']); size += len(row['text'])
        return self.validated_records(ids, tax_code)

    def following_chunks(self, chunk_id, tax_code=None):
        with self.connect() as db:
            seed=db.execute('SELECT version_id,sequence_no FROM document_chunks WHERE id=?',(chunk_id,)).fetchone()
            if not seed:return {}
            ids=[row[0] for row in db.execute('SELECT id FROM document_chunks WHERE version_id=? AND sequence_no>? AND sequence_no<=? ORDER BY sequence_no',
                (seed['version_id'],seed['sequence_no'],seed['sequence_no']+2))]
        return self.validated_records(ids,tax_code)

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

    @staticmethod
    def _summary(row):
        meta = json.loads(row['metadata_json'])
        allowed = ('doc_name','domain','source_type','source_format','chunk_count','page_count','has_file','ingested_at')
        return {**{key:meta[key] for key in allowed if key in meta},
                'id':row['version_id'],'status':API_STATUS.get(row['state'],'pending')}

    def browse(self, offset=0, limit=20, query='', domain=''):
        if offset < 0 or not 1 <= limit <= 50 or len(query)>120:
            raise ValueError('Batas pencarian tidak valid.')
        where = "d.deleted_at IS NULL AND v.deleted_at IS NULL"
        params=[]
        if query:
            where += " AND instr(lower(d.title),lower(?))>0"
            params.append(query)
        if domain:
            where += " AND EXISTS(SELECT 1 FROM version_tax_categories t WHERE t.version_id=v.id AND t.tax_code=?)"
            params.append(domain)
        join = " FROM archive_attributes a JOIN document_versions v ON v.id=a.version_id JOIN documents d ON d.id=v.document_id WHERE " + where
        with self.connect() as db:
            total=db.execute('SELECT count(*)'+join,params).fetchone()[0]
            rows=db.execute('SELECT a.version_id,a.metadata_json,v.state'+join+' ORDER BY a.rowid DESC LIMIT ? OFFSET ?',[*params,limit,offset]).fetchall()
        return {'items':[self._summary(row) for row in rows],'total':total,'offset':offset,'limit':limit}

    def browse_detail(self, source_id, offset=0, limit=10):
        if offset < 0 or not 1 <= limit <= 20:
            raise ValueError('Batas halaman tidak valid.')
        with self.connect() as db:
            row=db.execute('SELECT a.version_id,a.metadata_json,v.state FROM archive_attributes a JOIN document_versions v ON v.id=a.version_id JOIN documents d ON d.id=v.document_id WHERE v.id=? AND d.deleted_at IS NULL AND v.deleted_at IS NULL',(source_id,)).fetchone()
            if row is None:raise KeyError(source_id)
            rows=db.execute('SELECT id,sequence_no,physical_page_start,sheet_name,row_start FROM document_chunks WHERE version_id=? AND state!=? ORDER BY sequence_no LIMIT ? OFFSET ?',(source_id,'deleted',limit,offset)).fetchall()
            total=db.execute("SELECT count(*) FROM document_chunks WHERE version_id=? AND state!='deleted'",(source_id,)).fetchone()[0]
        return {**self._summary(row),'chunks':[{'id':r['id'],'number':r['sequence_no'],'page':r['physical_page_start'],'sheet':r['sheet_name'],'row':r['row_start']} for r in rows],
                'total':total,'offset':offset,'limit':limit}

    def read_chunk(self, source_id, chunk_id):
        with self.connect() as db:
            row=db.execute("SELECT c.text FROM document_chunks c JOIN document_versions v ON v.id=c.version_id JOIN documents d ON d.id=v.document_id WHERE c.version_id=? AND c.id=? AND c.state!='deleted' AND v.deleted_at IS NULL AND d.deleted_at IS NULL",(source_id,chunk_id)).fetchone()
        if row is None:raise KeyError(chunk_id)
        return {'id':chunk_id,'text':row['text']}

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
