"""Bounded Markdown intake. Source links are metadata, never fetched."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

PAGE = re.compile(r'<!--\s*page:\s*(\d+)\s*(?:\|[^>]*)?-->')
HEADER = re.compile(r'(?m)^---[ \t]*\n(?=url:)')

def parse_markdown(content, filename):
    if not content or len(content) > 20 * 1024 * 1024:
        raise ValueError('Markdown kosong atau melebihi 20 MB.')
    try:
        text = content.decode('utf-8-sig').replace('\r\n', '\n')
    except UnicodeDecodeError as exc:
        raise ValueError('Markdown harus menggunakan UTF-8.') from exc
    if '\x00' in text:
        raise ValueError('File mengandung karakter biner.')
    records = HEADER.split(text)
    if HEADER.search(text):
        if records[0].strip():
            raise ValueError('Teks di luar batas sumber paket belum didukung.')
        records = records[1:]
    if len(records) > 100:
        raise ValueError('Maksimal 100 sumber per paket.')
    result = []
    for index, record in enumerate(records):
        meta = {}
        body = record
        if record.startswith('url:'):
            split = re.split(r'(?m)^---[ \t]*$', record, maxsplit=1)
            if len(split) != 2:
                raise ValueError('Metadata sumber belum ditutup dengan --- .')
            header, body = split
            for key in ('url', 'title', 'content_hash', 'render_engine'):
                match = re.search(r'(?m)^' + key + r':\s*(.*?)\s*$', header)
                if match:
                    raw = match[1]
                    try:
                        value = json.loads(raw) if raw.startswith('"') else raw.strip("'")
                    except ValueError as exc:
                        raise ValueError('Metadata Markdown tidak valid.') from exc
                    if not isinstance(value, str) or len(value) > 2048:
                        raise ValueError('Metadata sumber terlalu panjang.')
                    meta[key] = value
            url = urlsplit(meta.get('url', ''))
            if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password:
                raise ValueError('URL sumber harus berupa HTTP/HTTPS tanpa kredensial.')
        title = meta.get('title') or next(iter(re.findall(r'(?m)^#\s+(.+)$', body)), Path(filename).stem)
        if not body.strip().strip('-').strip():
            raise ValueError(f'Sumber {index + 1} tidak memiliki isi.')
        segments = []
        page = None
        start = 0
        for match in PAGE.finditer(body):
            if body[start:match.start()].strip():
                segments.append((page, body[start:match.start()].strip()))
            page = int(match[1])
            if page < 1 or page > 100000:
                raise ValueError('Nomor halaman tidak valid.')
            start = match.end()
        if body[start:].strip():
            segments.append((page, body[start:].strip()))
        result.append({'title': title[:500], 'url': meta.get('url', ''),
                       'extraction_engine': meta.get('render_engine', ''),
                       'declared_hash': meta.get('content_hash', ''),
                       'digest': hashlib.sha256(record.encode()).hexdigest(),
                       'original': (('---\n' if record.startswith('url:') else '') + record).encode(), 'segments': segments})
    return result

def split_table(block, target=6000):
    """Split at complete rows, repeating each table's header and separator."""
    lines = block.splitlines()
    pending = []
    i = 0
    while i < len(lines):
        line = lines[i]
        is_row = bool(re.match(r'^\s*\|.*\|\s*$', line))
        if not is_row:
            pending.append(line)
            i += 1
            continue
        if pending:
            yield '\n'.join(pending)
            pending = []
        rows = []
        while i < len(lines) and re.match(r'^\s*\|.*\|\s*$', lines[i]):
            rows.append(lines[i])
            i += 1
        separator = lambda row: bool(re.fullmatch(r'\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?\s*', row))
        header = rows[:2] if len(rows) > 1 and separator(rows[1]) else []
        batch = list(header)
        size = sum(len(row) + 1 for row in batch)
        for row in rows[len(header):]:
            # Some exports concatenate tables without blank lines.
            if batch and len(batch) > len(header) and size + len(row) + 1 > target:
                yield '\n'.join(batch)
                batch = list(header)
                size = sum(len(value) + 1 for value in batch)
            batch.append(row)
            size += len(row) + 1
        if batch:
            yield '\n'.join(batch)
    if pending:
        yield '\n'.join(pending)


def markdown_chunks(record, splitter):
    """Keep physical pages and table rows; repeat headers in table chunks."""
    chunks = []
    for page, text in record['segments']:
        blocks = re.split(r'\n\s*\n', text)
        heading = ''
        for block in blocks:
            block = block.strip()
            if not block or block == '---':
                continue
            if re.match(r'^#{1,6}\s', block):
                heading = block.splitlines()[0]
            table = any(re.match(r'^\s*\|.*\|\s*$', line) for line in block.splitlines())
            for part in (split_table(block) if table else splitter.split_text(block)):
                if part.strip():
                    chunks.append((page, heading, part))
    if not chunks:
        raise ValueError('Tidak ada teks sumber yang dapat diindeks.')
    return chunks


class ImportProgress:
    """Process-local operational counters; never expose document contents or identity."""
    def __init__(self):
        import threading
        self.lock = threading.Lock()
        self.state = {'phase': 'idle', 'total': 0, 'completed': 0, 'failed': 0, 'skipped': 0}

    def update(self, **values):
        import time
        with self.lock:
            self.state = {**self.state, **values, 'updated_at': time.time()}

    def snapshot(self):
        with self.lock:
            return dict(self.state)


import_progress = ImportProgress()
