import asyncio
import json
import logging
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from .config import (
    DEEPSEEK_DRAFTING_MODEL,
    DEFAULT_CHAT_MODEL,
    OLLAMA_API_KEY,
    OLLAMA_CLOUD_URL,
    OLLAMA_LOCAL_URL,
    OLLAMA_SECONDARY_URL,
    OLLAMA_TIMEOUT,
    OLLAMA_NUM_CTX,
    OLLAMA_TEMPERATURE,
    OLLAMA_TOP_P,
    OLLAMA_TOP_K,
    OLLAMA_THINK,
)
from .rag_ingestion import chroma_store
from .tax_db import (
    TAX_THEMES,
    daftar_tunggakan_pajak_dki,
    get_all_legal_corpus,
    get_all_sppt_records,
    get_regulasi_chunks,
    rekapitulasi_pajak_dki,
    susun_rancangan_hukum_dki,
    telusuri_pasal_hukum_dki,
)
from .vector_store import vector_store

logger = logging.getLogger(__name__)

# Modular Capability Modes for Easy Feature Scaling
CAPABILITY_MODES: Dict[str, Dict[str, str]] = {
    "konsultasi": {
        "code": "konsultasi",
        "label": "Konsultasi Tarif & Data",
        "preferred_model": DEFAULT_CHAT_MODEL,
        "description": "Cek objek pajak, simulasi rumus, tarif, tunggakan, dan rekap wilayah.",
    },
    "pasal_hukum": {
        "code": "pasal_hukum",
        "label": "Pasal & Dasar Hukum",
        "preferred_model": DEFAULT_CHAT_MODEL,
        "description": "Telusur bunyi pasal, ayat, hierarki dasar hukum, dan norma regulasi.",
    },
    "perumusan_hukum": {
        "code": "perumusan_hukum",
        "label": "Perumusan Hukum (Drafting)",
        "preferred_model": DEEPSEEK_DRAFTING_MODEL,
        "description": "Susun draf pasal baru, konsiderans Menimbang/Mengingat, & kajian regulasi.",
    },
}

THEME_KEYWORDS: Dict[str, List[str]] = {
    "PBB-P2": [
        "pbb",
        "sppt",
        "nop",
        "njop",
        "njoptkp",
        "bumi dan bangunan",
        "scbd",
        "menteng",
        "kelapa gading",
        "pondok indah",
    ],
    "PBJT": [
        "pbjt",
        "restoran",
        "rumah makan",
        "kafe",
        "hotel",
        "parkir",
        "hiburan",
        "karaoke",
        "diskotek",
        "makanan",
        "minuman",
        "sptpd",
        "senopati",
    ],
    "BPHTB": [
        "bphtb",
        "sspd",
        "ajb",
        "jual beli",
        "waris",
        "hibah",
        "npop",
        "npoptkp",
        "akta",
        "balik nama",
    ],
    "REKLAME": [
        "reklame",
        "videotron",
        "billboard",
        "baliho",
        "megatron",
        "nsr",
        "kawasan kendali ketat",
    ],
    "PAT": [
        "air tanah",
        "pat",
        "npat",
        "sumur bor",
        "abstraksi air",
        "volume air",
        "pulo gadung",
    ],
}

DRAFTING_KEYWORDS = [
    "rumuskan",
    "merumuskan",
    "perumusan",
    "rancangan",
    "draf",
    "draft",
    "legal drafting",
    "konsiderans",
    "menimbang",
    "mengingat",
    "susun pasal",
    "buatkan pasal",
    "usulan pasal",
    "naskah akademik",
    "klausul",
]

LEGAL_BASIS_KEYWORDS = [
    "pasal",
    "ayat",
    "dasar hukum",
    "landasan hukum",
    "hierarki",
    "kaidah",
    "norma",
    "ketentuan hukum",
    "subjek hukum",
    "pengecualian objek",
    "bunyi pasal",
]


def _resolve_capability_mode(question: str, requested_mode: Optional[str] = None) -> str:
    """Resolve active capability mode from explicit user selection or prompt intent."""
    q_lower = question.lower()
    if any(k in q_lower for k in DRAFTING_KEYWORDS):
        return "perumusan_hukum"
    if any(k in q_lower for k in LEGAL_BASIS_KEYWORDS):
        return "pasal_hukum"
    if requested_mode and requested_mode in CAPABILITY_MODES:
        return requested_mode
    return "konsultasi"


def _detect_cross_theme(question: str, active_tema: str) -> Optional[str]:
    """Check if the user prompt targets a different regional tax category."""
    q_lower = question.lower()
    active_hits = sum(1 for kw in THEME_KEYWORDS.get(active_tema, []) if kw in q_lower)
    if active_hits > 0:
        return None

    best_theme: Optional[str] = None
    best_score = 0
    for code, kws in THEME_KEYWORDS.items():
        if code == active_tema:
            continue
        score = sum(1 for kw in kws if kw in q_lower)
        if score > best_score:
            best_score = score
            best_theme = code

    return best_theme if best_score > 0 else None


