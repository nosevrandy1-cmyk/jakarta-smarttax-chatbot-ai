from datetime import datetime, timezone
import hashlib
import io
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pandas as pd
from pydantic import BaseModel, Field
import pymupdf
import pymupdf4llm

from .config import (
    CHROMA_COLLECTION,
    CHROMA_STORAGE_DIR,
    TAX_DOMAINS,
    UPLOAD_STAGING_DIR,
)
from .embedder import embedder
from .tax_db import (
    DKI_LEGAL_CORPUS,
    DKI_REGULASI_CHUNKS,
    DKI_TAX_RECORDS,
    TAX_THEMES,
)


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
        self.client = chromadb.PersistentClient(path=str(CHROMA_STORAGE_DIR))
        self.collection_name = CHROMA_COLLECTION
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n## ", "\n### ", "\nPasal ", "\n\n", "\n", " "],
        )
        self.last_ingested_source: Optional[Dict[str, Any]] = None

    def ensure_baseline_seeded(self) -> Dict[str, int]:
        existing_count = self.collection.count()
        if existing_count > 0:
            return {"seeded": 0, "total_chunks": existing_count}
        return self.seed_baseline_knowledge()

    def seed_baseline_knowledge(self) -> Dict[str, int]:
        now_iso = datetime.now(timezone.utc).isoformat()
        ids: List[str] = []
        docs: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for leg in DKI_LEGAL_CORPUS:
            dom = normalize_domain(leg["tema_pajak"])
            doc_name = f"{leg['jenis_instrumen']} ({leg['kode_pasal']})"
            chunk_text = (
                f"[SUMBER REGULASI: {doc_name}]\n"
                f"## {leg['bab_bagian']}\n"
                f"### {leg['pasal_ayat']} - {leg['tentang']}\n"
                f"{leg['bunyi_norma']}\n"
                f"Kaidah Perumusan: {leg['kaidah_perumusan']}"
            )
            cid = f"seed-pdf-{leg['kode_pasal'].lower()}"
            ids.append(cid)
            docs.append(chunk_text)
            metadatas.append(
                {
                    "source_type": "pdf_regulasi",
                    "doc_name": doc_name,
                    "domain": dom,
                    "tema_pajak": leg["tema_pajak"],
                    "chunk_index": 0,
                    "contributor": "Tim Hukum Bapenda DKI",
                    "ingested_at": now_iso,
                }
            )

        for reg in DKI_REGULASI_CHUNKS:
            dom = normalize_domain(reg["tema_pajak"])
            doc_name = f"Ringkasan Regulasi {reg['tema_pajak']} DKI Jakarta"
            chunk_text = f"[SUMBER REGULASI: {doc_name}]\n{reg['content']}"
            cid = f"seed-reg-{reg['id']}"
            ids.append(cid)
            docs.append(chunk_text)
            metadatas.append(
                {
                    "source_type": "pdf_regulasi",
                    "doc_name": doc_name,
                    "domain": dom,
                    "tema_pajak": reg["tema_pajak"],
                    "chunk_index": 1,
                    "contributor": "Bapenda Provinsi DKI Jakarta",
                    "ingested_at": now_iso,
                }
            )

        for idx, rec in enumerate(DKI_TAX_RECORDS, start=1):
            is_jpb = "gedung" in rec["nama_objek"].lower() or "scbd" in rec["nama_objek"].lower()
            dom = "JPB" if is_jpb else normalize_domain(rec["tema_pajak"])
            category = f"Ketetapan {dom} DKI Jakarta"
            serialized = serialize_row(category, idx, rec)
            cid = f"seed-xls-{idx:03d}"
            ids.append(cid)
            docs.append(serialized)
            metadatas.append(
                {
                    "source_type": "excel_data",
                    "doc_name": f"Rekap_Ketetapan_{dom}_2026.xlsx",
                    "category": category,
                    "sheet_name": dom,
                    "row_index": idx,
                    "domain": dom,
                    "tema_pajak": rec["tema_pajak"],
                    "contributor": "Subbid Data & Informasi Bapenda",
                    "ingested_at": now_iso,
                }
            )

        baseline_reasonings = [
            LearnReasoningPayload(
                pertanyaan_kasus="Bagaimana perhitungan dan syarat pembebasan 100% PBB-P2 rumah tinggal Orang Pribadi serta batas NJOPTKP di DKI Jakarta?",
                alur_penalaran="Berdasarkan Pasal 36-39 Perda Pajak Daerah DKI Jakarta dan Pergub Insentif PBB-P2 Pasal 4-9: (1) NJOPTKP ditetapkan Rp 60.000.000 untuk 1 objek tertinggi; (2) Rumah tinggal milik Orang Pribadi dengan NJOP s.d. Rp 2.000.000.000 (Rp 2 Miliar) yang tervalidasi NIK memperoleh pembebasan pokok 100%.",
                jawaban_final="NJOPTKP PBB-P2 di Provinsi DKI Jakarta adalah Rp 60.000.000 per Wajib Pajak untuk 1 objek tertinggi, dan rumah tinggal Orang Pribadi dengan NJOP sampai dengan Rp 2.000.000.000 (Rp 2 Miliar) tervalidasi NIK diberikan pembebasan pokok PBB-P2 sebesar 100%.",
                topik_pajak="PBB-P2",
                kontributor="Auditor Utama PBB-P2",
            ),
            LearnReasoningPayload(
                pertanyaan_kasus="Bagaimana pembedaan tarif PBJT Restoran (service charge), jatuh tempo e-SPTPD, dan tarif hiburan tertentu (diskotek/karaoke/spa) di DKI Jakarta?",
                alur_penalaran="Mengacu Pasal 45-57 Perda Pajak Daerah DKI Jakarta: Dasar pengenaan PBJT mencakup jumlah pembayaran termasuk biaya pelayanan (service charge). Tarif Makanan/Minuman (Restoran), Hotel, Parkir, dan Hiburan umum sebesar 10%, sedangkan hiburan tertentu (diskotek, karaoke, kelab malam, bar, mandi uap/spa) dikenakan tarif khusus 40%. Jatuh tempo pembayaran tanggal 15 dan pelaporan e-SPTPD tanggal 20 bulan berikutnya.",
                jawaban_final="Tarif PBJT Restoran, Hotel, dan Parkir adalah 10% termasuk service charge (biaya pelayanan) dengan jatuh tempo pembayaran tanggal 15 dan pelaporan e-SPTPD tanggal 20, sedangkan tarif khusus hiburan diskotek, karaoke, kelab malam, bar, dan spa adalah 40%.",
                topik_pajak="PBJT",
                kontributor="Tim Pemeriksa PBJT Bapenda",
            ),
            LearnReasoningPayload(
                pertanyaan_kasus="Bagaimana perhitungan BPHTB Jual Beli (NPOPTKP Rp 80 Juta) vs Waris (NPOPTKP Rp 350 Juta) dengan tarif 5% di DKI Jakarta?",
                alur_penalaran="Berdasarkan Pasal 58-64 Perda DKI Jakarta: Rumus BPHTB adalah 5% x (NPOP - NPOPTKP). Jika NPOP lebih rendah dari NJOP PBB-P2, digunakan NJOP PBB-P2. NPOPTKP perolehan umum pertama (Jual Beli/AJB) sebesar Rp 80.000.000 (contoh NPOP Rp 3,5 Miliar -> NPOPKP Rp 3.420.000.000 x 5% = Rp 171.000.000). Untuk Waris atau Hibah Wasiat sedarah satu derajat, NPOPTKP sebesar Rp 350.000.000 (contoh NPOP Rp 2,4 Miliar -> NPOPKP Rp 2.050.000.000 x 5% = Rp 102.500.000).",
                jawaban_final="Tarif BPHTB adalah 5% dari NPOPKP (NPOP dikurangi NPOPTKP, atau menggunakan NJOP PBB-P2 bila NPOP lebih rendah). NPOPTKP Jual Beli umum adalah Rp 80.000.000 dan NPOPTKP Waris adalah Rp 350.000.000.",
                topik_pajak="BPHTB",
                kontributor="Analis Hukum BPHTB",
            ),
        ]

        for r_idx, item in enumerate(baseline_reasonings, start=1):
            dom = normalize_domain(item.topik_pajak)
            block = format_reasoning_block(item)
            cid = f"seed-reasoning-{r_idx:03d}"
            ids.append(cid)
            docs.append(block)
            metadatas.append(
                {
                    "source_type": "user_reasoning",
                    "doc_name": f"Penalaran Ahli {dom} #{r_idx}",
                    "topik_pajak": item.topik_pajak,
                    "domain": dom,
                    "tema_pajak": domain_to_theme(dom),
                    "contributor": item.kontributor,
                    "ingested_at": now_iso,
                }
            )

        vectors = embedder.embed_texts(docs)
        self.collection.upsert(
            ids=ids,
            embeddings=vectors,
            documents=docs,
            metadatas=metadatas,
        )
        return {"seeded": len(ids), "total_chunks": self.collection.count()}

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

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)

        try:
            md_text = pymupdf4llm.to_markdown(str(tmp_path))
            if not md_text or not md_text.strip():
                doc = pymupdf.open(str(tmp_path))
                pages = [page.get_text("text") for page in doc]
                doc.close()
                md_text = "\n\n".join(pages)
        finally:
            tmp_path.unlink(missing_ok=True)

        cleaned_md = (md_text or "").strip()
        if not cleaned_md:
            raise ValueError("Tidak ditemukan teks yang dapat diekstrak dari dokumen PDF.")

        raw_chunks = self.splitter.split_text(cleaned_md)
        if not raw_chunks:
            raw_chunks = [cleaned_md]

        now_iso = datetime.now(timezone.utc).isoformat()
        doc_hash = hashlib.sha1(f"{clean_name}:{len(file_bytes)}".encode("utf-8")).hexdigest()[:10]

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
                    "contributor": contributor.strip() or "Tim Regulasi Bapenda",
                    "ingested_at": now_iso,
                }
            )

        vectors = embedder.embed_texts(prefixed_chunks)
        for start in range(0, len(ids), 100):
            end = start + 100
            self.collection.upsert(
                ids=ids[start:end],
                embeddings=vectors[start:end],
                documents=prefixed_chunks[start:end],
                metadatas=metadatas[start:end],
            )

        summary = {
            "source_type": "pdf_regulasi",
            "doc_name": clean_name,
            "domain": dom,
            "tema_pajak": tema,
            "chunks_ingested": len(ids),
            "contributor": contributor.strip() or "Tim Regulasi Bapenda",
            "ingested_at": now_iso,
            "total_collection_chunks": self.collection.count(),
        }
        self.last_ingested_source = summary
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

        for start in range(0, len(ids), 100):
            end = start + 100
            batch_docs = docs[start:end]
            batch_vecs = embedder.embed_texts(batch_docs)
            self.collection.upsert(
                ids=ids[start:end],
                embeddings=batch_vecs,
                documents=batch_docs,
                metadatas=metadatas[start:end],
            )

        summary = {
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
        self.last_ingested_source = summary
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

        vec = embedder.embed_texts([formatted_block])
        metadata = {
            "source_type": "user_reasoning",
            "doc_name": doc_name,
            "topik_pajak": payload.topik_pajak.strip(),
            "domain": dom,
            "tema_pajak": tema,
            "contributor": payload.kontributor.strip(),
            "ingested_at": now_iso,
        }
        self.collection.upsert(
            ids=[chunk_id],
            embeddings=vec,
            documents=[formatted_block],
            metadatas=[metadata],
        )

        summary = {
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
        self.last_ingested_source = summary
        return summary

    def query_knowledge(
        self,
        query: str,
        top_k: int = 4,
        domain: Optional[str] = None,
        tema_pajak: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> List[RetrievalResult]:
        self.ensure_baseline_seeded()
        total = self.collection.count()
        if total == 0:
            return []

        q_vec = embedder.embed_query(query)
        where_clauses: List[Dict[str, Any]] = []
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

        try:
            res = self.collection.query(
                query_embeddings=[q_vec],
                n_results=min(top_k, total),
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            res = self.collection.query(
                query_embeddings=[q_vec],
                n_results=min(top_k, total),
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

    def get_collection_telemetry(self) -> Dict[str, Any]:
        self.ensure_baseline_seeded()
        all_items = self.collection.get(include=["metadatas"])
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
            "by_source_type": by_source_type,
            "domain_matrix": domain_matrix,
            "covered_slots": covered_slots,
            "total_slots": total_slots,
            "full_domains_count": full_domains,
            "domain_coverage_percentage": coverage_pct,
            "recent_sources": recent_sources[:15],
            "last_ingested_source": self.last_ingested_source,
        }

    def generate_sample_pdf_bytes(self, domain: str = "JPB") -> tuple[bytes, str]:
        dom = normalize_domain(domain)
        doc = pymupdf.open()
        page = doc.new_page()
        content = (
            f"# PERATURAN GUBERNUR PROVINSI DKI JAKARTA TENTANG KLASIFIKASI {dom} 2026\n\n"
            f"## BAB I KETENTUAN UMUM DAN TARIF {dom}\n\n"
            f"Pasal 1\n"
            f"(1) Objek gedung perkantoran komersial (JPB Perkantoran) seperti Gedung Perkantoran SCBD Lot 9 "
            f"(NOP 31.74.010.003.008-0042.0) dengan NJOP Rp 185.000.000.000 dan pengurang NJOPTKP Rp 60.000.000 "
            f"dikenakan tarif PBB-P2 sebesar 0,5% dengan pokok pajak Rp 369.880.000.\n"
            f"(2) Keterlambatan pembayaran setelah jatuh tempo dikenakan sanksi administratif bunga denda 1% per bulan "
            f"(maksimal 24 bulan), yaitu Rp 3.698.800 untuk 1 bulan tunggakan.\n\n"
            f"Pasal 2\n"
            f"(1) Penyelenggaraan reklame pada Kawasan Kendali Ketat wajib berbentuk LED/Videotron menempel pada bangunan "
            f"(building-attached) dengan tarif 25% dari Nilai Sewa Reklame (NSR).\n"
            f"(2) Tarif Pajak Air Tanah (PAT) ditetapkan 20% dari Nilai Perolehan Air Tanah (NPAT) berdasarkan Harga Dasar Air (HDA) "
            f"pada zona konservasi dan wajib memasang meter air otomatis (AMR)."
        )
        rect = pymupdf.Rect(48, 48, 545, 780)
        page.insert_textbox(rect, content, fontsize=10.5, fontname="helv")
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes, f"Pergub_DKI_Pedoman_{dom}_2026.pdf"

    def generate_sample_excel_bytes(self, domain: str = "REKLAME") -> tuple[bytes, str]:
        dom = normalize_domain(domain)
        rows = [
            {
                "Kode_Domain": dom,
                "Nomor_Ketetapan": "SKPD-REK-3171-2026-0402",
                "Wajib_Pajak": "PT Media Visi Digital Jakarta",
                "Kawasan": "Kawasan Kendali Ketat Sudirman-Thamrin",
                "Jenis_Media": "Videotron LED building-attached",
                "Dasar_Pengenaan": "Nilai Sewa Reklame (NSR) Rp 960.000.000",
                "Tarif_Pajak": "25%",
                "Pokok_Pajak_Rp": 240000000,
                "Sanksi_Denda": "1% per bulan (maksimal 24 bulan)",
            },
            {
                "Kode_Domain": "PAT",
                "Nomor_Ketetapan": "SKPD-PAT-3175-2026-0881",
                "Wajib_Pajak": "PT Tirta Manufaktur Cakung",
                "Kawasan": "Zona Konservasi Pulo Gadung",
                "Jenis_Media": "Meter Air Otomatis (AMR)",
                "Dasar_Pengenaan": "Nilai Perolehan Air Tanah (NPAT) & Harga Dasar Air (HDA) Rp 185.000.000",
                "Tarif_Pajak": "20%",
                "Pokok_Pajak_Rp": 37000000,
                "Sanksi_Denda": "1% per bulan",
            },
        ]
        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=f"Tabel_{dom}")
        return buf.getvalue(), f"Tabel_Ketetapan_{dom}_DKI_2026.xlsx"


chroma_store = SmartTaxChromaStore()
