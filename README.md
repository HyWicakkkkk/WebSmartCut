# Web SmartCut — AI YouTube Video Clipper

Web SmartCut adalah aplikasi berbasis web (Software as a Service) yang berfungsi untuk memotong video YouTube berdurasi panjang menjadi klip video pendek berformat vertikal 9:16 (MP4) secara otomatis berdasarkan analisis momen paling ramai penonton (YouTube Most Replayed Heatmap).

- Pengembang: Muhammad Rizky Wicaksono
- NIM: 11241062
- Program Studi: Informatika
- Mata Kuliah: Implementasi dan Pengujian Perangkat Lunak (IPPL)

---

## Tech Stack & Arsitektur Sistem

- Frontend: React 18, Vite, Tailwind CSS, Lucide Icons
- Backend API: Python (Uvicorn ASGI), SQLAlchemy ORM, SQLite Database
- Keamanan: Password Hashing Bcrypt, JSON Web Token (JWT 24 Jam)
- Engine Pemrosesan Video: yt-dlp (ekstraktor stream YouTube), FFmpeg via imageio-ffmpeg (pemotong rasio 9:16 vertikal & AAC audio processing)

---

## Prasyarat Sistem (Prerequisites)

Sebelum memulai instalasi, pastikan perangkat komputer Anda telah terpasang perangkat lunak berikut:

1. Git
   - Cek versi: git --version
   - Unduh jika belum ada: https://git-scm.com/
2. Python (Versi 3.10 atau lebih baru) & pip
   - Cek versi: python --version (atau python3 --version)
   - Khusus Windows: Saat menginstal Python, pastikan mencentang kotak "Add python.exe to PATH".
3. Node.js (Versi 18 atau lebih baru) & npm
   - Cek versi: node -v dan npm -v
   - Unduh jika belum ada: https://nodejs.org/

---

## Panduan Instalasi & Menjalankan Aplikasi

Ikuti urutan langkah berikut secara berurutan dari awal sampai akhir:

### Langkah 1: Clone Repositori

1. Buka aplikasi Terminal (macOS/Linux) atau PowerShell / Command Prompt (Windows).
2. Tentukan folder tempat Anda ingin menyimpan proyek, lalu jalankan perintah:

git clone https://github.com/HyWicakkkkk/WebSmartCut.git

3. Masuk ke direktori proyek yang baru saja di-clone:

cd WebSmartCut

4. Periksa dan beralih ke branch pengerjaan utama:

git checkout Progress-UTS-Prototype

Catatan: Jika branch default repositori Anda sudah berada di branch yang tepat, lewati perintah checkout ini.

---

### Langkah 2: Konfigurasi & Menjalankan Backend (Server API)

Buka satu jendela terminal khusus untuk menjalankan backend:

1. Masuk ke direktori backend:

cd backend

2. Buat lingkungan virtual Python (virtual environment):
   - Pengguna Windows:
     python -m venv .venv
   - Pengguna macOS / Linux:
     python3 -m venv .venv

3. Aktifkan lingkungan virtual tersebut:
   - Pengguna Windows (PowerShell):
     .\.venv\Scripts\Activate.ps1
     (Jika muncul pesan script execution policy di PowerShell, gunakan CMD biasa: .\.venv\Scripts\activate.bat)
   - Pengguna Windows (Command Prompt / CMD):
     .\.venv\Scripts\activate.bat
   - Pengguna macOS / Linux:
     source .venv/bin/activate
   Tanda berhasil: Akan muncul tulisan (.venv) di awal baris perintah terminal.

4. Pasang seluruh pustaka dependensi yang dibutuhkan:

pip install -r requirements.txt

5. Jalankan server backend:

uvicorn main:app --reload --port 8000

6. Verifikasi Backend:
   - Server backend aktif di: http://127.0.0.1:8000
   - Dokumentasi antarmuka Swagger API dapat diakses di: http://127.0.0.1:8000/docs
   - Database SQLite (smartcut.db) beserta tabelnya akan otomatis dibuat saat backend pertama kali dinyalakan.

Penting: Biarkan jendela terminal backend ini tetap terbuka dan berjalan. Jangan ditutup selama menggunakan aplikasi.

---

### Langkah 3: Konfigurasi & Menjalankan Frontend (Antarmuka Web)

Buka jendela terminal baru (jendela kedua), lalu arahkan ke lokasi folder proyek:

1. Masuk ke direktori frontend:

cd WebSmartCut/frontend

2. Pasang paket dependensi Node.js:

npm install

3. Jalankan server frontend:

npm run dev

4. Verifikasi Frontend:
   - Buka browser web favorit Anda (Chrome / Brave / Edge / Firefox).
   - Akses URL: http://localhost:5173

---

### OPSI ALTERNATIF: Cara Cepat 1-Klik (Khusus Windows)