def _generate_follow_ups(question: str, tema: str, mode_kapabilitas: str = "konsultasi") -> List[str]:
    """Return 3 contextual follow-up queries for the active tax theme and capability mode."""
    q_lower = question.lower()

    if mode_kapabilitas == "perumusan_hukum":
        drafting_prompts: Dict[str, List[str]] = {
            "PBB-P2": [
                "Rumuskan draf pasal insentif pengurangan PBB-P2 untuk bangunan hijau (Green Building) di DKI Jakarta",
                "Susun konsiderans Menimbang & Mengingat untuk Pergub Pembebasan PBB-P2 Hunian di bawah Rp 2 Miliar",
                "Tampilkan pasal induk acuan dasar pengenaan dan NJOPTKP PBB-P2 DKI Jakarta",
            ],
            "PBJT": [
                "Rumuskan draf pasal kewajiban alat perekam transaksi elektronik (e-POS) untuk Wajib Pajak PBJT Restoran",
                "Susun konsiderans & rancangan pasal batas omzet UMKM yang dikecualikan dari PBJT Makanan/Minuman",
                "Tampilkan dasar hukum tarif 10% dan 40% pada PBJT DKI Jakarta",
            ],
            "BPHTB": [
                "Rumuskan draf pasal pemberian insentif BPHTB 0% bagi kepemilikan rumah pertama masyarakat di DKI",
                "Susun rancangan pasal integrasi validasi SSPD-BPHTB elektronik dengan sistem PPAT dan BPN",
                "Tampilkan bunyi pasal objek dan NPOPTKP BPHTB Waris vs Jual Beli",
            ],
            "REKLAME": [
                "Rumuskan draf pasal penataan reklame LED Videotron pada Kawasan Kendali Ketat DKI Jakarta",
                "Susun konsiderans & pasal indeks Nilai Sewa Reklame (NSR) untuk media digital luar ruang",
                "Tampilkan bunyi pasal dasar pengenaan dan tarif 25% Pajak Reklame",
            ],
            "PAT": [
                "Rumuskan draf pasal pembatasan pengambilan air tanah pada zona penurunan tanah kritis di DKI",
                "Susun rancangan pasal kewajiban meter air otomatis (AMR) bagi industri Wajib Pajak Air Tanah",
                "Tampilkan dasar hukum rumus NPAT dan tarif 20% Pajak Air Tanah",
            ],
        }
        candidates = drafting_prompts.get(tema, drafting_prompts["PBB-P2"])
        filtered = [p for p in candidates if p.lower()[:22] not in q_lower]
        return (filtered or candidates)[:3]

    if mode_kapabilitas == "pasal_hukum":
        legal_prompts: Dict[str, List[str]] = {
            "PBB-P2": [
                "Tampilkan bunyi pasal objek, subjek, dan pengecualian PBB-P2 di DKI Jakarta",
                "Apa dasar hukum batas NJOPTKP Rp 60 juta dan pembebasan PBB-P2 100%?",
                "Rumuskan draf pasal baru untuk insentif PBB-P2 bangunan pendidikan & kesehatan",
            ],
            "PBJT": [
                "Tampilkan bunyi pasal ruang lingkup 5 sektor objek PBJT di DKI Jakarta",
                "Apa dasar hukum pembedaan tarif PBJT 10% (Restoran/Hotel) dan 40% (Hiburan Tertentu)?",
                "Rumuskan draf pasal pengawasan pelaporan e-SPTPD PBJT berbasis sistem elektronik",
            ],
            "BPHTB": [
                "Tampilkan bunyi pasal objek perolehan hak dan perhitungan NPOPKP pada BPHTB",
                "Apa dasar hukum penetapan NPOPTKP Rp 80 Juta (Umum) dan Rp 350 Juta (Waris)?",
                "Rumuskan draf pasal keringanan BPHTB untuk program hunian terjangkau di DKI Jakarta",
            ],
            "REKLAME": [
                "Tampilkan bunyi pasal penyelenggaraan reklame pada Kawasan Kendali Ketat DKI",
                "Apa dasar hukum perhitungan Nilai Sewa Reklame (NSR) dan tarif 25%?",
                "Rumuskan draf pasal sanksi administratif bagi reklame tanpa SKPD di jalan protokol",
            ],
            "PAT": [
                "Tampilkan bunyi pasal objek Pajak Air Tanah dan pengecualian rumah tangga",
                "Apa dasar hukum komponen Sumber Daya Alam pada perhitungan NPAT?",
                "Rumuskan draf pasal zona konservasi air tanah dan transisi perpipaan di DKI Jakarta",
            ],
        }
        candidates = legal_prompts.get(tema, legal_prompts["PBB-P2"])
        filtered = [p for p in candidates if p.lower()[:22] not in q_lower]
        return (filtered or candidates)[:3]

    prompts_by_theme: Dict[str, List[str]] = {
        "PBB-P2": [
            "Tampilkan objek PBB-P2 DKI yang masih menunggak beserta dendanya",
            "Tampilkan bunyi pasal & dasar hukum NJOPTKP serta pembebasan PBB-P2 100%",
            "Rumuskan draf pasal insentif pengurangan PBB-P2 untuk bangunan ramah lingkungan",
            "Rekapitulasi realisasi PBB-P2 DKI Jakarta per Kota Administrasi",
        ],
        "PBJT": [
            "Daftar Wajib Pajak PBJT yang belum lunas beserta denda e-SPTPD",
            "Tampilkan bunyi pasal & dasar hukum tarif PBJT Restoran (10%) dan Hiburan (40%)",
            "Rumuskan draf pasal kewajiban perekam transaksi online untuk PBJT Restoran",
            "Rekapitulasi ketetapan dan realisasi PBJT per Kota Administrasi",
        ],
        "BPHTB": [
            "Berapa perbandingan NPOPTKP Jual Beli (Rp 80 Juta) vs Waris (Rp 350 Juta)?",
            "Tampilkan bunyi pasal & dasar hukum objek BPHTB serta tarif 5%",
            "Rumuskan draf pasal insentif BPHTB untuk perolehan rumah pertama di DKI Jakarta",
            "Cek transaksi SSPD BPHTB yang belum tervalidasi / belum lunas",
        ],
        "REKLAME": [
            "Cek SKPD Reklame yang belum lunas beserta rincian dendanya",
            "Tampilkan bunyi pasal Kawasan Kendali Ketat dan tarif 25% Pajak Reklame",
            "Rumuskan draf pasal pengaturan reklame LED pada gedung protokol DKI Jakarta",
            "Rekapitulasi ketetapan dan realisasi Pajak Reklame DKI Jakarta",
        ],
        "PAT": [
            "Tampilkan SKPD Pajak Air Tanah yang masih menunggak di DKI",
            "Tampilkan bunyi pasal perhitungan NPAT dan tarif 20% Pajak Air Tanah",
            "Rumuskan draf pasal pengendalian pengambilan air tanah industri di DKI Jakarta",
            "Rekapitulasi ketetapan dan realisasi Pajak Air Tanah per wilayah",
        ],
    }
    candidates = prompts_by_theme.get(tema, prompts_by_theme["PBB-P2"])
    filtered = [p for p in candidates if p.lower()[:22] not in q_lower]
    return (filtered or candidates)[:3]


