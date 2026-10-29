# Login Google Jakarta SmartTax

Implementasi ini mewajibkan login sebelum memakai chatbot. Dashboard `/admin` dan `/audit`, dokumentasi API, serta API pengelolaan hanya dapat dipakai akun developer yang ditetapkan server. Menghilangkan tombol pada frontend tidak digunakan sebagai pengaman API.

## Status implementasi

- Google OpenID Connect authorization code flow dengan state, nonce, dan PKCE S256.
- ID token diperiksa memakai library resmi `google-auth`: signature, audience, issuer, masa berlaku. Aplikasi juga memeriksa nonce, subject, email terverifikasi, dan allowlist jika ditetapkan.
- Identitas permanen berdasarkan provider dan Google `sub`, bukan pencocokan alamat email saja.
- Sesi aplikasi memakai token acak di cookie HttpOnly, SameSite=Lax, Secure untuk HTTPS. Hanya hash token sesi yang disimpan di server.
- Batas sesi 30 menit tidak aktif dan maksimal 8 jam sejak login. Logout mencabut sesi saat ini dan memberi tahu tab lain pada browser yang sama.
- Mutasi API memeriksa Origin dan token CSRF. Akun biasa hanya diizinkan memakai chat dan health minimal; pengelolaan memerlukan role developer dari konfigurasi server.
- Data akun dan sesi terpisah di `backend/data/auth.sqlite`, tidak masuk koleksi RAG dan diabaikan Git. Akses ke file database dan backup perlu dibatasi di perangkat/hosting.
- Tanpa konfigurasi OAuth yang valid, chatbot tetap terkunci dan menampilkan penjelasan login belum tersedia. Tidak ada fallback anonymous atau akun developer otomatis.

Uji otomatis menggunakan identitas fiktif dan database sementara, tanpa meminta akses ke akun Google sebenarnya. Login nyata belum dapat dinyatakan berhasil sebelum langkah Google Cloud di bawah selesai.

## 1 Buat OAuth Client di Google Cloud

1. Buka https://console.cloud.google.com/ dan pilih atau buat project untuk JST.
2. Buka **Google Auth Platform**. Pada **Branding**, isi nama aplikasi Jakarta SmartTax, email dukungan dan email kontak pengembang.
3. Pada **Audience**, pilih Internal jika project dan seluruh pengguna memang berada pada organisasi Workspace yang sesuai. Untuk akun pribadi atau peserta luar organisasi, gunakan External. Selama pengujian, tambahkan akun yang akan mencoba login sebagai test users jika diminta oleh konsol.
4. Scope untuk login ini hanya `openid`, `email`, dan `profile`. Jangan menambahkan scope Gmail, Drive, atau layanan lain.
5. Buka **Clients → Create client**. Pilih tipe **Web application**, misalnya dengan nama JST Local Development.
6. Pada **Authorized redirect URIs**, masukkan persis:

```text
http://localhost:8000/api/auth/google/callback
```

7. Alur ini dikelola backend, jadi tidak memakai Google JavaScript SDK. Authorized JavaScript origins tidak diperlukan untuk alur server ini; bila konfigurasi konsol membutuhkannya untuk penggunaan lain, origin pengembangan frontend adalah `http://localhost:3000`.
8. Simpan client. Salin Client ID dan Client secret langsung ke `.env` lokal yang sudah ada. Jangan kirim secret ke chat, commit Git, atau environment frontend.

Ikuti nama menu yang tersedia pada konsol Google saat konfigurasi. Referensi resmi: https://developers.google.com/identity/openid-connect/openid-connect

## 2 Isi konfigurasi backend yang sudah ada

Edit **`backend/.env` yang sudah ada**. Tambahkan key yang belum ada; perbarui nilai yang memang ingin diganti. **Jangan menjalankan `cp .env.example .env` untuk menimpa konfigurasi lama.**

```dotenv
GOOGLE_CLIENT_ID=isi_dari_google_cloud
GOOGLE_CLIENT_SECRET=isi_langsung_di_file_lokal
AUTH_PUBLIC_URL=http://localhost:3000
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
AUTH_DEVELOPER_EMAILS=email_developer_yang_dipilih
AUTH_ALLOWED_EMAILS=
```

