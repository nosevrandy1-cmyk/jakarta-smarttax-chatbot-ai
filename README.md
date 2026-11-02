# Jakarta SmartTax 2026 — Platform AI Chatbot Pajak Daerah DKI Jakarta

Repositori resmi **Tim AI Jakarta SmartTax 2026**. Proyek ini adalah platform *chat* interaktif berbasis RAG (*Retrieval-Augmented Generation*) untuk seluruh kategori pajak daerah **Bapenda Provinsi DKI Jakarta**:

- **PBB-P2** (Pajak Bumi dan Bangunan Perdesaan dan Perkotaan)
- **PBJT** (Pajak Barang dan Jasa Tertentu — Restoran, Perhotelan, Parkir, Kesenian & Hiburan)
- **BPHTB** (Bea Perolehan Hak atas Tanah dan Bangunan)
- **REKLAME** (Pajak Reklame — Videotron, Megatron, Billboard Kawasan Protokol & Kendali Ketat)
- **PAT** (Pajak Air Tanah — Sumur Bor Industri & Komersial)

Platform ini mendukung 3 kapabilitas utama:
1. **Konsultasi Tarif, Rumus & Data Pajak** (Simulasi perhitungan, pengecekan NOP/NPWPD, tunggakan, dan rekap wilayah)
2. **Telusur Pasal & Dasar Hukum** (Pencarian bunyi pasal, ayat, dan kaidah regulasi pajak daerah)
3. **Perumusan Dasar Hukum Baru (*Legal Drafting*)** (Penyusunan draf Konsiderans *Menimbang*, Dasar *Mengingat*, dan Batang Tubuh *Rancangan Pasal & Ayat*)

Seluruh pemrosesan berjalan **100% lokal (*On-Premise*)** menggunakan **Gemma** dan **DeepSeek** di atas **Ollama**, sehingga jawaban terkunci pada data dan korpus hukum resmi yang disediakan tanpa halusinasi.

---

## Ringkasan Tech Stack (Frontend, Backend, Data & AI)

### 1. Frontend (`frontend/`)
- **Framework:** **Next.js 15** (*App Router*) + **React 19** + **TypeScript 5** (`jakarta-smarttax-chatbot-ai-frontend`).
- **Arsitektur Konfigurasi Modular (`src/config/smarttaxConfig.ts`):** Seluruh daftar tema pajak, mode kapabilitas (`konsultasi`, `pasal_hukum`, `perumusan_hukum`), dan *starter prompts* dipisahkan ke satu file konfigurasi agar tim mudah menambah fitur atau kategori baru.
- **Styling & Mobile UX (`src/app/globals.css`):** Menggunakan **Native CSS Custom Properties** dengan dukungan *off-canvas drawer* responsif di layar HP, *tabular-nums* untuk tabel rupiah, dan transisi halus antar-tema.
- **Streaming Client:** Membaca aliran **NDJSON** (*Newline-Delimited JSON*) secara *real-time* menggunakan Web `ReadableStream` + `TextDecoder`.

