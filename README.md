# Jakarta SmartTax

Jakarta SmartTax (JST) adalah chatbot pajak daerah DKI Jakarta. Jawaban menggunakan dokumen yang diunggah pengelola, dengan referensi dokumen dan halaman jika tersedia.

Frontend memakai Next.js, React, dan TypeScript. Backend memakai FastAPI, Ollama untuk model lokal, SQLite untuk data aplikasi, serta Qdrant untuk pencarian dokumen. PDF dibaca dengan pypdf dan tabel diproses dengan pandas. Embedding masih menggunakan hashing khusus proyek.

## Setup pertama

Siapkan Python 3.12, uv, Node.js, npm, dan Ollama. Jalankan perintah berikut dari folder proyek.

Untuk backend:

```powershell
cd backend
Copy-Item .env.example .env
uv sync --locked --python (py -3.12 -c "import sys; print(sys.executable)") --no-python-downloads
```

Untuk frontend, buka terminal lain:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
```

Salin konfigurasi hanya saat setup pertama dan file tujuan belum ada. Pada PC yang sudah dipakai, gunakan file `.env` yang ada.

Unduh model sesuai konfigurasi backend. Contoh:

```powershell
ollama pull gemma4:12b
```

Atur `OLLAMA_MODEL` dan `OLLAMA_NUM_CTX` di `backend/.env` sesuai perangkat. Pastikan Ollama berjalan sebelum memakai chatbot.

## Menjalankan aplikasi

Terminal backend:

```powershell
cd backend
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```

Terminal frontend:

```powershell
cd frontend
npm run dev
```

Buka [chatbot](http://localhost:3000). Pengelola dapat membuka [dashboard](http://localhost:3000/admin). Untuk menjalankan ulang aplikasi, cukup ulangi perintah di bagian ini.

## Login dan akses pengelola

Dengan `AUTH_ENABLED=true`, pengguna mendaftar melalui Google sebelum login. Akses dashboard diperiksa backend berdasarkan akun developer yang tercantum di `AUTH_DEVELOPER_EMAILS`.

Buat OAuth Client jenis Web application di Google Cloud. Untuk pengembangan lokal, gunakan `http://localhost:3000` sebagai alamat frontend dan `http://localhost:8000/api/auth/google/callback` sebagai redirect URI. Isi `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `AUTH_PUBLIC_URL`, dan `GOOGLE_REDIRECT_URI` di konfigurasi backend.

`AUTH_ENABLED=false` menyediakan akses pengembangan khusus localhost dengan satu identitas lokal. Aktifkan autentikasi sebelum membuka akses publik. Setelah mengubah konfigurasi, restart backend dan muat ulang browser.

## Data aplikasi

| Data | Lokasi bawaan |
| :--- | :--- |
| Akun, identitas Google, dan sesi login | `backend/data/auth.sqlite` |
| Room, pesan, referensi, dan pencarian riwayat | `backend/data/conversations.sqlite` |
| Ringkasan dan kelanjutan percakapan | `backend/data/memory.sqlite` |
| Katalog dokumen, halaman, potongan, dan evaluasi | `backend/data/uploads/knowledge.sqlite` |
| File asli | `backend/data/uploads/` |
| Vektor dokumen | `backend/qdrant_knowledge_storage/` |

Path relatif dihitung dari folder backend. Riwayat tetap tersimpan setelah restart. Saat menemukan struktur lama, backend memigrasikan data dan membuat cadangan lokal. SQL untuk inisialisasi database berada di `backend/app/schemas/`.

Unggah sumber melalui dashboard pengelola. Chat hanya menerima teks. Kelanjutan ke room baru dapat membawa ringkasan dari rangkaian percakapan sebelumnya. Memory percakapan dipisahkan dari sumber peraturan.

Jangan masukkan `.env`, database, unggahan, atau cadangan ke Git. Qdrant embedded digunakan oleh satu proses backend aktif.

## Pengujian

Dari folder backend:

```powershell
uv run --locked python -m unittest discover -s tests
```

Dari folder frontend:

```powershell
node --test tests/*.test.cjs
npm run build
```

Hentikan frontend development sebelum menjalankan build di folder yang sama agar keduanya tidak menulis ke `.next` bersamaan.
