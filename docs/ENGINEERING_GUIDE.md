# Engineering Guide — Tim AI Jakarta SmartTax 2026

Halo rekan-rekan **Tim AI Jakarta SmartTax 2026**. Dokumen ini ditulis sebagai pegangan teknis (*handbook*) untuk seluruh anggota tim—baik yang megang **Frontend**, **Backend**, **Data/Database**, maupun **Server/Infra**—supaya kita punya pemahaman yang sama tentang cara kerja kode ini dan tahu persis file mana yang harus disentuh saat ada perubahan.

---

## 1. Gambaran Besar Sistem (Bagaimana Semuanya Terhubung)

Secara sederhana, **Jakarta SmartTax 2026** adalah sistem tanya-jawab pajak daerah DKI Jakarta (`PBB-P2`, `PBJT`, `BPHTB`, `REKLAME`, `PAT`) yang menggabungkan **pencarian tabel SQL pasti** (untuk angka tagihan, NOP/NPWPD, denda, dan rekap wilayah) dengan **pencarian vektor semantik / RAG** (untuk tarif, rumus perhitungan, dan ketentuan pajak).

Kenapa kita gabungkan SQL + Vector Search?
Karena kalau mengandalkan LLM atau Vector Search saja untuk urusan angka rupiah pajak, rawan terjadi *halusinasi* saat menjumlahkan piutang atau denda. Dengan arsitektur kita sekarang:
1. Angka rupiah, denda, dan status lunas dihitung pasti oleh **SQLite**.
2. Konteks aturan dan pencarian teks bebas dicari oleh **Qdrant Vector Database**.
3. **Ollama (LLM Lokal)** bertugas merangkai hasil keduanya menjadi jawaban bahasa Indonesia yang enak dibaca dan rapi dalam bentuk tabel Markdown.

```text
[Browser Desktop / Mobile]
   │  Next.js 15 + React 19 (Port 3000)
   │  Kirim POST /api/chat/stream (Payload: message, tema_pajak, history)
   ▼
[Backend FastAPI + Uvicorn (Port 8000)]
   ├─► 1. Cek apakah pertanyaan nyasar ke tema pajak lain (_detect_cross_theme)
   ├─► 2. Cari kecocokan semantik di Qdrant (difilter khusus tema_pajak aktif)
   ├─► 3. Jalankan query SQLite (cari objek/NOP, daftar tunggakan, rekap wilayah)
   └─► 4. Rangkai prompt + konteks data lokal ──► Kirim ke Ollama (Port 11434)
          *(Jika Ollama mati/belum terpasang, otomatis pakai Deterministic SQL Formatter)*
   │
   ▼  Alirkan balik per baris via protokol NDJSON (status -> sources -> token -> done)
[Browser merender huruf demi huruf + Tabel Markdown + Tombol Follow-up]
```

---

## 2. Bedah Tech Stack: Kita Pakai Apa Saja?

### A. Frontend (`frontend/`) — Pakai Apa & Kenapa?
- **Next.js 15 (App Router) + React 19 + TypeScript 5**
  Kita pakai Next.js 15 dengan *App Router* (`frontend/src/app/`). Seluruh interaksi *chat* berjalan di sisi klien (*Client Component* pada `src/app/page.tsx`) supaya transisi antar-sesi, pergantian *dropdown* pajak, dan efek *streaming* teks terasa instan tanpa *reload* halaman.
- **Native CSS Custom Properties (`src/app/globals.css`)**
  Kita sengaja tidak menumpuk *library* UI pihak ketiga yang bikin *bundle* bengkak. Seluruh warna tema (*Light Mode* & *Dark Mode*), ukuran *bubble* percakapan, *badge* indikator pajak, hingga *off-canvas sidebar drawer* untuk tampilan HP diatur lewat CSS Variables di `globals.css`.