def strip_prior_thinking_blocks(content: str) -> str:
    # Strip prior <|think|> and <think> blocks from multi-turn history to prevent KV cache OOM on 8GB VRAM.
    cleaned = re.sub(r"<\|think\|>.*?<\|/think\|>", "", content, flags=re.DOTALL)
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.replace("<|think|>", "").replace("<|/think|>", "")
    return cleaned.strip()


def build_thematic_system_prompt(tema_pajak: str, mode_kapabilitas: str = "konsultasi") -> str:
    theme_info = TAX_THEMES.get(tema_pajak.upper(), TAX_THEMES["PBB-P2"])
    theme_code = theme_info["code"]
    theme_name = theme_info["name"]

    base_rules = (
        f"<|think|>\n"
        f"Anda adalah **Jakarta SmartTax 2026** (dikembangkan oleh **Tim AI Jakarta SmartTax 2026** — Bapenda Provinsi DKI Jakarta) "
        f"pada kategori **{theme_name}**.\n"
        f"PRINSIP ANTI-HALUSINASI (STRICT GROUNDED RAG):\n"
        f"1. Seluruh angka tarif, rumus, data objek pajak, bunyi pasal, maupun acuan perumusan hukum WAJIB bersumber 100% dari KONTEKS DATA LOKAL DKI JAKARTA yang disuntikkan di bawah.\n"
        f"2. Dilarang keras mengarang angka, mengarang nomor pasal di luar konteks lokal, atau mengambil asumsi dari internet.\n"
        f"3. Jika pengguna menanyakan kategori pajak lain di luar **{theme_code}**, sampaikan secara singkat bahwa ruang percakapan sedang fokus pada **{theme_code}** dan sarankan menekan tombol pindah kategori di bawah pesan.\n"
    )

    if mode_kapabilitas == "perumusan_hukum":
        return (
            base_rules
            + f"4. Anda sedang berada dalam **Mode Perumusan Dasar Hukum (Legal Drafting AI)**. Susun rumusan regulasi secara sistematis meliputi:\n"
            f"   - **Judul Rancangan Instrumen** (Peraturan Gubernur / Keputusan Kepala Bapenda)\n"
            f"   - **Konsiderans Menimbang** (Landasan Filosofis, Sosiologis, dan Yuridis)\n"
            f"   - **Dasar Hukum Mengingat** (Mengacu pada korpus pasal lokal {theme_code})\n"
            f"   - **Rumusan Batang Tubuh (Pasal & Ayat)** yang terstruktur, normatif, dan selaras dengan tarif/ketentuan lokal {theme_code}\n"
            f"   - **Catatan Harmonisasi & Mitigasi Risiko Hukum**."
        )

    if mode_kapabilitas == "pasal_hukum":
        return (
            base_rules
            + f"4. Anda sedang berada dalam **Mode Telusur Pasal & Dasar Hukum**. Tampilkan secara rinci:\n"
            f"   - **Kode & Nomor Pasal/Ayat** beserta Bab/Bagiannya dari korpus hukum lokal {theme_code}\n"
            f"   - **Bunyi Norma Hukum** per ayat secara utuh dan akurat\n"
            f"   - **Kaidah Perumusan / Implikasi Pelaksanaan** bagi Wajib Pajak maupun Bapenda DKI Jakarta."
        )

    return (
        base_rules
        + f"4. Sajikan jawaban yang lugas, akurat, dan mudah dipahami dalam tabel Markdown yang rapi."
    )


def _run_local_pre_lookup(
    question: str, tema_pajak: str, mode_kapabilitas: str = "konsultasi"
) -> List[Dict[str, Any]]:
    """Query SQLite tables (tax records, tariff chunks, legal corpus, and drafting engine) scoped to the active theme."""
    q_lower = question.lower()
    tema = tema_pajak.upper() if tema_pajak.upper() in TAX_THEMES else "PBB-P2"
    tool_outputs: List[Dict[str, Any]] = []

    if mode_kapabilitas == "perumusan_hukum" or any(k in q_lower for k in DRAFTING_KEYWORDS):
        draft_pack = susun_rancangan_hukum_dki(topik_perumusan=question, tema_pajak=tema)
        tool_outputs.append(
            {"tool": "susun_rancangan_hukum_dki", "tema": tema, "data": draft_pack}
        )

    if (
        mode_kapabilitas in ("pasal_hukum", "perumusan_hukum")
        or any(k in q_lower for k in LEGAL_BASIS_KEYWORDS)
    ):
        pasal_rows = json.loads(telusuri_pasal_hukum_dki(kata_kunci=question, tema_pajak=tema))
        if pasal_rows:
            tool_outputs.append(
                {"tool": "telusuri_pasal_hukum_dki", "tema": tema, "data": pasal_rows}
            )

    if any(k in q_lower for k in ["tunggakan", "belum lunas", "menunggak", "denda", "telat", "terlambat"]):
        res = json.loads(daftar_tunggakan_pajak_dki(tema_pajak=tema))
        tool_outputs.append({"tool": "daftar_tunggakan_pajak_dki", "tema": tema, "data": res})

    if any(k in q_lower for k in ["rekap", "total", "realisasi", "ringkasan", "kecamatan", "kelurahan", "kota", "wilayah"]):
        res = json.loads(rekapitulasi_pajak_dki(tema_pajak=tema))
        tool_outputs.append({"tool": "rekapitulasi_pajak_dki", "tema": tema, "data": res})

    theme_rows = get_all_sppt_records(tema_pajak=tema)
    matched_rows = []
    for r in theme_rows:
        for field in (
            r["nomor_identitas"],
            r["nama_wp"],
            r["nama_objek"],
            r["kelurahan"],
            r["kecamatan"],
            r["kota_administrasi"],
            r["alamat_objek"],
            r["kategori_subjek"],
        ):
            tokens = [
                t
                for t in re.split(r"[\s,\.\-/()]+", field.lower())
                if len(t) >= 3 and t not in ("jalan", "jakarta", "dki", "dan", "pajak", "pbjt", "pbb", "kota", "adm")
            ]
            if any(t in q_lower for t in tokens):
                matched_rows.append(r)
                break

    if (
        not matched_rows
        and mode_kapabilitas == "konsultasi"
        and any(k in q_lower for k in ["tampilkan", "lihat", "daftar", "semua", "cek", "contoh", "data", "objek"])
    ):
        matched_rows = theme_rows

    if matched_rows:
        tool_outputs.append({"tool": "cari_data_pajak_dki", "tema": tema, "data": matched_rows})

    reg_chunks = get_regulasi_chunks(tema_pajak=tema)
    if reg_chunks:
        tool_outputs.append({"tool": "regulasi_dki_lokal", "tema": tema, "data": reg_chunks})

    return tool_outputs


