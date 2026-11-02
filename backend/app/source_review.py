"""Private archive with automatic technical activation for authorized uploads."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import uuid


class SourceArchive:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, metadata TEXT NOT NULL,
                payload TEXT NOT NULL, reviewed_by TEXT, reviewed_at TEXT, note TEXT)''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / 'sources.sqlite', timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def stage(self, documents, metadatas, original, filename, warnings=None):
        source_id = uuid.uuid4().hex
        suffix = Path(filename).suffix.lower() if original is not None else '.json'
        content = original if original is not None else json.dumps(documents, ensure_ascii=False).encode()
        # The stored basename is generated, never derived from an uploaded path.
        stored_name = source_id + suffix
        path = self.root / stored_name
        path.write_bytes(content)
        metas = [{**m, 'document_id': source_id, 'content_sha256': hashlib.sha256(content).hexdigest()}
                 for m in metadatas]
        metadata = {**metas[0], 'id': source_id, 'status': 'pending', 'chunk_count': len(documents),
                    'stored_name': stored_name, 'warnings': warnings or [], 'has_file': original is not None}
        payload = {'ids': [f'{source_id}-{i:05d}' for i in range(len(documents))],
                   'documents': documents, 'metadatas': metas}
        try:
            with self.connect() as db:
                db.execute('INSERT INTO sources(id,status,metadata,payload) VALUES(?,?,?,?)',
                           (source_id, 'pending', json.dumps(metadata), json.dumps(payload)))
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return source_id

    def list(self):
        with self.connect() as db:
            rows = db.execute('SELECT id,status,metadata,reviewed_by,reviewed_at,note FROM sources ORDER BY rowid DESC').fetchall()
        return [{**{k: v for k, v in json.loads(r['metadata']).items() if k != 'stored_name'},
                 'status': r['status'], 'reviewed_at': r['reviewed_at'], 'note': r['note']} for r in rows]

    def get(self, source_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone()
        if row is None:
            raise KeyError(source_id)
        return row

    def detail(self, source_id):
        row = self.get(source_id)
        meta = json.loads(row['metadata'])
        meta.pop('stored_name', None)
        payload = json.loads(row['payload'])
        return {**meta, 'status': row['status'], 'note': row['note'], 'chunks': [
            {'text': text, 'page': m.get('page_number'), 'sheet': m.get('sheet_name'), 'row': m.get('row_index')}
            for text, m in zip(payload['documents'], payload['metadatas'])]}

    def file(self, source_id):
        meta = json.loads(self.get(source_id)['metadata'])
        if not meta['has_file']:
            raise KeyError(source_id)
        path = (self.root / meta['stored_name']).resolve()
        if path.parent != self.root.resolve() or not path.is_file():
            raise KeyError(source_id)
        return path, meta['doc_name']

    def activate(self, source_id, uploader, collection, embedder):
        """Trusted developer uploads activate after technical checks; no human approval."""
        with self.lock:
            row = self.get(source_id)
            if row['status'] not in {'pending', 'failed'}:
                raise ValueError('Sumber sudah aktif atau tidak dapat diproses ulang.')
            metadata = json.loads(row['metadata'])
            metadata.setdefault('uploaded_by', uploader)
            metadata['activation_mode'] = 'automatic'
            with self.connect() as db:
                db.execute('UPDATE sources SET metadata=? WHERE id=?', (json.dumps(metadata), source_id))
            try:
                if metadata.get('warnings'):
                    raise ValueError('Ada halaman tanpa teks. Gunakan PDF dengan teks lengkap; OCR belum tersedia.')
                return self.review(source_id, 'approve', uploader,
                    'Aktif otomatis setelah pemeriksaan teknis.', collection, embedder)
            except Exception:
                with self.connect() as db:
                    db.execute("UPDATE sources SET status='failed', note=? WHERE id=?",
                        ('Pemrosesan belum selesai. Periksa peringatan atau coba proses ulang.', source_id))
                raise

    def review(self, source_id, action, reviewer, note, collection, embedder):
        if action not in {"approve", "reject"}:
            raise ValueError("Keputusan pemeriksaan tidak valid.")
        if action == "reject" and not note.strip():
            raise ValueError("Isi alasan penolakan sumber.")
        with self.lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone()
            if row is None:
                raise KeyError(source_id)
            if row['status'] not in {'pending', 'failed'}:
                raise ValueError('Sumber ini sudah diperiksa. Muat ulang daftar.')
            payload = json.loads(row['payload'])
            if action == 'approve':
                try:
                    for start in range(0, len(payload['ids']), 100):
                        texts = payload['documents'][start:start+100]
                        collection.upsert(ids=payload['ids'][start:start+100], documents=texts,
                                          metadatas=payload['metadatas'][start:start+100],
                                          embeddings=embedder.embed_texts(texts))
                    db.execute('UPDATE sources SET status=?,reviewed_by=?,reviewed_at=?,note=? WHERE id=?',
                               ('approved', reviewer, datetime.now(timezone.utc).isoformat(), note, source_id))
                    db.commit()
                except Exception:
                    collection.delete(ids=payload['ids'])
                    raise
            else:
                db.execute('UPDATE sources SET status=?,reviewed_by=?,reviewed_at=?,note=? WHERE id=?',
                           ('rejected', reviewer, datetime.now(timezone.utc).isoformat(), note, source_id))
        return self.detail(source_id)
