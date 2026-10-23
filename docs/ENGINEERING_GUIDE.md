# Engineering Guide — Tim AI Jakarta SmartTax 2026

Halo rekan-rekan **Tim AI Jakarta SmartTax 2026**. Dokumen ini disusun sebagai pegangan teknis bersama untuk tim **Frontend**, **Backend**, **Data/Regulasi**, dan **AI/Server** agar pengembangan **Jakarta SmartTax Chatbot AI** tetap rapi, konsisten, dan mudah di-*scale up*.

---

## 1. Arsitektur & 3 Kapabilitas Utama Sistem

**Jakarta SmartTax Chatbot AI** dirancang bukan sekadar untuk tanya-jawab tarif pajak biasa, melainkan memiliki **3 mode kapabilitas terpadu** yang berjalan di atas data lokal Bapenda DKI Jakarta (`PBB-P2`, `PBJT`, `BPHTB`, `REKLAME`, `PAT`):

1. **Mode Konsultasi Tarif, Rumus & Data Pajak (`konsultasi`)**
   Menangani pengecekan objek pajak (NOP/NPWPD/SSPD/SKPD), simulasi rumus perhitungan, daftar tunggakan + denda, serta rekapitulasi realisasi per Kota Administrasi DKI Jakarta.
2. **Mode Telusur Pasal & Dasar Hukum (`pasal_hukum`)**
   Menangani pencarian bunyi pasal dan ayat secara presisi dari tabel `korpus_hukum_dki`, lengkap dengan hierarki instrumen hukum (Perda, Pergub, Kepgub) dan implikasi penerapannya.
3. **Mode Perumusan Dasar Hukum Baru / Legal Drafting (`perumusan_hukum`)**
   Membantu tim hukum dan analis kebijakan menyusun draf regulasi baru (Rancangan Pergub / Kepgub / SK Kepala Bapenda) yang mencakup **Konsiderans Menimbang**, **Dasar Hukum Mengingat**, **Rancangan Batang Tubuh (Pasal & Ayat)**, serta **Matriks Harmonisasi Pasal Induk**.

```text
[Browser Desktop / Mobile — Next.js 15 + React 19 (Port 3000)]
   │  Pilih Pajak (PBB-P2 / PBJT / BPHTB / REKLAME / PAT)
   │  Pilih Mode (Tarif & Data | Pasal & Dasar Hukum | Perumusan Hukum)
   │  POST /api/chat/stream
   ▼
[Backend FastAPI + Uvicorn (Port 8000)]
   ├─► 1. Deteksi mode kapabilitas (_resolve_capability_mode) & cek lintas-pajak (_detect_cross_theme)
   ├─► 2. Query Qdrant Vector DB (filter tema_pajak + doc_type: objek_pajak / regulasi / pasal_hukum)
   ├─► 3. Query SQLite (pajak_dki_jakarta + korpus_hukum_dki + susun_rancangan_hukum_dki)
   └─► 4. Kirim konteks RAG terstruktur (temperature=0.0, top_p=0.1) ke Ollama:
          • Gemma (gemma2:9b di OLLAMA_HOST) ──► untuk RAG cepat Tarif & Data
          • DeepSeek (deepseek-r1:8b di OLLAMA_SECONDARY_HOST) ──► untuk Analisis Pasal & Legal Drafting
   │
   ▼  Alirkan balik via NDJSON (status -> sources -> thinking -> token -> done)
[Browser merender tahapan proses, penalaran, tabel Markdown, & chip tindak lanjut]
```

---

## 2. Penjelasan Tech Stack (Frontend, Backend, Database & AI)

### A. Frontend (`frontend/`)
- **Next.js 15 (App Router) + React 19 + TypeScript 5**
  Komponen utama berada di `src/app/page.tsx`, sedangkan seluruh konfigurasi tema pajak, mode kapabilitas, dan daftar *starter prompts* dipisahkan secara modular di `src/config/smarttaxConfig.ts`.
- **Native CSS Custom Properties (`src/app/globals.css`)**
  Mengatur seluruh tata letak *sidebar*, *drawer* layar HP (`@media (max-width: 767px)`), animasi *shimmer loading*, dan tabel Markdown tanpa membebani ukuran *bundle* dengan *library* CSS eksternal yang berat.