def _build_conversational_greeting_reply(
    question: str, tema: str, theme_name: str, mode_kapabilitas: str
) -> Optional[str]:
    q_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", question.lower()).strip()
    tokens = q_clean.split()
    if not tokens or len(tokens) > 7:
        return None

    greeting_phrases = {
        "halo",
        "hai",
        "hi",
        "hello",
        "pagi",
        "siang",
        "sore",
        "malam",
        "selamat pagi",
        "selamat siang",
        "selamat sore",
        "selamat malam",
        "assalamualaikum",
        "permisi",
        "tes",
        "test",
        "ping",
        "apa kabar",
        "siapa kamu",
        "bisa bantu apa",
    }
    thanks_phrases = {"terima kasih", "makasih", "thanks", "thank you", "oke terima kasih"}

    if q_clean in thanks_phrases or (len(tokens) <= 3 and any(t in {"makasih", "thanks"} for t in tokens)):
        return (
            f"Sama-sama! Senang dapat membantu Anda terkait **{theme_name}**. "
            f"Silakan beri tahu saya jika ada simulasi perhitungan pajak, pengecekan NOP/NPWPD, atau pasal regulasi DKI Jakarta lainnya yang ingin Anda tanyakan."
        )

    is_greeting = q_clean in greeting_phrases or (
        len(tokens) <= 4
        and any(
            t in {"halo", "hai", "hi", "hello", "pagi", "siang", "sore", "malam", "tes", "test", "assalamualaikum"}
            for t in tokens
        )
        and not any(
            kw in q_clean
            for kw in ["tarif", "rumus", "pasal", "denda", "tunggakan", "njop", "npoptkp", "pbb", "pbjt", "bphtb", "reklame", "pat"]
        )
    )
    if not is_greeting:
        return None

    examples_by_theme = {
        "PBB-P2": (
            "- *\"Berapa batas NJOPTKP dan syarat pembebasan 100% PBB-P2 rumah tinggal di DKI Jakarta?\"*\n"
            "- *\"Tampilkan objek PBB-P2 DKI yang masih menunggak beserta dendanya\"*\n"
            "- *\"Bagaimana perhitungan PBB-P2 untuk rumah tinggal dengan NJOP Rp 3,5 Miliar?\"*"
        ),
        "PBJT": (
            "- *\"Berapa tarif PBJT Makanan/Minuman (Restoran), Perhotelan, dan Hiburan di DKI Jakarta?\"*\n"
            "- *\"Daftar Wajib Pajak PBJT yang belum lunas beserta denda e-SPTPD\"*\n"
            "- *\"Tampilkan bunyi pasal ruang lingkup 5 sektor objek PBJT di DKI Jakarta\"*"
        ),
        "BPHTB": (
            "- *\"Berapa perbandingan NPOPTKP Jual Beli (Rp 80 Juta) vs Waris (Rp 350 Juta)?\"*\n"
            "- *\"Hitung BPHTB Waris untuk rumah tinggal di Jakarta Selatan dengan NJOP Rp 2,4 Miliar\"*\n"
            "- *\"Tampilkan bunyi pasal objek perolehan hak pada BPHTB DKI Jakarta\"*"
        ),
        "REKLAME": (
            "- *\"Berapa tarif Pajak Reklame dari Nilai Sewa Reklame (NSR) dan aturan Kawasan Kendali Ketat?\"*\n"
            "- *\"Cek SKPD Reklame yang belum lunas beserta rincian dendanya\"*\n"
            "- *\"Tampilkan bunyi pasal penyelenggaraan reklame pada Kawasan Kendali Ketat DKI\"*"
        ),
        "PAT": (
            "- *\"Bagaimana rumus NPAT, tarif 20% Pajak Air Tanah, dan kewajiban meter air AMR?\"*\n"
            "- *\"Tampilkan SKPD Pajak Air Tanah yang masih menunggak di DKI Jakarta\"*\n"
            "- *\"Tampilkan bunyi pasal objek Pajak Air Tanah dan pengecualian rumah tangga\"*"
        ),
    }
    examples = examples_by_theme.get(tema, examples_by_theme["PBB-P2"])
    return (
        f"Halo! Saya **Asisten AI Jakarta SmartTax 2026** untuk layanan **{theme_name}** Bapenda Provinsi DKI Jakarta.\n\n"
        f"Saat ini Anda berada pada kategori **{tema}**. Anda dapat langsung menanyakan simulasi perhitungan pajak, pengecekan tunggakan objek pajak, maupun bunyi pasal regulasi resmi. Contoh pertanyaan yang bisa Anda ketik:\n"
        f"{examples}"
    )