Jika Anda menggunakan OS Windows dan sudah menyelesaikan instalasi paket dependensi pada Langkah 2 dan 3 di atas, pada penggunaan berikutnya Anda cukup menjalankan berkas:

start_smartcut.bat

Berkas batch ini akan otomatis membuka 2 jendela terminal untuk menjalankan server backend dan frontend secara bersamaan.

---

## Panduan Skenario Pengujian Fitur (Demo Walkthrough)

Setelah kedua server berjalan dan halaman http://localhost:5173 terbuka, lakukan tahapan uji coba berikut:

1. Registrasi Akun Baru (Use Case 01)
   - Pada layar awal, klik teks "Register here".
   - Masukkan Nama Lengkap, Email, dan Password (minimal 8 karakter).
   - Klik tombol Register.
   - Akun baru otomatis berhasil terdaftar dengan hash kata sandi aman (Bcrypt) dan langsung diberikan status akun Free dengan jatah 2 kuota klip gratis.

2. Login & Sesi Pengguna (Use Case 02)
   - Jika logout, masuk kembali melalui form Login menggunakan email dan password yang telah didaftarkan.
   - Sistem akan menerbitkan token sesi JWT dengan masa berlaku 24 jam dan mengarahkan pengguna ke halaman Dashboard.

3. Validasi URL YouTube (Use Case 03)
   - Pada kolom input "Masukkan URL Youtube Disini", tempelkan tautan video YouTube berdurasi publik (contoh video podcast, wawancara, atau edukasi).
   - Sistem secara instan memvalidasi format link dan menampilkan kartu preview berupa judul asli video, nama channel, dan durasi total.

4. Pemotongan Video Otomatis 9:16 (Use Case 06)
   - Klik tombol hijau besar "Buat Klip Sekarang".
   - Kuota akun pengguna berkurang 1.
   - Sistem backend menjalankan worker di latar belakang:
     1. Menganalisis kurva lonjakan penonton (Most Replayed Heatmap) dari YouTube.
     2. Mengunduh stream audio-video asli via yt-dlp.
     3. Memotong segmen sepanjang 30–45 detik dan merender rasio vertikal 9:16 via FFmpeg.
   - Tunggu proses render selama kurang lebih 15–30 detik (indikator loading berputar).

5. Preview Video, Watermark, & Unduh MP4 (Use Case 09 & 10)
   - Setelah selesai, kartu hasil klip akan langsung tampil di bawah form input.
   - Klik tombol Play pada pemutar video: video berformat vertikal 9:16 dan audio asli terdengar jelas.
   - Perhatikan label Watermark SmartCut Free di bagian atas video (karena diproses menggunakan akun Free).
   - Rincian durasi waktu pemotongan, catatan transkrip segmen, serta riwayat waktu eksekusi server (process logs) tercantum di sebelah kanan.
   - Klik tombol "Unduh File MP4" untuk mengunduh video ke penyimpanan lokal perangkat.
   - Klip yang telah dibuat otomatis tercatat pada panel Riwayat Klip di bilah sisi kiri (sidebar).

6. Simulasi Upgrade Akun Premium (Use Case 11)
   - Klik pill "Status Akun : Free" di kanan atas, atau coba aktifkan centang pada opsi Auto Subtitle / Terjemahkan ke Indonesia.
   - Kotak dialog modal penawaran Upgrade ke Premium seharga Rp 39.000 akan muncul.
   - Klik tombol "Bayar Sekarang".
   - Sistem mensimulasikan validasi transaksi: status akun otomatis berubah menjadi Premium, batas kuota menjadi tak terbatas (unlimited), video berikutnya tidak memiliki watermark, serta fitur subtitle dan terjemahan terbuka.

---

## Kendala Umum & Solusi (Troubleshooting)

1. Port 8000 atau Port 5173 Sudah Terpakai (Address already in use):
   - Pastikan tidak ada aplikasi web lain yang berjalan di port 8000 atau 5173.
   - Buka Task Manager di Windows dan hentikan proses Python atau Node.js yang menggantung jika perlu.

2. Eksekusi Script PowerShell Dinonaktifkan di Windows (Execution Policy Error):
   - Jika saat menjalankan .\.venv\Scripts\Activate.ps1 muncul error kebijakan eksekusi, buka PowerShell sebagai Administrator lalu jalankan:
     Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   - Atau gunakan terminal Command Prompt (CMD) biasa dan jalankan .\.venv\Scripts\activate.bat.

3. Gagal Memproses Video YouTube Tertentu:
   - Pastikan komputer Anda terhubung ke internet yang stabil.
   - Pastikan link video YouTube yang dimasukkan bukan video yang bersifat Private, Age-restricted (dibatasi umur yang mewajibkan login akun dewasa), atau siaran langsung (Live Stream) yang sedang berlangsung.