- `AUTH_DEVELOPER_EMAILS`: daftar email akun Google developer, dipisahkan koma. Jika kosong, tidak ada akun yang memperoleh akses dashboard. Tidak ada aturan first user becomes admin.
- `AUTH_ALLOWED_EMAILS`: opsional untuk membatasi pilot. Jika kosong, akun Google terverifikasi dapat mendaftar selama diizinkan konfigurasi Google Cloud. Login hanya menerima akun JST yang sudah terdaftar. Bila diisi, hanya email dalam daftar tersebut atau daftar developer yang boleh masuk. Daftar developer tetap harus diatur terpisah.
- Peran tidak diambil dari parameter URL, request body, localStorage, atau klaim role buatan pengguna. Daftar email developer hanya ditentukan oleh pengelola server.
- Buka aplikasi menggunakan `http://localhost:3000`, bukan bergantian `127.0.0.1`. Host frontend dan callback harus sama; jangan campur keduanya. API frontend yang saat ini dikonfigurasi harus menuju `http://localhost:8000`.
- Scope login tidak mencakup isi prompt/dokumen. Google menerima informasi identitas dan metadata login yang diperlukan alur autentikasi, bukan isi chat sebagai bagian permintaan login.

Setelah menyimpan `.env`, **restart backend milikmu** agar konfigurasi dimuat kembali. Jangan menjalankan instance kedua pada port yang sama. Environment proses memiliki prioritas atas `.env`, jadi hapus atau sesuaikan override lama bila konfigurasi tampak tidak berubah.

```powershell
cd D:\jakarta-smarttax-chatbot-ai\backend
uv sync --locked
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend dapat tetap memakai proses development yang sudah berjalan. Refresh browser setelah backend siap.

## 3 Uji melalui browser

1. Buka `http://localhost:3000/`. Sebelum login, chat dan dashboard tidak ditampilkan.
2. Akun baru: klik **Daftar**, kemudian **Daftar dengan Google**. Akun yang sudah terdaftar memakai **Masuk dengan Google**. Selesaikan langkah Google sendiri. Login akun yang belum terdaftar ditolak; daftar ulang akun lama juga ditolak.
3. Login akun biasa: chatbot terbuka. Mengakses `/admin` atau `/audit` menampilkan akses khusus developer dan API pengelolaan menolak request.
4. Login akun dalam `AUTH_DEVELOPER_EMAILS`: chatbot dan dashboard dapat dibuka. Tautan dashboard muncul pada area akun.
5. Uji refresh; sesi tetap berlaku selama belum kedaluwarsa. Tombol **Keluar akun** mencabut sesi server dan mempertahankan history server pada akun yang sama. Tab lain pada browser yang sama menerima pemberitahuan logout.
6. Bila memakai allowlist, uji akun yang tidak diizinkan; tidak boleh tercipta sesi aplikasi.
7. Uji pembatalan Google dan callback yang diulang; aplikasi menampilkan alasan singkat dan dapat memulai login baru.

Pesan `redirect_uri_mismatch` berarti callback di Google Cloud tidak sama persis dengan `GOOGLE_REDIRECT_URI`, termasuk scheme, host, port dan path. Kesalahan cookie/sesi juga sering disebabkan pencampuran localhost dengan 127.0.0.1.

## Riwayat chat per akun

History kini disimpan di database akun server, dipisahkan berdasarkan user ID JST, dan tetap ada setelah logout. Rename/hapus ikut disimpan. LocalStorage lama tidak diimpor otomatis. Tunggu indikator Riwayat tersimpan di akun sebelum keluar atau menutup browser. Kontribusi history untuk training belum diaktifkan.

Lihat [cara tes dua akun dan batas penyimpanan](CHAT_HISTORY_2026-10-29.md).

## Sebelum online

- Daftarkan OAuth Client/redirect HTTPS sesuai domain nyata. `AUTH_PUBLIC_URL` dan callback harus memakai hostname serta scheme yang sama; path callback tetap `/api/auth/google/callback`.
- Sediakan routing satu origin ke frontend/API dan sesuaikan URL API frontend serta CORS. Jangan membuka origin/database/Ollama langsung ke internet.
- Cookie Secure otomatis aktif pada HTTPS. HTTP hanya diterima untuk localhost/127.0.0.1.
- Tetapkan akun developer, allowlist, korpus pilot yang boleh dibaca bersama, kebijakan data, backup dan pembatasan request di gateway. Implementasi ini membatasi maksimal 100 alur login yang masih aktif; ini belum menggantikan rate limit per IP di deployment.
- Token Google tidak disimpan setelah login. Query callback dibersihkan sebelum pencatatan access log aplikasi; proxy/gateway di depan aplikasi juga harus dikonfigurasi agar tidak mencatat query callback.
- Penghapusan akun/riwayat server, administrasi akun melalui UI, audit akses lengkap, Google Workspace hosted-domain policy, dan pencabutan semua perangkat masih pekerjaan lanjutan.