- **NDJSON Stream Reader (`ReadableStream` + `TextDecoder`)**
  Di `page.tsx`, fungsi `sendQuestion()` tidak menunggu jawaban selesai sekaligus, melainkan membuka aliran `response.body.getReader()`. Begitu backend mengirim potongan baris JSON (`status`, `token`, `done`), layar pengguna langsung memperbarui tahapan *loading* dan mengetik jawaban secara *real-time*.
- **Penyimpanan Sesi Lokal (`localStorage`)**
  Riwayat obrolan disimpan di *browser* dengan kunci `bapenda-dki-sessions-v2`. Setiap sesi menyimpan properti `taxTheme` masing-masing, jadi obrolan PBB-P2 tidak akan bercampur dengan obrolan PBJT Restoran.

### B. Backend (`backend/`) — Pakai Apa & Kenapa?
- **Python 3.11+ & FastAPI (`app/main.py`)**
  Kita pakai FastAPI karena dukungannya terhadap *asynchronous generator* (`StreamingResponse`) sangat matang dan ringan. Server dijalankan menggunakan **Uvicorn ASGI**.
- **Manajemen Paket dengan `uv` (`pyproject.toml`)**
  Tim tidak perlu lagi pusing dengan `virtualenv` manual atau `pip install` yang lambat. Cukup jalankan `uv sync`, semua *dependency* terkunci rapi sesuai `uv.lock`.
