# Jakarta SmartTax 2026 — Platform AI Pajak Daerah DKI Jakarta

Repositori resmi **Tim AI Jakarta SmartTax 2026**. Proyek ini adalah platform *chat* interaktif berbasis RAG (*Retrieval-Augmented Generation*) dan pencarian SQL terstruktur untuk seluruh kategori pajak daerah **Bapenda Provinsi DKI Jakarta**:

- **PBB-P2** (Pajak Bumi dan Bangunan Perdesaan dan Perkotaan)
- **PBJT** (Pajak Barang dan Jasa Tertentu — Restoran, Perhotelan, Parkir, Kesenian & Hiburan)
- **BPHTB** (Bea Perolehan Hak atas Tanah dan Bangunan)
- **REKLAME** (Pajak Reklame — Videotron, Megatron, Billboard Kawasan Protokol & Kendali Ketat)
- **PAT** (Pajak Air Tanah — Sumur Bor Industri & Komersial)

Seluruh pemrosesan data berjalan **100% lokal (On-Premise)** tanpa mengirim data Wajib Pajak ke layanan pihak ketiga.

---

## Ringkasan Tech Stack (Frontend, Backend, Data & AI)

Supaya tim bisa langsung paham komponen apa saja yang jalan di balik layar, berikut daftar teknologi yang kita pakai:

### 1. Frontend (`frontend/`)
- **Framework:** **Next.js 15** (*App Router*) + **React 19** + **TypeScript 5**.
- **Styling & UI:** **Native CSS Custom Properties** (`src/app/globals.css`) tanpa ketergantungan *library* komponen berat. Mendukung tema *Light/Dark*, tabel angka *tabular-nums*, dan *off-canvas drawer* responsif untuk layar HP (*mobile*).
- **Streaming Client:** Menggunakan **Web `ReadableStream` API + `TextDecoder`** bawaan *browser* untuk membaca aliran token **NDJSON** (*Newline-Delimited JSON*) secara *real-time* dari backend (mirip cara kerja UI ChatGPT).
- **State & Riwayat Sesi:** Disimpan di `localStorage` *browser* (`bapenda-dki-sessions-v2`) dan otomatis dikelompokkan berdasarkan kategori pajak (`PBB-P2`, `PBJT`, `BPHTB`, `REKLAME`, `PAT`).

### 2. Backend (`backend/`)
- **Framework API:** **FastAPI** (Python 3.11+) yang dijalankan di atas server ASGI **Uvicorn**.
- **Package & Venv Manager:** Menggunakan **`uv`** agar instalasi *dependency* dan sinkronisasi `pyproject.toml` jauh lebih cepat dibanding `pip` biasa.
- **Validasi & Keamanan:** **Pydantic v2** untuk membatasi panjang *payload* (`message` maks 2.000 karakter, `history` maks 20 giliran) ditambah *middleware* HTTP Security Headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`) dan pengaturan CORS ketat.
- **Async HTTP Client:** **`httpx.AsyncClient`** untuk membuka koneksi *streaming* asinkron ke server LLM lokal.

### 3. Database Relasional & Vector Engine (`backend/data/`)
- **Database Transaksional:** **SQLite 3** (`backend/data/pbb_p2_lokal.db`) untuk menyimpan data objek pajak, NOP/NPWPD, rincian ketetapan pokok, denda keterlambatan, status pembayaran, dan aturan tarif tiap pajak.
- **Vector Database (RAG):** **Qdrant** (`qdrant-client`) dalam mode penyimpanan disk lokal (`backend/data/qdrant_storage/`). Setiap dokumen diindeks dengan filter *payload* `tema_pajak` supaya pencarian satu jenis pajak tidak tercampur dengan pajak lain.
- **Embedding Engine:** **HuggingFace `transformers` + `PyTorch`** (`sentence-transformers/all-MiniLM-L6-v2`, dimensi 384) dengan *fallback* otomatis ke *deterministic subword hashing* 384-dimensi jika server berjalan tanpa koneksi internet sama sekali (*air-gapped*).

### 4. AI / LLM Runtime
- **LLM Engine Lokal:** **Ollama** (berjalan di `http://localhost:11434`, mendukung model seperti `qwen2.5:7b-instruct` atau `llama3.1:8b`).
- **Deterministic SQL Fallback:** Jika *service* Ollama di mesin lokal belum dinyalakan, backend **tidak akan error**—sistem otomatis menyusun jawaban dan tabel Markdown langsung dari hasil *query* SQLite & Qdrant.

---

## Struktur Folder Proyek

```text
.
├── backend/
│   ├── app/
│   │   ├── config.py           # Konfigurasi env, port, CORS, dan nama koleksi Qdrant
│   │   ├── main.py             # Entrypoint FastAPI, endpoint REST + NDJSON streaming
│   │   ├── ollama_service.py   # Orkestrator RAG, deteksi pindah tema, dan streaming LLM
│   │   ├── tax_db.py           # Skema SQLite, query agregasi/tunggakan, dan seed data DKI
│   │   ├── vector_store.py     # Wrapper Qdrant lokal & filter payload per kategori pajak
│   │   └── embedder.py         # Pembangkit vektor 384-dimensi (Transformers / Subword)
│   ├── data/                   # Lokasi file .db SQLite & storage Qdrant (di-ignore Git)
│   └── pyproject.toml          # Daftar dependency Python (dikelola via uv)
├── frontend/
│   ├── src/app/
│   │   ├── layout.tsx          # Root HTML, konfigurasi font Inter, dan metadata viewport mobile
│   │   ├── page.tsx            # Komponen utama chat, dropdown kategori pajak, & parser NDJSON
│   │   └── globals.css         # Seluruh desain UI, variabel warna, dan media query mobile
│   ├── next.config.mjs         # Konfigurasi Next.js & security headers
│   └── package.json
└── docs/
    └── ENGINEERING_GUIDE.md    # Panduan teknis lengkap untuk Tim AI Jakarta SmartTax 2026
```

---

## Cara Menjalankan di Mesin Lokal

### 1. Jalankan Backend (FastAPI — Port `8000`)

Pastikan Python 3.11+ dan [`uv`](https://docs.astral.sh/uv/) sudah terpasang:

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Saat pertama kali menyala, backend otomatis membuat database SQLite di `backend/data/pbb_p2_lokal.db` dan membangun indeks vektor Qdrant di `backend/data/qdrant_storage/`.

### 2. Jalankan Frontend (Next.js — Port `3000`)

Buka terminal baru:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Buka `http://localhost:3000` di *browser*.

---

## Dokumentasi Tim Engineering

Untuk penjelasan mendalam mengenai alur kerja sistem, arsitektur *backend/frontend*, dan panduan bagian kode mana yang harus diedit oleh tim, silakan baca:

👉 **[Panduan Engineering Tim AI Jakarta SmartTax 2026 (`docs/ENGINEERING_GUIDE.md`)](docs/ENGINEERING_GUIDE.md)**
