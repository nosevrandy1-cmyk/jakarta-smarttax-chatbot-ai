from datetime import datetime, timezone
import hashlib
import io
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pandas as pd
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from .config import (
    CHROMA_COLLECTION,
    CHROMA_STORAGE_DIR,
    TAX_DOMAINS,
    UPLOAD_STAGING_DIR,
)
from .embedder import embedder
from .source_review import SourceArchive
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
        f"Kesimpulan / Solusi Resmi: {payload.jawaban_final.strip()}"
    )


class SmartTaxChromaStore:
    def __init__(self) -> None:
        CHROMA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_STAGING_DIR.mkdir(parents=True, exist_ok=True)
        self.archive = SourceArchive(UPLOAD_STAGING_DIR)
        self.client = chromadb.PersistentClient(path=str(CHROMA_STORAGE_DIR))
        self.collection_name = CHROMA_COLLECTION
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=None,  # Only explicit application-generated vectors are accepted.
            metadata={"hnsw:space": "cosine"},
        )
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
            query_embeddings=[q_vec], n_results=min(top_k, total), where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        ids_list = (res.get("ids") or [[]])[0]
        docs_list = (res.get("documents") or [[]])[0]
        metas_list = (res.get("metadatas") or [[]])[0]
        dists_list = (res.get("distances") or [[]])[0]

        results: List[RetrievalResult] = []
        for cid, doc_text, meta, dist in zip(ids_list, docs_list, metas_list, dists_list):
            meta_dict = meta or {}
            cosine_dist = float(dist) if dist is not None else 0.5
            sim = max(0.0, min(1.0, 1.0 - cosine_dist))
            results.append(
                RetrievalResult(
                    chunk_id=str(cid),
                    text=str(doc_text or ""),
                    similarity=round(sim, 4),
                    cosine_distance=round(cosine_dist, 4),
                    source_type=str(meta_dict.get("source_type", "pdf_regulasi")),
                    doc_name=str(meta_dict.get("doc_name", "Korpus Lokal DKI")),
                    domain=str(meta_dict.get("domain", meta_dict.get("tema_pajak", "PBB-P2"))),
                    contributor=str(meta_dict.get("contributor", "Bapenda DKI")),
                    ingested_at=str(meta_dict.get("ingested_at", "")),
                    metadata=meta_dict,
                )
            )
        return results

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
        all_items = self.active_records(["metadatas"])
        metas = all_items.get("metadatas") or []

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

        for m in metas:
            if not m:
                continue
            st = str(m.get("source_type", "pdf_regulasi"))
            dom = normalize_domain(str(m.get("domain") or m.get("tema_pajak") or "PBB-P2"))
            if st in by_source_type:
                by_source_type[st] += 1
            if dom in domain_matrix and st in domain_matrix[dom]:
                domain_matrix[dom][st] += 1

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
            "persist_dir": str(CHROMA_STORAGE_DIR),
            "distance_metric": "cosine",
            "total_chunks": len(metas),
            "total_documents": len({self._document_key(cid, meta or {}) for cid, meta in zip(all_items.get("ids") or [], metas)}),
            "by_source_type": by_source_type,
            "domain_matrix": domain_matrix,
            "covered_slots": covered_slots,
            "total_slots": total_slots,
            "full_domains_count": full_domains,
            "domain_coverage_percentage": coverage_pct,
            "recent_sources": recent_sources[:15],
            "last_ingested_source": self.last_ingested_source,
        }


chroma_store = SmartTaxChromaStore()