- **Validasi Input & Keamanan (`Pydantic v2` + Middleware)**
  Di `app/main.py`, semua *request* yang masuk ke `/api/chat` dan `/api/chat/stream` divalidasi oleh `ChatRequestInput`:
  - Panjang pesan dibatasi maksimal `2.000` karakter.
  - Riwayat percakapan dibatasi maksimal `20` item terakhir.
  - Dilengkapi *Security Headers Middleware* (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`) dan pembatasan domain `CORS_ORIGINS`.
- **Async HTTP Client (`httpx`)**
  Untuk menembak endpoint `/api/chat` milik Ollama secara *streaming* tanpa memblokir *event loop* utama FastAPI.

### C. Database & Vector Engine (`backend/app/tax_db.py` & `vector_store.py`)
- **SQLite 3 (`backend/data/pbb_p2_lokal.db`)**
  Berisi 2 tabel utama dengan mode `WAL` (*Write-Ahead Logging*) agar aman diakses bersamaan:
  1. `pajak_dki_records`: Menyimpan data ketetapan pajak untuk ke-5 tema (`PBB-P2`, `PBJT`, `BPHTB`, `REKLAME`, `PAT`), mulai dari `nomor_identitas` (NOP / NPWPD / Nomor SSPD / SKPD), `nama_wp`, `nama_objek`, wilayah administrasi DKI Jakarta, nilai `dpp_atau_njop_rp`, `pokok_pajak_rp`, `denda_rp`, hingga `status_bayar`.
  2. `regulasi_dki_chunks`: Menyimpan ringkasan aturan tarif, rumus perhitungan, dan ketentuan khusus per jenis pajak.
- **Qdrant Vector Database (`backend/data/qdrant_storage/`)**
  Kita menggunakan `QdrantClient(path=...)` yang menyimpan indeks vektor langsung di folder lokal (atau bisa diarahkan ke Qdrant Server via `QDRANT_URL`). Setiap dokumen yang dimasukkan ke koleksi `bapenda_dki_pajak_v2` memiliki metadata `tema_pajak`. Saat pengguna memilih tema `PBJT`, Qdrant memasang `FieldCondition(key="tema_pajak", match=MatchValue(value="PBJT"))` sehingga hasil pencarian dijamin 100% relevan dengan tema aktif.
- **Local Embedding (`backend/app/embedder.py`)**
  Menghasilkan vektor berdimensi `384` menggunakan model `sentence-transformers/all-MiniLM-L6-v2` via `transformers` & `torch`. Kalau server produksi kita nanti diisolasi dari internet dan belum sempat mengunduh *cache* HuggingFace, `embedder.py` punya *fallback* otomatis ke algoritma *subword hashing* 384-dimensi yang tetap jalan secara lokal.

### D. AI / LLM Runtime (`backend/app/ollama_service.py`)
- **Ollama Lokal (`http://localhost:11434`)**
  Secara *default* diarahkan ke model `qwen2.5:7b-instruct` (bisa diganti lewat file `.env`). Kita men-set `temperature: 0.0` supaya model patuh 100% pada angka di konteks lokal dan tidak mengarang angka pajak.
- **Deterministic SQL Fallback (`_build_local_deterministic_answer`)**
  Ini fitur penyelamat kita: kalau *service* Ollama di server sedang *down*, *restart*, atau di laptop anggota tim belum ter-install Ollama, sistem otomatis menyusun tabel Markdown dari hasil query SQLite dan mengalirkannya ke frontend dengan kecepatan ketik natural.

---

## 3. Protokol Streaming Backend ke Frontend (NDJSON)

Endpoint `POST /api/chat/stream` mengirimkan respon dengan tipe `application/x-ndjson`. Setiap baris adalah objek JSON mandiri:

1. **Tahap Proses (`type: "status"`)** — Ditampilkan sebagai indikator langkah kerja di UI:
   ```json
   {"type": "status", "text": "Menelusuri arsip PBB-P2 Bapenda DKI Jakarta..."}
   ```
2. **Metadata Sumber & Deteksi Lintas-Pajak (`type: "sources"`)**:
   ```json
   {
     "type": "sources",
     "tema_pajak": "PBB-P2",
     "suggested_theme": "PBJT",
     "qdrant_sources": [...],
     "sql_tools_used": ["daftar_tunggakan_pajak_dki"]
   }
   ```
   *Catatan:* Jika `suggested_theme` tidak `null` (misalnya user sedang di tab `PBB-P2` tapi bertanya soal *Pajak Restoran*), frontend otomatis memunculkan kartu tombol **"Pindah ke PBJT"**.
3. **Aliran Teks Jawaban (`type: "token"`)**:
   ```json
   {"type": "token", "delta": "Berikut rincian "}
   ```
4. **Selesai (`type: "done"`)** — Mengirimkan rekomendasi pertanyaan lanjutan (*follow-up chips*):
   ```json
   {
     "type": "done",
     "tema_pajak": "PBB-P2",
     "suggested_theme": null,
     "follow_ups": ["Tampilkan objek PBB-P2 DKI yang masih menunggak beserta dendanya", "..."],
     "model_used": "qwen2.5:7b-instruct",
     "duration_ms": 410
   }
   ```

---

## 4. Cheat-Sheet Tim: Kalau Mau Edit Sesuatu, Buka File Mana?

Bagian ini dibuat supaya teman-teman tim tidak perlu menebak-nebak lokasi kode saat dapat *task* baru:

### Skenario 1: Mengubah Tampilan UI, Warna, Ukuran Huruf, atau Tampilan Mobile
- **File yang diedit:**
  - `frontend/src/app/globals.css` (semua variabel warna `--bg-main`, `--text-primary`, *layout* `.sidebar-shell`, dan aturan layar HP di `@media (max-width: 767px)`).
  - `frontend/src/app/page.tsx` (komponen *header*, *dropdown* pemilih pajak, *sidebar* riwayat percakapan, dan *composer* input pesan).
- **Tips untuk Tim Frontend:**
  - Warna *badge* indikator tiap pajak ada di konstanta `TAX_THEMES` di bagian atas `frontend/src/app/page.tsx`.
  - Kalau mau mengubah teks sapaan awal atau contoh pertanyaan (*starter cards*) saat ruang chat masih kosong, langsung ubah properti `starters` di dalam `TAX_THEMES` pada `frontend/src/app/page.tsx`.

### Skenario 2: Menambah / Mengubah Data Objek Pajak & Ketentuan Tarif
- **File yang diedit:**
  - `backend/app/tax_db.py`
- **Langkahnya:**
  1. Buka `backend/app/tax_db.py`, cari variabel `SEED_RECORDS` (untuk data objek pajak/NOP/NPWPD) atau `SEED_REGULASI` (untuk penjelasan tarif, rumus, dan denda).
  2. Tambahkan atau ubah baris datanya sesuai struktur tuple yang sudah ada.
  3. Supaya data baru langsung masuk ke SQLite dan di-indeks ulang oleh Qdrant, hapus file database lama lalu nyalakan ulang backend, atau panggil endpoint re-index:
     ```bash
     rm -f backend/data/pbb_p2_lokal.db
     curl -X POST http://localhost:8000/api/reindex
     ```

### Skenario 3: Menambah Kategori Pajak Daerah Baru (Misalnya: Pajak Kendaraan Bermotor / PKB)
Kalau nanti kita diminta menambah kategori ke-6 (misalnya `PKB`), cukup lakukan 4 langkah ini:
1. **`backend/app/tax_db.py`**: Tambahkan definisi `"PKB"` ke dalam dictionary `TAX_THEMES`, lalu masukkan data sampelnya ke `SEED_RECORDS` dan `SEED_REGULASI`.
2. **`backend/app/ollama_service.py`**:
   - Tambahkan kata kunci deteksi lintas-tema (seperti `"stnk"`, `"pkb"`, `"kendaraan"`, `"plat nomor"`) ke `THEME_KEYWORDS["PKB"]`.
   - Tambahkan 3–4 kalimat rekomendasi pertanyaan ke `prompts_by_theme["PKB"]` di dalam fungsi `_generate_follow_ups()`.
3. **`frontend/src/app/page.tsx`**: Tambahkan objek konfigurasi `"PKB"` ke array `TAX_THEMES` supaya muncul di menu *dropdown* atas dan memiliki contoh pertanyaan awal.
4. Restart backend atau jalankan `POST /api/reindex`.

### Skenario 4: Mengubah Gaya Bahasa AI / System Prompt atau Mengganti Model LLM
- **File yang diedit:**
  - `backend/app/ollama_service.py` -> fungsi `build_thematic_system_prompt(tema_pajak: str)` untuk mengubah instruksi gaya bahasa AI.
  - `backend/.env` -> ubah `DEFAULT_CHAT_MODEL=qwen2.5:7b-instruct` ke nama model Ollama lain yang terpasang di server (misalnya `llama3.1:8b` atau `gemma2:9b`).

---

## 5. Daftar Endpoint API Backend (Port `8000`)

| Method | Endpoint | Fungsi |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Mengecek kesehatan server, status koneksi Ollama, jumlah baris di SQLite, dan status koleksi Qdrant. |
| `GET` | `/api/sppt` | Mengambil data tabel `pajak_dki_records` dan `regulasi_dki_chunks` (bisa difilter dengan query `?tema_pajak=PBJT`). |
| `POST` | `/api/chat/stream` | Endpoint utama *chat* yang mengalirkan respon dalam format **NDJSON** (*real-time streaming*). |
| `POST` | `/api/chat` | Endpoint *chat* standar (non-streaming, langsung mengembalikan JSON utuh) untuk keperluan pengujian otomatis / integrasi. |
| `POST` | `/api/reindex` | Memaksa Qdrant membangun ulang seluruh vektor dari isi SQLite terbaru. |

---

## 6. Standar Kerapian Kode & Git untuk Tim

Supaya repositori kita tetap bersih dan enak dipelihara bersama:
1. **Jangan pernah commit file `.env` atau isi folder `backend/data/`** (file `.db` SQLite dan folder `qdrant_storage/` sudah masuk di `.gitignore`).
2. **Validasi sebelum *push*:**
   - Untuk perubahan Frontend, pastikan `npm run build` di folder `frontend/` lolos tanpa *error* TypeScript.
   - Untuk perubahan Backend, pastikan endpoint `GET http://localhost:8000/api/health` mengembalikan `"status": "ok"`.
3. **Gunakan penamaan commit yang jelas:** misalnya `feat(pbjt): tambah filter pencarian kecamatan` atau `fix(ui): rapikan drawer sidebar di layar mobile`.
