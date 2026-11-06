import json
from datetime import datetime, timezone
import hashlib
import io
from pathlib import Path
from typing import Any, Dict, List, Optional

from .vector_store import QdrantRecords
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pandas as pd
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from .config import (
    QDRANT_KNOWLEDGE_COLLECTION,
    QDRANT_STORAGE_DIR,
    QDRANT_URL,
    VECTOR_DIM,
    TAX_DOMAINS,
    UPLOAD_STAGING_DIR,
)
from .embedder import embedder
from .source_review import SourceArchive, text_query_scope
from .retrieval_text import passage_score, document_matches, legal_queries, normalize_legal_query, normalized_terms
from .tax_db import TAX_THEMES


class LearnReasoningPayload(BaseModel):
    pertanyaan_kasus: str = Field(..., min_length=10, max_length=2000)
    alur_penalaran: str = Field(..., min_length=15, max_length=6000)
    jawaban_final: str = Field(..., min_length=10, max_length=4000)
    topik_pajak: str = Field(..., min_length=2, max_length=60)
    kontributor: str = Field(..., min_length=2, max_length=120)


class RetrievalResult(BaseModel):
    chunk_id: str
    text: str
    similarity: float
    cosine_distance: float
    source_type: str
    doc_name: str
    domain: str
    contributor: str
    ingested_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


def normalize_domain(raw_topic: str) -> str:
    cleaned = (raw_topic or "").strip().upper()
    if cleaned in TAX_DOMAINS:
        return cleaned
    mapping = {
        "PBB": "PBB-P2",
        "GEDUNG": "JPB",
        "PERKANTORAN": "JPB",
        "KOMERSIAL": "JPB",
        "RESTORAN": "PBJT",
        "HOTEL": "PBJT",
        "HIBURAN": "PBJT",
        "PARKIR": "PBJT",
        "WARIS": "BPHTB",
        "AJB": "BPHTB",
        "VIDEOTRON": "REKLAME",
        "BILLBOARD": "REKLAME",
        "AIR TANAH": "PAT",
        "NPAT": "PAT",
    }
    for key, val in mapping.items():
        if key in cleaned:
            return val
    return "PBB-P2"


def domain_to_theme(domain: str) -> str:
    dom = normalize_domain(domain)
    if dom == "JPB":
        return "PBB-P2"
    return dom if dom in TAX_THEMES else "PBB-P2"


def serialize_row(category: str, row_idx: int, row_dict: Dict[str, Any]) -> str:
    pairs: List[str] = []
    for col, val in row_dict.items():
        if pd.isna(val):
            continue
        col_clean = str(col).strip()
        val_clean = str(val).strip()
        if col_clean and val_clean:
            pairs.append(f"{col_clean}: {val_clean}")
    joined_pairs = " | ".join(pairs)
    return f"[DATA TABEL: {category} - Baris {row_idx}] {joined_pairs}"


def format_reasoning_block(payload: LearnReasoningPayload) -> str:
    return (
        f"[REFERENSI PENALARAN KASUS PAJAK - Topik: {payload.topik_pajak}]\n"
        f"Kasus / Pertanyaan: {payload.pertanyaan_kasus.strip()}\n"
        f"Alur Penalaran & Dasar Hukum: {payload.alur_penalaran.strip()}\n"
        f"Kesimpulan / Jawaban kasus: {payload.jawaban_final.strip()}"
    )