def _build_local_deterministic_answer(
    question: str,
    tema_pajak: str,
    qdrant_hits: List[Dict[str, Any]],
    tool_outputs: List[Dict[str, Any]],
    suggested_theme: Optional[str] = None,
    mode_kapabilitas: str = "konsultasi",
    chroma_hits: Optional[List[Any]] = None,
) -> str:
    """Format a 100% grounded Markdown response from local SQLite and Qdrant results (Zero-Hallucination Engine)."""
    tema = tema_pajak.upper() if tema_pajak.upper() in TAX_THEMES else "PBB-P2"
    theme_name = TAX_THEMES[tema]["name"]
    lines: List[str] = []
    q_lower = question.lower()

    greeting_reply = _build_conversational_greeting_reply(
        question, tema, theme_name, mode_kapabilitas
    )
    if greeting_reply:
        return greeting_reply

    if suggested_theme and suggested_theme in TAX_THEMES:
        target_name = TAX_THEMES[suggested_theme]["name"]
        return (
            f"Pertanyaan Anda berkaitan dengan **{target_name}**, sedangkan ruang percakapan ini sedang berada pada kategori **{theme_name}**.\n\n"
            f"Silakan klik tombol **Pindah ke {suggested_theme}** di bawah pesan ini untuk langsung menanyakan ulang pada korpus data & dasar hukum **{suggested_theme} DKI Jakarta**."
        )

    # 1. Mode Perumusan Dasar Hukum (Legal Drafting Engine)
    for t in tool_outputs:
        if t["tool"] == "susun_rancangan_hukum_dki":
            d = t["data"]
            acuan_list = d.get("pasal_induk_acuan", [])
            lines.append(f"### Rancangan Perumusan Dasar Hukum ({tema} — DKI Jakarta)")
            lines.append(
                f"Berikut draf rumusan regulasi yang disusun secara ketat berdasarkan **Korpus Hukum Lokal {theme_name}**:\n\n"
                f"**Bentuk Instrumen:** {d['instrumen_disarankan']}\n"
                f"**Fokus Pengaturan:** *{d['topik_perumusan']}*"
            )
            lines.append(
                "#### 1. Konsiderans `MENIMBANG`\n"
                + "\n".join(f"- {m}" for m in d["konsiderans_menimbang"])
            )
            lines.append(
                "#### 2. Dasar Hukum `MENGINGAT` (Pasal Induk Terkait)\n"
                + "\n".join(f"- **{m}**" for m in d["dasar_hukum_mengingat"])
            )

            lines.append("#### 3. Rancangan Batang Tubuh (Pasal & Ayat)")
            lines.append(
                f"**Pasal 1 — Ruang Lingkup & Subjek Pengaturan**\n"
                f"(1) Pengaturan dalam ketentuan ini berlaku terhadap objek dan subjek **{theme_name}** di wilayah Provinsi DKI Jakarta.\n"
                f"(2) Pelaksanaan pemungutan, verifikasi, dan pengawasan mengacu pada basis data perpajakan daerah Bapenda Provinsi DKI Jakarta.\n\n"
                f"**Pasal 2 — Norma Pokok & Ketentuan Tarif / Insentif**\n"
                f"(1) Dalam rangka optimalisasi penerimaan daerah dan keadilan fiskal terkait *{d['topik_perumusan']}*, pengenaan **{tema}** dilaksanakan sesuai batasan tarif dan dasar pengenaan yang berlaku di Provinsi DKI Jakarta.\n"
                f"(2) Pemberian keringanan, pengurangan, atau tata cara pelaporan elektronik diverifikasi secara sistem melalui portal resmi pajak daerah DKI Jakarta.\n\n"
                f"**Pasal 3 — Pengawasan & Sanksi Administratif**\n"
                f"(1) Wajib Pajak yang tidak memenuhi kewajiban pelaporan atau pembayaran sesuai jatuh tempo dikenakan sanksi administratif sesuai ketentuan peraturan perpajakan daerah.\n"
                f"(2) Ketentuan ini mulai berlaku pada tanggal ditetapkan."
            )

            if acuan_list:
                lines.append("#### 4. Matriks Harmonisasi Pasal Induk Acuan")
                lines.append("| Kode Korpus | Pasal & Ayat Induk | Topik Norma | Kaidah Perumusan (Legal Drafting) |")
                lines.append("| :--- | :--- | :--- | :--- |")
                for ac in acuan_list:
                    lines.append(
                        f"| `{ac['kode_pasal']}` | **{ac['pasal_ayat']}** | {ac['tentang']} | {ac['kaidah_perumusan']} |"
                    )
            return "\n\n".join(lines)

    # 2. Mode Telusur Pasal & Dasar Hukum
    for t in tool_outputs:
        if t["tool"] == "telusuri_pasal_hukum_dki" and (
            mode_kapabilitas == "pasal_hukum" or any(k in q_lower for k in LEGAL_BASIS_KEYWORDS)
        ):
            pasal_list = t["data"]
            lines.append(f"### Korpus Pasal & Dasar Hukum {theme_name} — DKI Jakarta")
            for p in pasal_list:
                lines.append(
                    f"#### `{p['kode_pasal']}` — {p['pasal_ayat']}: {p['tentang']}\n"
                    f"- **Instrumen & Bagian:** {p['jenis_instrumen']} ({p['bab_bagian']})\n"
                    f"- **Bunyi Norma Hukum:**\n"
                    + "\n".join(f"  > {ln}" for ln in p["bunyi_norma"].split("\n"))
                    + f"\n- **Kaidah Perumusan / Implikasi Regulasi:** {p['kaidah_perumusan']}"
                )

    # 3. Data Tunggakan
    for t in tool_outputs:
        if t["tool"] == "daftar_tunggakan_pajak_dki":
            d = t["data"]
            lines.append(f"### Daftar Tunggakan {theme_name} — DKI Jakarta")
            lines.append(
                f"Terdapat **{d['jumlah_objek_belum_lunas']} objek pajak** yang tercatat belum lunas pada arsip lokal Bapenda DKI Jakarta:\n\n"
                f"- **Pokok Pajak Tertunggak:** Rp {d['total_pokok_pajak_rp']:,}\n"
                f"- **Akumulasi Denda:** Rp {d['total_denda_rp']:,}\n"
                f"- **Total Tagihan Keseluruhan:** **Rp {d['total_tagihan_keseluruhan_rp']:,}**\n"
            )
            if d["daftar_tunggakan"]:
                lines.append("| Nomor Identitas | Wajib Pajak & Objek | Wilayah DKI Jakarta | Masa/Tahun | Pokok Pajak | Denda | Total Tagihan |")
                lines.append("| :--- | :--- | :--- | :---: | ---: | ---: | ---: |")
                for item in d["daftar_tunggakan"]:
                    lines.append(
                        f"| `{item['nomor_identitas']}` | **{item['nama_wp']}** ({item['nama_objek']}) | {item['kecamatan']}, {item['kota_administrasi']} | {item['masa_atau_tahun_pajak']} | Rp {item['pokok_pajak_rp']:,} | Rp {item['denda_rp']:,} | **Rp {item['total_tagihan_rp']:,}** |"
                    )

    # 4. Rekapitulasi Wilayah
    for t in tool_outputs:
        if t["tool"] == "rekapitulasi_pajak_dki":
            d = t["data"]
            tot = d.get("ringkasan_total", {})
            lines.append(f"### Rekapitulasi {theme_name} per Wilayah — DKI Jakarta")
            lines.append(
                f"- **Cakupan Objek Terdaftar:** {tot.get('total_objek', 0)} Objek "
                f"({tot.get('objek_lunas', 0)} Lunas • {tot.get('objek_belum_lunas', 0)} Belum Lunas)\n"
                f"- **Total Ketetapan Pokok:** Rp {tot.get('total_ketetapan_rp', 0):,}\n"
                f"- **Realisasi Penerimaan (Lunas):** Rp {tot.get('total_realisasi_lunas_rp', 0):,}\n"
                f"- **Sisa Piutang + Denda:** Rp {tot.get('total_tunggakan_dan_denda_rp', 0):,}\n"
            )
            lines.append("| Kota Administrasi | Kecamatan | Objek | Ketetapan Pokok | Realisasi Lunas | Sisa Tagihan + Denda |")
            lines.append("| :--- | :--- | :---: | ---: | ---: | ---: |")
            for w in d.get("rekap_per_wilayah", []):
                lines.append(
                    f"| {w['kota_administrasi']} | {w['kecamatan']} | {w['jumlah_objek']} | Rp {w['total_ketetapan_rp']:,} | Rp {w['realisasi_lunas_rp']:,} | **Rp {w['total_sisa_tagihan_rp']:,}** |"
                )

    # 5. Pencarian Objek Pajak
    for t in tool_outputs:
        if t["tool"] == "cari_data_pajak_dki" and t["data"] and not lines:
            lines.append(f"### Rincian Objek {theme_name} — DKI Jakarta")
            lines.append("| Nomor Identitas | Wajib Pajak & Objek | Wilayah DKI | DPP / NJOP | Pokok Pajak | Denda | Status |")
            lines.append("| :--- | :--- | :--- | ---: | ---: | ---: | :--- |")
            for r in t["data"]:
                lines.append(
                    f"| `{r['nomor_identitas']}` | **{r['nama_wp']}** — {r['nama_objek']} | {r['kelurahan']}, {r['kota_administrasi']} | Rp {r['dpp_atau_njop_rp']:,} | Rp {r['pokok_pajak_rp']:,} | Rp {r['denda_rp']:,} | **{r['status_bayar']}** |"
                )
                if len(t["data"]) == 1 and r.get("keterangan"):
                    lines.append(f"\n> **Catatan Ketetapan:** {r['keterangan']} (Jatuh Tempo: `{r['jatuh_tempo']}`)")

    if chroma_hits:
        strong_chroma = [
            h for h in chroma_hits if getattr(h, "similarity", 0.0) >= 0.32
        ]
        for h in strong_chroma[:2]:
            src_type = getattr(h, "source_type", "")
            if src_type == "user_reasoning":
                lines.append(
                    f"### Referensi Penalaran Kasus ({h.doc_name})\n{h.text}"
                )
            elif src_type in ("pdf_regulasi", "excel_data") and not lines:
                lines.append(
                    f"### Kutipan Korpus Pengetahuan ({h.doc_name})\n{h.text}"
                )

    # 6. Ketentuan Tarif & Rumus
    if any(k in q_lower for k in ["tarif", "rumus", "njoptkp", "npoptkp", "denda", "jatuh tempo", "aturan", "ketentuan", "insentif", "bebas", "hitung", "syarat", "berapa", "bagaimana", "jelaskan"]):
        for t in tool_outputs:
            if t["tool"] == "regulasi_dki_lokal":
                for reg in t["data"]:
                    lines.append(reg["content"])

    if not lines:
        lines.append(
            f"Pertanyaan Anda belum spesifik merujuk pada objek pajak atau topik regulasi di kategori **{theme_name}**.\n\n"
            f"Silakan sebutkan **Nomor Objek Pajak (NOP/NPWPD)**, **nama gedung/wajib pajak**, **wilayah kecamatan**, atau tanyakan tentang **tarif, rumus perhitungan, tunggakan, maupun pasal regulasi {tema} DKI Jakarta**."
        )

    return "\n\n".join(lines)