### 2. Backend (`backend/`)
- **Framework API:** **FastAPI** (Python 3.11+) di atas server ASGI **Uvicorn** (`jakarta-smarttax-chatbot-ai-backend`).
- **Manajemen Paket:** Dikelola menggunakan **`uv`** (`pyproject.toml` & `uv.lock`).
- **Validasi & Keamanan:** Validasi *payload* menggunakan **Pydantic v2** ditambah *middleware* HTTP Security Headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`) serta pembatasan `CORS_ORIGINS`.

### 3. Database & Vector Engine (`backend/data/`)
- **Database Relasional (SQLite 3 — `pajak_dki.sqlite`):**
  - Tabel `pajak_dki_jakarta`: Menyimpan data ketetapan objek pajak, NOP/NPWPD/SSPD/SKPD, nilai DPP/NJOP, pokok pajak, denda, dan status pembayaran.
  - Tabel `korpus_hukum_dki`: Menyimpan struktur pasal, ayat, bab/bagian, bunyi norma hukum, dan kaidah perumusan (*legal drafting*) untuk tiap kategori pajak.
- **Vector Database (Qdrant):** Indeks aktif untuk PDF, tabel Excel/CSV, dan contoh kasus. Mode default embedded lokal di `backend/qdrant_knowledge_storage`, collection `jakarta_smarttax_knowledge`, cosine similarity dengan vektor hashing aplikasi. File asli dan metadata status tetap di arsip sumber SQLite. Startup tidak menghapus atau membangun ulang indeks secara otomatis.

- **Embedding Engine (`backend/app/embedder.py`):** Menggunakan model `nomic-embed-text` yang terikat pada CPU (*CPU-bound embeddings*) agar VRAM GPU tetap 100% didedikasikan untuk inferensi LLM utama.

### 4. AI / LLM Runtime & Safeguard 8GB VRAM (MSI Infinite S3 — NVIDIA RTX 5060 Ti 8GB)
- **Primary LLM (`gemma4:12b`):** Berjalan di atas Ollama lokal dengan batasan ketat memori 8GB VRAM:
  - `OLLAMA_FLASH_ATTENTION=1` dan `OLLAMA_KV_CACHE_TYPE=q8_0`
  - Parameter inferensi terkunci pada `num_ctx: 4096`, `temperature: 1.0`, `top_p: 0.95`, `top_k: 64`
  - Prepend `<|think|>` pada *system prompt* untuk penalaran pajak multi-langkah, serta pembersihan otomatis blok `<|think|>` dari riwayat *multi-turn chat* sebelum pengiriman *request* guna mencegah *KV cache OOM*.
- **AI Intelligence Benchmark & Audit Evidence Engine (`backend/app/eval_engine.py`):**
  - Menghitung skor komposit **SmartTax IQ %**: `(0.40 * Golden Eval Accuracy) + (0.25 * Faithfulness) + (0.20 * Retrieval Precision) + (0.15 * Domain Coverage)` terhadap `golden_dataset.json` (8 kasus pajak daerah DKI Jakarta: PBB-P2, JPB, PBJT, BPHTB, Reklame, PAT, dan sanksi denda keterlambatan).
  - Mencatat bukti *Before vs. After Delta* ke `./dashboard_intelligence_history.json`.

---

## Struktur Folder Proyek

```text
.
├── backend/
│   ├── app/
│   │   ├── config.py           # Konfigurasi Ollama (RTX 5060 Ti 8GB safeguards), Qdrant
│   │   ├── main.py             # Entrypoint FastAPI, endpoint chat, RAG ingestion, & evaluasi audit
│   │   ├── rag_ingestion.py    # Multi-source Qdrant RAG engine (PDF, Excel/CSV, User Reasoning)
│   │   ├── eval_engine.py      # Mesin evaluasi RAGAS / TruLens Triad & Golden Dataset Benchmark
│   │   ├── ollama_service.py   # Router kapabilitas, strip <|think|>, & streaming LLM
│   │   ├── tax_db.py           # Skema SQLite (pajak_dki_jakarta & korpus_hukum_dki)
│   │   ├── vector_store.py     # Qdrant chunk persistence, stable UUIDs and metadata filters
│   │   └── embedder.py         # CPU-bound nomic-embed-text & semantic tax synonym vector engine
│   ├── golden_dataset.json     # 8 kasus benchmark resmi pajak daerah DKI Jakarta
│   └── pyproject.toml          # Konfigurasi paket jakarta-smarttax-chatbot-ai-backend
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── IntelligenceAuditDashboard.tsx # Dashboard RAG Ingestion & Audit Evidence
│   │   ├── types/
│   │   │   └── audit.ts        # Kontrak tipe TypeScript untuk telemetri & audit evaluasi
│   │   ├── config/
│   │   │   └── smarttaxConfig.ts # Konfigurasi modular tema pajak, mode kapabilitas & prompt
│   │   └── app/
│   │       ├── audit/page.tsx  # Halaman langsung RAG & Intelligence Audit Dashboard (/audit)
│   │       ├── layout.tsx      # Root layout, font Inter, & konfigurasi viewport mobile
│   │       ├── page.tsx        # Komponen utama chat, toggle Audit Terminal, & stream NDJSON
│   │       └── globals.css     # Variabel desain Civic-Tech / Financial Terminal & layout responsif
│   └── package.json            # Konfigurasi paket jakarta-smarttax-chatbot-ai-frontend
└── docs/
    └── ENGINEERING_GUIDE.md    # Panduan teknis lengkap untuk Tim AI Jakarta SmartTax 2026
