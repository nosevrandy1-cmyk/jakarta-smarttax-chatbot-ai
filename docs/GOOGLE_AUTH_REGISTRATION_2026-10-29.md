# Pemisahan pendaftaran dan login Google JST

Tanggal: 29 Oktober 2026 (Asia/Jakarta). Branch: `feat/google-auth`.

## Perilaku

| Tindakan | Status akun | Hasil |
| --- | --- | --- |
| Daftar dengan Google | Belum ada | Verifikasi identitas, buat akun JST, masuk chatbot |
| Masuk dengan Google | Sudah ada | Verifikasi identitas dan buat sesi |
| Masuk dengan Google | Belum ada | Tolak; tampilkan pesan akun belum terdaftar dan arahkan tampilan ke Daftar |
| Daftar dengan Google | Sudah ada | Tolak tanpa mengubah profil/sesi; arahkan tampilan ke Masuk |

Pencocokan akun menggunakan provider dan Google subject (`sub`), bukan email saja. Akun yang sudah dibuat sebelumnya dianggap terdaftar. Role tetap berdasarkan konfigurasi developer di server dan otoritas identitas; form daftar tidak menerima input role. Kebijakan allowlist tetap diterapkan.

## Implementasi

Backend menyediakan endpoint awal register terpisah dengan callback yang sama. Intent `login` atau `register` disimpan bersama state OAuth dalam database. Callback mengambil intent dari flow yang telah diverifikasi, sehingga parameter tambahan dari browser tidak dapat mengubah login menjadi pendaftaran.

Pemeriksaan status akun, pembaruan profil, dan penerbitan sesi berada dalam transaksi SQLite yang sama (`BEGIN IMMEDIATE`). Login yang ditolak tidak membuat akun atau sesi. Pendaftaran ganda tidak mengubah nama/email profil yang ada. State tetap sekali pakai, nonce/PKCE tetap digunakan, dan login/register berbagi pembatasan percobaan yang sama.

Migrasi database versi 2 ke versi 3 menambahkan kolom `auth_flows.intent` dengan default `login`. Akun, ID internal, dan sesi lama dipertahankan. Migrasi versi 1 juga tetap didukung. Tidak perlu menghapus database atau menyalin `.env` ulang.

Frontend menyediakan halaman kartu daftar/masuk yang dapat ditukar lewat tombol teks. Pesan callback `not_registered` menampilkan tombol daftar; `already_registered` menampilkan tombol masuk. Tidak dibuat password JST.

## Verifikasi

- 62 tes backend lolos: 53 regresi dan 9 tes registrasi/persetujuan.
- Tes mencakup akun baru ditolak login tanpa penulisan database, pendaftaran berhasil, akun lama bisa masuk, pendaftaran ganda ditolak, query callback tidak dapat mengganti intent, Google subject berbeda tidak dianggap akun sama, state/cookie wajib, serta migrasi menjaga akun/sesi/flow lama.
- TypeScript noEmit/noUnusedLocals lolos.
- Build production frontend terisolasi lolos; direktori dev `.next` tidak ditimpa.
- Pengguna mengonfirmasi alur terbaru sudah sesuai setelah mencoba ulang pada 29 Oktober 2026. Ini merupakan konfirmasi pengguna, bukan rekaman UAT seluruh kombinasi akun. Tes endpoint memakai pertukaran Google yang dimock; tes parameter OAuth memastikan persetujuan diminta khusus saat daftar.
- Advisory ChromaDB sebelumnya tetap berlaku; perubahan ini tidak menutup temuan dependensi tersebut.

## Berkas

- `backend/app/auth.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_auth_hardening.py`
- `backend/tests/test_registration.py`
- `frontend/src/components/AuthProvider.tsx`
- `frontend/src/app/auth.css`
- `docs/GOOGLE_AUTH_SETUP.md`

## Uji manual berikutnya

1. Gunakan akun Google pengujian yang belum terdaftar dan diizinkan konfigurasi Google Cloud/allowlist.
2. Pilih Masuk dengan Google: setelah verifikasi, aplikasi harus menolak dengan pesan belum terdaftar.
3. Pilih Daftar dengan Google: selesaikan verifikasi, lalu chatbot harus terbuka.
4. Dalam sesi browser terpisah, pilih Daftar dengan akun yang sama: aplikasi meminta masuk, tidak membuat akun kedua.
5. Pilih Masuk dengan akun yang sudah terdaftar: chatbot terbuka; dashboard tetap mengikuti role developer.

Pakai profil browser terpisah untuk pengujian agar sesi aktif dan riwayat pengguna tidak perlu dikeluarkan. Screenshot tidak disimpan di proyek, sesuai keputusan pengguna.

Pembaruan persetujuan: pendaftaran menggunakan `prompt=select_account consent` agar Google meminta persetujuan kembali; login tetap `select_account`. Halaman daftar menjelaskan penerimaan nama, email, dan ID Google. Tes parameter OAuth tambahan menjaga scope dan callback tetap sama. Total suite terbaru: 62 tes backend. Reset akun lokal untuk pengujian dilakukan atas permintaan pengguna; tidak menghapus izin pada akun Google.