async def stream_smarttax_chat(
    user_message: str,
    history: List[Dict[str, str]],
    model: str = DEFAULT_CHAT_MODEL,
    tema_pajak: str = "PBB-P2",
    mode_kapabilitas: str = "konsultasi",
) -> AsyncGenerator[str, None]:
    """Stream NDJSON response chunks for the selected DKI Jakarta tax theme and capability mode (Gemma / DeepSeek RAG)."""
    start_ts = time.perf_counter()
    tema = tema_pajak.upper() if (tema_pajak and tema_pajak.upper() in TAX_THEMES) else "PBB-P2"
    theme_label = TAX_THEMES[tema]["name"]
    resolved_mode = _resolve_capability_mode(user_message, mode_kapabilitas)
    mode_info = CAPABILITY_MODES.get(resolved_mode, CAPABILITY_MODES["konsultasi"])

    selected_model = model
    if resolved_mode == "perumusan_hukum" and model == DEFAULT_CHAT_MODEL:
        selected_model = DEEPSEEK_DRAFTING_MODEL

    greeting_reply = _build_conversational_greeting_reply(
        user_message, tema, theme_label, resolved_mode
    )
    if greeting_reply:
        follow_ups = _generate_follow_ups(user_message, tema, mode_kapabilitas=resolved_mode)
        words = re.split(r"(\s+)", greeting_reply)
        batch = ""
        for w in words:
            batch += w
            if len(batch) >= 24:
                yield json.dumps({"type": "token", "delta": batch}, ensure_ascii=False) + "\n"
                batch = ""
                await asyncio.sleep(0.008)
        if batch:
            yield json.dumps({"type": "token", "delta": batch}, ensure_ascii=False) + "\n"
        elapsed = round(time.perf_counter() - start_ts, 2)
        yield json.dumps(
            {
                "type": "done",
                "elapsed_sec": elapsed,
                "model": selected_model,
                "tema_pajak": tema,
                "mode_kapabilitas": resolved_mode,
                "mode_label": mode_info["label"],
                "suggested_theme": None,
                "follow_ups": follow_ups,
                "response_source": "conversational_greeting",
            },
            ensure_ascii=False,
        ) + "\n"
        return

    status_stage_1 = {
        "konsultasi": f"Menelusuri arsip data & tarif {tema} Bapenda DKI Jakarta...",
        "pasal_hukum": f"Menelusuri korpus pasal & dasar hukum {tema} DKI Jakarta...",
        "perumusan_hukum": f"Menyusun kerangka konsiderans & rancangan pasal {tema} DKI Jakarta...",
    }.get(resolved_mode, f"Menelusuri arsip {tema} Bapenda DKI Jakarta...")

    yield json.dumps(
        {"type": "status", "text": status_stage_1},
        ensure_ascii=False,
    ) + "\n"

    suggested_theme = _detect_cross_theme(user_message, tema)
    preferred_doc_type = (
        "pasal_hukum" if resolved_mode in ("pasal_hukum", "perumusan_hukum") else None
    )
    qdrant_hits = vector_store.search(
        user_message, limit=6, tema_pajak=tema, doc_type=preferred_doc_type
    )
    if not qdrant_hits:
        qdrant_hits = vector_store.search(user_message, limit=6, tema_pajak=tema)

    chroma_hits = chroma_store.query_knowledge(
        user_message, top_k=4, tema_pajak=tema
    )

    pre_tool_outputs = _run_local_pre_lookup(
        user_message, tema_pajak=tema, mode_kapabilitas=resolved_mode
    )
    sql_tools_used = [t["tool"] for t in pre_tool_outputs]
    follow_ups = _generate_follow_ups(user_message, tema, mode_kapabilitas=resolved_mode)

    await asyncio.sleep(0.08)
    status_stage_2 = {
        "konsultasi": f"Mencocokkan rincian objek & ketetapan {tema}...",
        "pasal_hukum": f"Memverifikasi bunyi pasal & norma regulasi {tema}...",
        "perumusan_hukum": f"Menyelaraskan draf batang tubuh pasal dengan korpus {tema}...",
    }.get(resolved_mode, f"Mencocokkan rincian {tema}...")

    yield json.dumps(
        {"type": "status", "text": status_stage_2},
        ensure_ascii=False,
    ) + "\n"

    yield json.dumps(
        {
            "type": "sources",
            "tema_pajak": tema,
            "mode_kapabilitas": resolved_mode,
            "mode_label": mode_info["label"],
            "suggested_theme": suggested_theme,
            "qdrant_sources": qdrant_hits,
            "chroma_sources": [h.model_dump() for h in chroma_hits],
            "sql_tools_used": sql_tools_used,
        },
        ensure_ascii=False,
    ) + "\n"

    if suggested_theme:
        deterministic_text = _build_local_deterministic_answer(
            user_message,
            tema,
            qdrant_hits,
            pre_tool_outputs,
            suggested_theme=suggested_theme,
            mode_kapabilitas=resolved_mode,
        )
        words = re.split(r"(\s+)", deterministic_text)
        batch = ""
        for idx, w in enumerate(words):
            batch += w
            if idx % 5 == 0 or idx == len(words) - 1:
                yield json.dumps({"type": "token", "delta": batch}, ensure_ascii=False) + "\n"
                batch = ""
                await asyncio.sleep(0.012)

        elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
        yield json.dumps(
            {
                "type": "done",
                "tema_pajak": tema,
                "mode_kapabilitas": resolved_mode,
                "suggested_theme": suggested_theme,
                "follow_ups": follow_ups,
                "model_used": selected_model,
                "response_source": "local_routing",
                "duration_ms": elapsed_ms,
            },
            ensure_ascii=False,
        ) + "\n"
        return

    context_blocks: List[str] = [
        f"KATEGORI PAJAK AKTIF: {theme_label} — PROVINSI DKI JAKARTA",
        f"MODE KAPABILITAS AKTIF: {mode_info['label']} ({resolved_mode})",
    ]
    if chroma_hits:
        context_blocks.append(
            f"=== KORPUS PENGETAHUAN CHROMADB LOKAL ({tema} DKI JAKARTA) ===\n"
            + "\n\n".join(
                [
                    f"[{h.source_type.upper()} | doc={h.doc_name} | sim={h.similarity}]\n{h.text}"
                    for h in chroma_hits
                ]
            )
        )
    if pre_tool_outputs:
        context_blocks.append(
            f"=== DATA TERSTRUKTUR & KORPUS HUKUM SQLITE LOKAL ({tema} DKI JAKARTA) ===\n"
            + json.dumps(pre_tool_outputs, ensure_ascii=False, indent=2)
        )
    if qdrant_hits:
        context_blocks.append(
            f"=== DOKUMEN VEKTOR QDRANT LOKAL ({tema} DKI JAKARTA) ===\n"
            + "\n\n".join(
                [
                    f"[{h['doc_type'].upper()} | score={h['score']}] {h['title']}\n{h['text']}"
                    for h in qdrant_hits
                ]
            )
        )

    grounded_user_prompt = (
        f"KONTEKS DATA & KORPUS HUKUM LOKAL BAPENDA DKI JAKARTA:\n"
        f"{chr(10).join(context_blocks)}\n\n"
        f"PERTANYAAN / INSTRUKSI PENGGUNA (Tema: {tema} | Mode: {mode_info['label']}):\n{user_message}\n\n"
        f"Jawab atau rumuskan draf hukum HANYA berdasarkan konteks data & korpus pasal lokal {tema} DKI Jakarta di atas (Zero-Hallucination)."
    )

    system_prompt = build_thematic_system_prompt(tema, mode_kapabilitas=resolved_mode)
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for msg in history[-6:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            clean_hist_content = strip_prior_thinking_blocks(str(msg["content"]))
            if clean_hist_content:
                messages.append({"role": msg["role"], "content": clean_hist_content})
    messages.append({"role": "user", "content": grounded_user_prompt})

    use_direct_cloud = bool(OLLAMA_API_KEY) and (
        ":cloud" in selected_model or selected_model.startswith("gemma4:31b")
    )
    if use_direct_cloud:
        base_url = OLLAMA_CLOUD_URL
        api_model = "gemma4:31b" if selected_model == "gemma4:cloud" else selected_model
        headers = {"Authorization": f"Bearer {OLLAMA_API_KEY}"}
    elif "deepseek" in selected_model.lower():
        base_url = OLLAMA_SECONDARY_URL
        api_model = selected_model
        headers = {}
    else:
        base_url = OLLAMA_LOCAL_URL
        api_model = selected_model
        headers = {}

    streamed_any_token = False
    in_deepseek_think_tag = False

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(OLLAMA_TIMEOUT, connect=10.0)
        ) as client:
            async with client.stream(
                "POST",
                f"{base_url}/api/chat",
                headers=headers,
                json={
                    "model": api_model,
                    "messages": messages,
                    "stream": True,
                    **({"think": OLLAMA_THINK} if api_model.startswith("gemma4:") else {}),
                    "options": {
                        "num_ctx": OLLAMA_NUM_CTX,
                        "temperature": OLLAMA_TEMPERATURE,
                        "top_p": OLLAMA_TOP_P,
                        "top_k": OLLAMA_TOP_K,
                        "repeat_penalty": 1.1,
                    },
                },
            ) as resp:
                resp.raise_for_status()
                if resp.status_code == 200:
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except Exception:
                            continue

                        if chunk.get("error"):
                            raise RuntimeError(chunk["error"])
                        msg_part = chunk.get("message") or {}
                        thinking_delta = msg_part.get("thinking") or ""
                        content_delta = msg_part.get("content") or ""

                        if "<think>" in content_delta:
                            in_deepseek_think_tag = True
                            content_delta = content_delta.replace("<think>", "")
                        if "</think>" in content_delta:
                            parts = content_delta.split("</think>", 1)
                            if parts[0]:
                                yield json.dumps(
                                    {"type": "thinking", "delta": parts[0]},
                                    ensure_ascii=False,
                                ) + "\n"
                            in_deepseek_think_tag = False
                            content_delta = parts[1] if len(parts) > 1 else ""

                        if thinking_delta:
                            yield json.dumps(
                                {"type": "thinking", "delta": thinking_delta},
                                ensure_ascii=False,
                            ) + "\n"

                        if content_delta:
                            if in_deepseek_think_tag:
                                yield json.dumps(
                                    {"type": "thinking", "delta": content_delta},
                                    ensure_ascii=False,
                                ) + "\n"
                            else:
                                streamed_any_token = True
                                yield json.dumps(
                                    {"type": "token", "delta": content_delta},
                                    ensure_ascii=False,
                                ) + "\n"
    except Exception as exc:
        logger.warning("Ollama request failed for %s at %s: %s", api_model, base_url, exc)

    if not streamed_any_token:
        deterministic_text = _build_local_deterministic_answer(
            user_message,
            tema,
            qdrant_hits,
            pre_tool_outputs,
            suggested_theme=suggested_theme,
            mode_kapabilitas=resolved_mode,
            chroma_hits=chroma_hits,
        )
        words = re.split(r"(\s+)", deterministic_text)
        batch = ""
        for idx, w in enumerate(words):
            batch += w
            if idx % 6 == 0 or idx == len(words) - 1:
                yield json.dumps({"type": "token", "delta": batch}, ensure_ascii=False) + "\n"
                batch = ""
                await asyncio.sleep(0.014)

    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
    yield json.dumps(
        {
            "type": "done",
            "tema_pajak": tema,
            "mode_kapabilitas": resolved_mode,
            "suggested_theme": suggested_theme,
            "follow_ups": follow_ups,
            "model_used": api_model,
            "response_source": "ollama" if streamed_any_token else "local_fallback",
            "duration_ms": elapsed_ms,
        },
        ensure_ascii=False,
    ) + "\n"