class SmartTaxKnowledgeStore:
    def __init__(self) -> None:
        QDRANT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_STAGING_DIR.mkdir(parents=True, exist_ok=True)
        self.archive = SourceArchive(UPLOAD_STAGING_DIR)
        self.collection_name = QDRANT_KNOWLEDGE_COLLECTION
        self.collection = QdrantRecords(QDRANT_STORAGE_DIR, QDRANT_URL, self.collection_name, VECTOR_DIM)
        self.client = self.collection.client
        self.mode = "qdrant-server" if QDRANT_URL else "qdrant-local-disk"
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n## ", "\n### ", "\nPasal ", "\n\n", "\n", " "],
        )
        self.last_ingested_source: Optional[Dict[str, Any]] = None

    def ingest_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        domain: str = "PBB-P2",
        contributor: str = "Tim Regulasi Bapenda",
    ) -> Dict[str, Any]:
        if not file_bytes:
            raise ValueError("File PDF kosong atau tidak valid.")

        clean_name = Path(filename).name
        dom = normalize_domain(domain)
        tema = domain_to_theme(dom)

        # Pure Python parsing avoids unsigned native PDF DLLs on Windows.
        # Extract in memory, then archive the original under an application-generated basename.
        try:
            with io.BytesIO(file_bytes) as stream:
                reader = PdfReader(stream)
                if reader.is_encrypted:
                    raise ValueError("PDF terenkripsi belum didukung. Unggah salinan tanpa password.")
                page_texts = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
        except (PyPdfError, OSError) as exc:
            raise ValueError("File PDF rusak atau tidak dapat dibaca.") from exc
        raw_chunks = []
        chunk_pages = []
        warnings = []
        for page_number, text in enumerate(page_texts, start=1):
            if not text.strip():
                warnings.append(f"Halaman {page_number} tidak memiliki teks; periksa apakah perlu OCR.")
                continue
            page_chunks = self.splitter.split_text(text.strip())
            raw_chunks.extend(page_chunks)
            chunk_pages.extend([page_number] * len(page_chunks))
        if not raw_chunks:
            raise ValueError("Tidak ditemukan teks yang dapat diekstrak. OCR belum tersedia.")
        now_iso = datetime.now(timezone.utc).isoformat()
        doc_hash = hashlib.sha256(file_bytes).hexdigest()[:20]

        ids: List[str] = []
        prefixed_chunks: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for idx, chunk in enumerate(raw_chunks):
            formatted = f"[SUMBER REGULASI: {clean_name}]\n{chunk.strip()}"
            chunk_id = f"pdf-{doc_hash}-{idx:04d}"
            ids.append(chunk_id)
            prefixed_chunks.append(formatted)
            metadatas.append(
                {
                    "source_type": "pdf_regulasi",
                    "doc_name": clean_name,
                    "domain": dom,
                    "tema_pajak": tema,
                    "chunk_index": idx,
                    "page_number": chunk_pages[idx],
                    "page_count": len(page_texts),
                    "contributor": contributor.strip() or "Tim Regulasi Bapenda",
                    "ingested_at": now_iso,
                }
            )

        source_id = self.archive.stage(prefixed_chunks, metadatas, file_bytes, clean_name, warnings)

        summary = {
            "source_id": source_id, "review_status": "pending",
            "source_type": "pdf_regulasi",
            "doc_name": clean_name,
            "domain": dom,
            "tema_pajak": tema,
            "chunks_ingested": len(ids),
            "contributor": contributor.strip() or "Tim Regulasi Bapenda",
            "ingested_at": now_iso,
            "total_collection_chunks": self.collection.count(),
        }
        return summary

    def ingest_excel(
        self,
        file_bytes: bytes,
        filename: str,
        category: str = "PBB-P2",
        contributor: str = "Analis Data Pajak",
    ) -> Dict[str, Any]:
        if not file_bytes:
            raise ValueError("File Excel/CSV kosong atau tidak valid.")

        clean_name = Path(filename).name
        suffix = Path(clean_name).suffix.lower()
        dom = normalize_domain(category)
        tema = domain_to_theme(dom)
        now_iso = datetime.now(timezone.utc).isoformat()
        file_hash = hashlib.sha1(f"{clean_name}:{len(file_bytes)}".encode("utf-8")).hexdigest()[:10]

        sheets: Dict[str, pd.DataFrame] = {}
        bio = io.BytesIO(file_bytes)
        if suffix == ".csv":
            sheets["CSV_Data"] = pd.read_csv(bio)
        elif suffix in (".xlsx", ".xls"):
            excel_obj = pd.read_excel(bio, sheet_name=None, engine="openpyxl")
            sheets = excel_obj if isinstance(excel_obj, dict) else {"Sheet1": excel_obj}
        else:
            raise ValueError("Format file tidak didukung. Gunakan .xlsx atau .csv.")

        ids: List[str] = []
        docs: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for sheet_name, df in sheets.items():
            if df is None or df.empty:
                continue
            df_clean = df.dropna(how="all")
            for row_idx, (_, row_series) in enumerate(df_clean.iterrows(), start=1):
                row_dict = row_series.to_dict()
                semantic_text = serialize_row(category=dom, row_idx=row_idx, row_dict=row_dict)
                if len(semantic_text) <= len(f"[DATA TABEL: {dom} - Baris {row_idx}] "):
                    continue
                cid = f"xls-{file_hash}-{sheet_name[:12].lower()}-{row_idx:05d}"
                ids.append(cid)
                docs.append(semantic_text)
                metadatas.append(
                    {
                        "source_type": "excel_data",
                        "doc_name": clean_name,
                        "category": dom,
                        "domain": dom,
                        "tema_pajak": tema,
                        "sheet_name": str(sheet_name),
                        "row_index": int(row_idx),
                        "contributor": contributor.strip() or "Analis Data Pajak",
                        "ingested_at": now_iso,
                    }
                )

        if not ids:
            raise ValueError("Tidak ada baris data valid yang dapat diindeks dari file tabel.")

        source_id = self.archive.stage(docs, metadatas, file_bytes, clean_name)

        summary = {
            "source_id": source_id, "review_status": "pending",
            "source_type": "excel_data",
            "doc_name": clean_name,
            "domain": dom,
            "tema_pajak": tema,
            "rows_ingested": len(ids),
            "sheets_processed": len(sheets),
            "contributor": contributor.strip() or "Analis Data Pajak",
            "ingested_at": now_iso,
            "total_collection_chunks": self.collection.count(),
        }
        return summary

    def ingest_user_reasoning(self, payload: LearnReasoningPayload) -> Dict[str, Any]:
        dom = normalize_domain(payload.topik_pajak)
        tema = domain_to_theme(dom)
        now_iso = datetime.now(timezone.utc).isoformat()
        formatted_block = format_reasoning_block(payload)
        digest = hashlib.sha1(
            f"{payload.topik_pajak}:{payload.pertanyaan_kasus}:{payload.jawaban_final}".encode("utf-8")
        ).hexdigest()[:12]
        chunk_id = f"usr-reasoning-{dom.lower()}-{digest}"
        doc_name = f"Penalaran Kasus {dom} ({payload.kontributor.strip()})"

        metadata = {
            "source_type": "user_reasoning",
            "doc_name": doc_name,
            "topik_pajak": payload.topik_pajak.strip(),
            "domain": dom,
            "tema_pajak": tema,
            "contributor": payload.kontributor.strip(),
            "ingested_at": now_iso,
        }
        source_id = self.archive.stage([formatted_block], [metadata], None, doc_name)

        summary = {
            "source_id": source_id, "review_status": "pending",
            "chunk_id": chunk_id,
            "source_type": "user_reasoning",
            "doc_name": doc_name,
            "domain": dom,
            "tema_pajak": tema,
            "contributor": payload.kontributor.strip(),
            "ingested_at": now_iso,
            "formatted_block": formatted_block,
            "total_collection_chunks": self.collection.count(),
        }
        return summary

    def reindex_active_sources(self):
        import json
        total = 0
        for source in self.archive.list():
            if source['status'] != 'approved':
                continue
            payload = json.loads(self.archive.get(source['id'])['payload'])
            for start in range(0, len(payload['ids']), 100):
                texts = payload['documents'][start:start+100]
                self.collection.upsert(ids=payload['ids'][start:start+100], documents=texts,
                    metadatas=payload['metadatas'][start:start+100], embeddings=embedder.embed_texts(texts))
                total += len(texts)
        return {'total_points':total, 'collection':self.collection_name}

    def approved_ids(self):
        return [item["id"] for item in self.archive.list() if item["status"] == "approved"]

    def active_records(self, include):
        approved = self.approved_ids()
        if not approved:
            return {"ids": [], "documents": [], "metadatas": []}
        return self.collection.get(where={"document_id": {"$in": approved}}, include=include)

    def query_knowledge(
        self,
        query: str,
        top_k: int = 4,
        domain: Optional[str] = None,
        tema_pajak: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> List[RetrievalResult]:
        query = normalize_legal_query(query)
        comparisons = legal_queries(query)
        if comparisons:
            groups = [self.query_knowledge(part, max(1, top_k // len(comparisons)), domain, tema_pajak, source_type)
                      for part in comparisons]
            merged, seen = [], set()
            for index in range(max((len(group) for group in groups), default=0)):
                for group in groups:
                    if index < len(group) and group[index].chunk_id not in seen:
                        merged.append(group[index]); seen.add(group[index].chunk_id)
            return merged[:top_k + 10]
        total = self.collection.count()
        if total == 0:
            return []

        q_vec = embedder.embed_query(query)
        approved = self.approved_ids()
        if not approved:
            return []
        where_clauses: List[Dict[str, Any]] = [{"document_id": {"$in": approved}}]
        if domain and domain.upper() in TAX_DOMAINS:
            where_clauses.append({"domain": domain.upper()})
        elif tema_pajak and tema_pajak.upper() in TAX_THEMES:
            where_clauses.append({"tema_pajak": tema_pajak.upper()})
        if source_type:
            where_clauses.append({"source_type": source_type})

        where_filter: Optional[Dict[str, Any]] = None
        if len(where_clauses) == 1:
            where_filter = where_clauses[0]
        elif len(where_clauses) > 1:
            where_filter = {"$and": where_clauses}

        res = self.collection.query(
            query_embeddings=[q_vec], n_results=min(max(top_k * 4, 24), total), where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        ids_list = (res.get("ids") or [[]])[0]
        docs_list = (res.get("documents") or [[]])[0]
        metas_list = (res.get("metadatas") or [[]])[0]
        dists_list = (res.get("distances") or [[]])[0]

        tax_code = domain.upper() if domain and domain.upper() in TAX_DOMAINS else tema_pajak.upper() if tema_pajak and tema_pajak.upper() in TAX_THEMES else None
        tax_code = 'PBB-P2' if tax_code == 'JPB' else tax_code
        lexical_ids = self.archive.search_text(query, tax_code, source_type, limit=24)
        scores = {}
        for weight, ranked in [(1.0, ids_list), (1.5, lexical_ids)]:
            for rank, cid in enumerate(ranked, 1):
                scores[cid] = scores.get(cid, 0.0) + weight / (60 + rank)
        ranked_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
        if any(text_query_scope(query).values()):
            ranked_ids = [cid for cid in ranked_ids if cid in lexical_ids]
        valid = self.archive.validated_records(ranked_ids, tax_code)
        ranked_ids = [cid for cid in ranked_ids if cid in valid and document_matches(query, valid[cid]['metadata'].get('doc_name', '')) and passage_score(query, valid[cid]['text'], valid[cid]['metadata'].get('doc_name', '')) >= 0]
        ranked_ids.sort(key=lambda cid: (passage_score(query, valid[cid]['text'], valid[cid]['metadata'].get('doc_name', '')), scores[cid]), reverse=True)
        distances = dict(zip(ids_list, dists_list))
        results: List[RetrievalResult] = []
        def result_for(cid, row, method):
            meta_dict = {**row['metadata'], 'retrieval_method': method}
            header = self.archive.page_context(cid)
            if header:meta_dict['page_context'] = header
            dist = float(distances.get(cid, 1.0))
            return RetrievalResult(chunk_id=str(cid),text=row['text'],similarity=round(max(0.0,min(1.0,1.0-dist)),4),
                cosine_distance=round(dist,4),source_type=str(meta_dict.get('source_type','pdf_regulasi')),
                doc_name=str(meta_dict.get('doc_name','Dokumen')),domain=str(meta_dict.get('domain','PBB-P2')),
                contributor=str(meta_dict.get('contributor','')),ingested_at=str(meta_dict.get('ingested_at','')),metadata=meta_dict)
        concepts = normalized_terms(query)
        focused_benefit = 'pembebasan' in concepts and bool({'100', 'penuh'} & concepts)
        seed_limit = min(top_k, 2) if focused_benefit else top_k
        seeds=[]
        for cid in ranked_ids:
            if cid in valid:
                seeds.append(result_for(cid,valid[cid],'hybrid' if cid in lexical_ids else 'vector'))
            if len(seeds)>=seed_limit:break
        seen=set()
        for hit in seeds:
            if hit.chunk_id in seen:continue
            results.append(hit);seen.add(hit.chunk_id)
            if len(results) <= 2:
                for cid, row in self.archive.legal_context(hit.chunk_id, tax_code).items():
                    if cid not in seen and len(results) < top_k + 10:
                        results.append(result_for(cid, row, 'article_context')); seen.add(cid)
            # A colon at the boundary signals an introduction whose list may be on the next page.
            if hit.text.rstrip().endswith((':','：')) and len(results)<top_k+2:
                for cid,row in self.archive.following_chunks(hit.chunk_id,tax_code).items():
                    if cid in seen:continue
                    body='\n'.join(line for line in row['text'].splitlines() if not line.startswith(('[SUMBER','##'))).strip()
                    if len(body)<25:continue
                    results.append(result_for(cid,row,'continuation'));seen.add(cid)
                    break
        return results[:top_k+10]

    @staticmethod
    def _document_key(chunk_id: str, metadata: Dict[str, Any]) -> str:
        # Older uploads have no document_id; recover their import identity from
        # the stored chunk ID rather than assuming file names are unique.
        parts = chunk_id.split("-")
        imported_id = "-".join(parts[:2]) if parts[0] in ("pdf", "xls") else chunk_id
        identity = [metadata.get("source_type", ""), metadata.get("doc_name", ""),
                    metadata.get("domain", ""), metadata.get("document_id", imported_id)]
        return hashlib.sha256("\0".join(str(value) for value in identity).encode()).hexdigest()[:24]

    def get_chunk_details(self, source_id: Optional[str] = None, query: str = "",
                          offset: int = 0, limit: int = 20) -> Dict[str, Any]:
        records = self.active_records(["documents", "metadatas"])
        documents: Dict[str, Dict[str, Any]] = {}
        chunks: List[Dict[str, Any]] = []
        search = query.strip().casefold()
        for chunk_id, text, meta in zip(records.get("ids") or [],
                                       records.get("documents") or [], records.get("metadatas") or []):
            meta = meta or {}
            key = self._document_key(chunk_id, meta)
            if key not in documents:
                documents[key] = {"id": key, "name": meta.get("doc_name", "Sumber tanpa nama"),
                    "source_type": meta.get("source_type", ""), "domain": meta.get("domain", ""),
                    "chunk_count": 0}
            documents[key]["chunk_count"] += 1
            if source_id and source_id != key:
                continue
            if search and search not in f"{meta.get('doc_name', '')}\n{text or ''}".casefold():
                continue
            chunks.append({"id": chunk_id, "source_id": key, "document_name": documents[key]["name"],
                "text": text or "", "chunk_index": meta.get("chunk_index"),
                "page": meta.get("page_number"), "sheet": meta.get("sheet_name"),
                "row": meta.get("row_index"), "source_type": meta.get("source_type", "")})
        chunks.sort(key=lambda item: (item["document_name"].casefold(), item["source_id"],
                    item["chunk_index"] if isinstance(item["chunk_index"], int) else item["row"] or 0, item["id"]))
        return {"documents": sorted(documents.values(), key=lambda item: (item["name"].casefold(), item["id"])),
                "total_documents": len(documents), "total_chunks": len(records.get("ids") or []),
                "matched_chunks": len(chunks), "offset": offset, "limit": limit,
                "items": chunks[offset:offset + limit]}


    def get_collection_telemetry(self) -> Dict[str, Any]:
        # Dashboard counts come from the active catalog, never a full vector scroll.
        with self.archive.connect() as db:
            rows = db.execute("""SELECT a.metadata_json, count(c.id) AS chunks
                FROM document_versions v JOIN documents d ON d.id=v.document_id
                JOIN archive_attributes a ON a.version_id=v.id
                JOIN document_chunks c ON c.version_id=v.id AND c.state='ready'
                WHERE v.state='active' AND d.lifecycle='published'
                AND d.deleted_at IS NULL AND v.deleted_at IS NULL
                AND d.access_scope IN ('public','authenticated')
                GROUP BY v.id""").fetchall()
        metas = [(json.loads(row['metadata_json']), row['chunks']) for row in rows]

        by_source_type: Dict[str, int] = {
            "pdf_regulasi": 0,
            "excel_data": 0,
            "user_reasoning": 0,
        }
        domain_matrix: Dict[str, Dict[str, int]] = {
            dom: {"pdf_regulasi": 0, "excel_data": 0, "user_reasoning": 0}
            for dom in TAX_DOMAINS
        }
        recent_sources: List[Dict[str, Any]] = []
        seen_docs = set()

        for m, chunk_count in metas:
            if not m:
                continue
            st = str(m.get("source_type", "pdf_regulasi"))
            dom = normalize_domain(str(m.get("domain") or m.get("tema_pajak") or "PBB-P2"))
            if st in by_source_type:
                by_source_type[st] += chunk_count
            if dom in domain_matrix and st in domain_matrix[dom]:
                domain_matrix[dom][st] += chunk_count

            doc_key = f"{st}:{m.get('doc_name', '')}:{dom}"
            if doc_key not in seen_docs:
                seen_docs.add(doc_key)
                recent_sources.append(
                    {
                        "source_type": st,
                        "doc_name": m.get("doc_name", "Korpus Lokal"),
                        "domain": dom,
                        "contributor": m.get("contributor", "Bapenda DKI"),
                        "ingested_at": m.get("ingested_at", ""),
                    }
                )

        recent_sources.sort(key=lambda x: x.get("ingested_at", ""), reverse=True)

        total_slots = len(TAX_DOMAINS) * 3
        covered_slots = sum(
            1
            for dom in TAX_DOMAINS
            for st in ("pdf_regulasi", "excel_data", "user_reasoning")
            if domain_matrix[dom][st] > 0
        )
        full_domains = sum(
            1
            for dom in TAX_DOMAINS
            if all(domain_matrix[dom][st] > 0 for st in ("pdf_regulasi", "excel_data", "user_reasoning"))
        )
        coverage_pct = round((covered_slots / total_slots) * 100.0, 2) if total_slots else 0.0

        return {
            "collection": self.collection_name,
            "persist_dir": str(QDRANT_STORAGE_DIR),
            "engine": "qdrant",
            "mode": self.mode,
            "distance_metric": "cosine",
            "total_chunks": sum(count for _, count in metas),
            "total_documents": len(metas),
            "by_source_type": by_source_type,
            "domain_matrix": domain_matrix,
            "covered_slots": covered_slots,
            "total_slots": total_slots,
            "full_domains_count": full_domains,
            "domain_coverage_percentage": coverage_pct,
            "recent_sources": recent_sources[:15],
            "last_ingested_source": self.last_ingested_source,
        }


knowledge_store = SmartTaxKnowledgeStore()