## Pengujian lokal

```powershell
cd D:\jakarta-smarttax-chatbot-ai\backend
uv run --locked python -m unittest discover -s tests -v
```

Tes mencakup login/callback simulasi, binding cookie browser, state sekali pakai, nonce, PKCE, token bertanda tangan dengan audience/issuer/expiry/signature salah, sesi hash/expiry/rotasi, CSRF, role developer, serta regresi RAG dan unggahan. Kredensial production dan API Google tidak dipakai dalam tes ini.

## Toleransi waktu verifikasi

Pada 29 Oktober 2026, komputer terukur sekitar satu detik di belakang respons waktu Google. Verifier memakai toleransi terbatas 30 detik untuk perbedaan jam kecil; signature, audience, issuer, dan expiry tetap divalidasi. Jam server tetap perlu tersinkron. Login Google nyata berhasil dikonfirmasi pengguna setelah penyesuaian ini. Pemeriksaan setelah hardening: 53 tes backend, TypeScript, dan build production frontend lolos.

Kesalahan pertukaran kode dan verifikasi token kini memakai kategori pesan yang spesifik. Log hanya mencatat kategori serta nama tipe error, bukan pesan mentah, token, code, atau client secret. Jika login gagal kembali, laporkan pesan kategori yang muncul di JST.


## Hasil audit 29 Oktober 2026

Laporan dan bukti pengujian tersedia di [GOOGLE_AUTH_IMPLEMENTATION_2026-10-29.md](GOOGLE_AUTH_IMPLEMENTATION_2026-10-29.md). Pemindaian dependensi frontend bersih; advisory ChromaDB masih tercatat; PyMuPDF telah diganti pypdf. Ini belum merupakan persetujuan untuk deployment publik.

Akun developer harus tercantum dalam konfigurasi serta mempunyai identitas email yang otoritatif bagi Google: Gmail terverifikasi atau akun Workspace terverifikasi dengan klaim `hd`. Email pihak ketiga tanpa klaim tersebut tidak memperoleh akses developer. Allowlist pilot menerapkan persyaratan otoritas yang sama.

CORS hanya mengizinkan `AUTH_PUBLIC_URL`. Pada HTTPS, cookie menggunakan awalan `__Host-`, Secure, HttpOnly, dan SameSite=Lax. Skema database autentikasi versi 3 mempertahankan status otoritas identitas dan pembatasan request, serta menambahkan tujuan daftar/masuk pada alur OAuth. Batas lokal meliputi login 20/menit per IP, pemeriksaan sesi 120/menit per IP, chat 10/menit per pengguna, dan API 120/menit per pengguna. Gateway publik tetap memerlukan konfigurasi proxy tepercaya dan perlindungan tambahan.

## Daftar dan masuk terpisah — 29 Oktober 2026

- Halaman awal menampilkan Masuk dengan Google dan tautan Belum punya akun? Daftar.
- `/api/auth/google/login` hanya menerbitkan sesi untuk akun JST yang sudah ada.
- `/api/auth/google/register` membuat akun setelah identitas Google terverifikasi, kemudian menerbitkan sesi.
- Akun belum terdaftar yang mencoba masuk mendapat pesan untuk mendaftar. Akun lama yang mencoba daftar mendapat pesan untuk masuk.
- Tujuan daftar/masuk disimpan di database flow dan terikat state/cookie, bukan dipercaya dari query callback.
- Akun dan sesi lama dipertahankan. Flow OAuth lama dimigrasikan sebagai login; tidak dapat membuat akun baru secara otomatis.
- Callback, Client ID, dan Client Secret tetap sama. Tidak perlu menyalin ulang `.env` atau membuat OAuth Client baru.
- Delapan tes baru menambah suite menjadi 61 tes backend; TypeScript dan build frontend lolos. Pengujian Google nyata untuk jalur baru masih perlu dilakukan pengguna.

Rincian: [Pemisahan pendaftaran dan login](GOOGLE_AUTH_REGISTRATION_2026-10-29.md).