async def run_smarttax_chat(
    user_message: str,
    history: List[Dict[str, str]],
    model: str = DEFAULT_CHAT_MODEL,
    tema_pajak: str = "PBB-P2",
    mode_kapabilitas: str = "konsultasi",
) -> Dict[str, Any]:
    full_text = ""
    qdrant_sources: List[Dict[str, Any]] = []
    sql_tools_used: List[str] = []
    model_used = model
    response_source = "local_fallback"
    suggested_theme: Optional[str] = None
    resolved_mode = mode_kapabilitas
    follow_ups: List[str] = []
    async for raw_line in stream_smarttax_chat(
        user_message, history, model, tema_pajak, mode_kapabilitas
    ):
        if not raw_line.strip():
            continue
        evt = json.loads(raw_line)
        if evt["type"] == "token":
            full_text += evt.get("delta", "")
        elif evt["type"] == "sources":
            qdrant_sources = evt.get("qdrant_sources", [])
            sql_tools_used = evt.get("sql_tools_used", [])
            suggested_theme = evt.get("suggested_theme")
            resolved_mode = evt.get("mode_kapabilitas", mode_kapabilitas)
        elif evt["type"] == "done":
            model_used = evt.get("model_used", model)
            response_source = evt.get("response_source", "local_fallback")
            follow_ups = evt.get("follow_ups", [])

    return {
        "answer": full_text.strip(),
        "tema_pajak": tema_pajak,
        "mode_kapabilitas": resolved_mode,
        "suggested_theme": suggested_theme,
        "follow_ups": follow_ups,
        "model_used": model_used,
        "response_source": response_source,
        "qdrant_sources": qdrant_sources,
        "sql_tools_used": sql_tools_used,
    }