- **NDJSON Stream Consumer**
  Membaca aliran respon baris demi baris dari backend menggunakan `ReadableStream` dan `TextDecoder`. Mendukung tampilan lipat (*collapsible*) untuk blok penalaran (`thinking`) saat menggunakan model **DeepSeek**.

### B. Backend (`backend/`)
- **Python 3.11+, FastAPI & Uvicorn (`app/main.py`)**
  Menyediakan endpoint *streaming* asinkron (`POST /api/chat/stream`), pengecekan kesehatan sistem (`GET /api/health`), inspeksi pasal (`GET /api/korpus-hukum`), dan *re-indexing* vektor (`POST /api/reindex`).
- **Manajemen Dependency dengan `uv` (`pyproject.toml`)**
  Nama paket dikunci sebagai `jakarta-smarttax-chatbot-ai-backend`. Cukup jalankan `uv sync` untuk menyamakan *environment* di semua mesin tim.
- **Keamanan & Validasi (`Pydantic v2`)**
  Membatasi ukuran pesan maksimal `2.000` karakter, riwayat percakapan maksimal `20` pesan, mengatur header keamanan HTTP, dan membatasi domain asal lewat `CORS_ORIGINS`.

### C. Database SQLite & Vector Engine Qdrant (`backend/app/tax_db.py` & `vector_store.py`)
- **SQLite 3 (`backend/data/pajak_dki.sqlite`)**
  Memiliki dua tabel utama yang otomatis dibuat saat startup (`init_tax_db()`):
  1. `pajak_dki_jakarta`: Menyimpan data ketetapan objek pajak, NOP/NPWPD/SSPD/SKPD, nilai dasar pengenaan, pokok pajak, denda, dan status lunas.
  2. `korpus_hukum_dki`: Menyimpan struktur pasal & dasar hukum (`kode_pasal`, `tema_pajak`, `jenis_instrumen`, `hierarki_level`, `bab_bagian`, `pasal_ayat`, `tentang`, `bunyi_norma`, `kaidah_perumusan`, `kata_kunci`).
- **Qdrant Vector Store (`backend/qdrant_storage/`)**
  Mengindeks seluruh baris dari `pajak_dki_jakarta`, `DKI_REGULASI_CHUNKS`, dan `korpus_hukum_dki` ke dalam koleksi `jakarta_smarttax_kb`. Saat pengguna berada di mode **Pasal & Dasar Hukum** atau **Perumusan Hukum**, Qdrant otomatis memprioritaskan dokumen berjenis `doc_type="pasal_hukum"`.

### D. Dual-Model Ollama Runtime: Gemma & DeepSeek (`backend/app/ollama_service.py`)
- **Prinsip Anti-Halusinasi (*Zero-Hallucination Grounding*):**
  Backend mengunci parameter inferensi Ollama pada `temperature: 0.0` dan `top_p: 0.1`, serta menyuntikkan hasil query SQLite + Qdrant langsung ke dalam *prompt*. Model dilarang mengarang angka atau nomor pasal di luar konteks lokal.
- **Pembagian Peran Model (1 PC maupun 2 PC LAN):**
  - `OLLAMA_MODEL=gemma2:9b` di `OLLAMA_HOST` (PC Server 1): Merespons cepat pertanyaan tarif, rumus, dan data ketetapan pajak.
  - `OLLAMA_DRAFTING_MODEL=deepseek-r1:8b` di `OLLAMA_SECONDARY_HOST` (PC Server 2 atau PC yang sama): Menangani analisis pasal dan perumusan draf hukum baru. Blok `<think>...</think>` dari DeepSeek otomatis dipisahkan oleh backend menjadi event `{"type": "thinking"}` sehingga hasil akhir di layar tetap bersih.

---

## 3. Panduan Scaling Up untuk Tim (File Mana yang Harus Diedit?)

Kode ini sudah dirancang modular agar setiap anggota tim bisa menambah fitur, pasal, atau tampilan baru tanpa saling menimpa pekerjaan:

### A. Menambah Pasal & Dasar Hukum Baru (Tim Data / Regulasi & Backend)
1. Buka `backend/app/tax_db.py` dan cari list `DKI_LEGAL_CORPUS`.
2. Tambahkan dictionary pasal baru dengan struktur berikut:
   ```python
   {
       "kode_pasal": "PASAL-PBB-04",
       "tema_pajak": "PBB-P2",
       "jenis_instrumen": "Peraturan Gubernur DKI Jakarta",
       "hierarki_level": 2,
       "bab_bagian": "Bab Tata Cara Pengurangan PBB-P2",
       "pasal_ayat": "Pasal 12 ayat (1) dan ayat (2)",
       "tentang": "Kriteria Pengurangan PBB-P2 bagi Veteran dan Pensiunan",
       "bunyi_norma": "(1) Pengurangan PBB-P2 dapat diberikan...",
       "kaidah_perumusan": "Digunakan sebagai acuan saat menyusun...",
       "kata_kunci": "pengurangan pbb veteran pensiunan",
   }
   ```
3. Jalankan perintah berikut agar SQLite dan Qdrant langsung mengindeks pasal baru tersebut:
   ```bash
   curl -X POST http://localhost:8000/api/reindex
   ```

### B. Mengembangkan Template Perumusan Dasar Hukum / Legal Drafting (Tim Backend & AI)
- Buka `backend/app/tax_db.py` -> fungsi `susun_rancangan_hukum_dki(topik_perumusan, tema_pajak)` untuk menambah struktur konsiderans atau klausul baku.
- Buka `backend/app/ollama_service.py` -> fungsi `build_thematic_system_prompt()` dan `_build_local_deterministic_answer()` untuk mengatur format luaran draf regulasi (misalnya menambah bagian *Penjelasan Pasal Demi Pasal* atau *Naskah Akademik*).

### C. Mengubah Tampilan UI, Kartu Prompt Awal, atau Menambah Mode Baru (Tim Frontend)
1. **Mengubah Kartu Pertanyaan Awal (*Starter Cards*) atau Label Mode:**
   - Langsung edit `frontend/src/config/smarttaxConfig.ts`. Di file ini sudah dipisahkan `starters` (mode konsultasi), `legalStarters` (mode pasal & dasar hukum), dan `draftingStarters` (mode perumusan hukum) untuk masing-masing pajak.
2. **Mengubah Komponen Chat, Dropdown, atau Header:**
   - Edit `frontend/src/app/page.tsx`.
3. **Mengubah Warna, Font, atau Layout Responsif Mobile:**
   - Edit `frontend/src/app/globals.css`.

### D. Menghubungkan 2 PC Server di Jaringan LAN (Tim AI & Server)
Jika menggunakan 2 PC di jaringan LAN Gigabit (misalnya PC 1 di `192.168.1.10` menjalankan `gemma2:9b` dan PC 2 di `192.168.1.11` menjalankan `deepseek-r1:8b`), cukup ubah file `backend/.env` di PC 1 menjadi:
```env
OLLAMA_HOST=http://192.168.1.10:11434
OLLAMA_SECONDARY_HOST=http://192.168.1.11:11434
OLLAMA_MODEL=gemma2:9b
OLLAMA_DRAFTING_MODEL=deepseek-r1:8b
```
Backend akan otomatis mengarahkan request model Gemma ke PC 1 dan request model DeepSeek / Perumusan Hukum ke PC 2.

---

## 4. Daftar Endpoint API Backend (Port `8000`)

| Method | Endpoint | Fungsi |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Mengecek status server, koneksi Ollama, jumlah objek pajak, dan jumlah pasal di `korpus_hukum_dki`. |
| `GET` | `/api/korpus-hukum` | Mengambil daftar pasal & dasar hukum dari SQLite (bisa difilter dengan `?tema_pajak=PBB-P2`). |
| `POST` | `/api/chat/stream` | Endpoint utama *chat* dengan *streaming* **NDJSON** (menerima `message`, `tema_pajak`, `mode_kapabilitas`, `model`, `history`). |
| `POST` | `/api/chat` | Endpoint *chat* non-streaming (mengembalikan JSON utuh) untuk keperluan pengujian otomatis QA. |
| `POST` | `/api/reindex` | Memperbarui tabel SQLite dan membangun ulang seluruh indeks vektor Qdrant. |