```

---

## Login Google dan akses dashboard

Chatbot sekarang memerlukan login Google. Dashboard dan API pengelolaan hanya
dapat dipakai akun developer yang ditetapkan pada konfigurasi backend.
Ikuti [panduan Google Auth](docs/GOOGLE_AUTH_SETUP.md) untuk membuat OAuth Client,
menetapkan callback, dan menambahkan konfigurasi pada `.env` yang sudah ada.
Jangan menimpa `.env` saat menjalankan ulang aplikasi. Tanpa konfigurasi Google,
halaman login tampil tetapi akses chat dan dashboard tetap terkunci.

Riwayat pada tahap ini masih berada di browser dan dipisahkan per akun;
sinkronisasi history server serta kontribusi data training belum tersedia.

## Setup dan Menjalankan Aplikasi (Windows / PowerShell)

Siapkan **Python 3.12 dari python.org**, **uv**, **Node.js + npm**, dan **Ollama**.
Qdrant berjalan embedded, jadi tidak perlu memasang Docker atau server database terpisah.

### Setup pertama setelah clone

Lakukan langkah ini **sekali saja**. Perintah `Copy-Item` hanya dijalankan jika file tujuan belum ada. Jika proyek sudah pernah dijalankan di PC ini, langsung ke bagian **Menjalankan ulang**.

**1. Backend** - buka terminal di folder proyek:

```powershell
cd backend
Copy-Item .env.example .env
uv sync --locked --python (py -3.12 -c "import sys; print(sys.executable)") --no-python-downloads
```

Buka `backend/.env` dan sesuaikan konfigurasi. Untuk login Google, ikuti [panduan Google Auth](docs/GOOGLE_AUTH_SETUP.md); jangan membagikan Client Secret atau memasukkannya ke Git.

**2. Frontend** - buka terminal lain di folder proyek:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
```

Contoh frontend sudah mengarah ke backend lokal di `http://localhost:8000`.

**3. Model Ollama** - unduh model sekali jika belum tersedia:

```powershell
ollama pull gemma4:12b
```

Pastikan aplikasi Ollama berjalan sebelum memakai chatbot. Pengaturan model dan ukuran konteks mengikuti `backend/.env`.

### Menjalankan ulang

Untuk pemakaian berikutnya, cukup jalankan dua terminal berikut. **Tidak perlu menyalin `.env` atau mengunduh model lagi.**

**Terminal backend**, dari folder proyek:

```powershell
cd backend
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal frontend**, dari folder proyek:

```powershell
cd frontend
npm run dev
```

Buka chatbot di **http://localhost:3000** dan dashboard di **http://localhost:3000/admin**. Secara default, Google login diperlukan dan dashboard hanya untuk developer yang diizinkan.

Mode sementara tanpa Google login tersedia pada branch `feat/google-auth` melalui `AUTH_ENABLED=false`, hanya untuk localhost. Gunakan pengaturan itu jika versi yang dijalankan sudah memuat perubahan mode lokal tersebut. Untuk mengaktifkan login kembali, gunakan `AUTH_ENABLED=true`, restart backend, lalu refresh browser.

### Data lokal

- Indeks Qdrant: `backend/qdrant_knowledge_storage/`.
- Akun, sesi dan history chat: `backend/data/auth.sqlite`.
- File asli dan arsip sumber: `backend/data/uploads/`.

Data tetap tersimpan saat aplikasi dihentikan atau dijalankan ulang. Jangan menghapus folder data ketika hanya ingin me-restart aplikasi. Jika menemui kendala runtime Windows, lihat [panduan backend Windows](docs/WINDOWS_BACKEND_SETUP.md).

---

## Panduan Teknis Tim Engineering

Penjelasan lengkap mengenai arsitektur kode, cara kerja *dual-model* **Gemma & DeepSeek**, serta panduan file mana yang harus diedit saat mengembangkan fitur baru tersedia di:

👉 **[Panduan Engineering Tim AI Jakarta SmartTax 2026 (`docs/ENGINEERING_GUIDE.md`)](docs/ENGINEERING_GUIDE.md)**

Laporan implementasi dan audit Google Auth: [dokumen 29 Oktober 2026](docs/GOOGLE_AUTH_IMPLEMENTATION_2026-10-29.md).

Migrasi indeks November 2026: lihat [Qdrant migration](docs/QDRANT_MIGRATION_2026-11-02.md).
