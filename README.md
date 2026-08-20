# Twitter / X Scraper (WX-Scrapper)

> **Developer:** [@W1ld](https://github.com/W1ld)  
> **Repository:** [https://github.com/W1ld/WX-Scrapper](https://github.com/W1ld/WX-Scrapper)

Aplikasi scraper Twitter (X) berbasis Python dengan antarmuka CLI interaktif, fitur penanganan Rate Limit otomatis, auto-checkpointing, dan mode headless/command-line arguments.

---

## ⚠️ Hal-Hal Penting yang Perlu Diperhatikan

1. **Autentikasi Sesi Browser (`auth_token` & `ct0`)**:
   - Twitter mewajibkan autentikasi akun untuk membaca tweet, search, dan komentar.
   - Program ini menggunakan **Session Cookies (`auth_token` & `ct0`)** dari browser Anda sehingga **tidak memerlukan username / password** sama sekali.
   - **100% Bebas CAPTCHA & Akun Terkunci**: Menghindari pemblokiran bot saat proses login.
   - Sesi otomatis disimpan ke `cookies.json` untuk penggunaan seterusnya.

2. **Cara Mendapatkan `auth_token` & `ct0` dari Browser (15 Detik)**:
   - Buka `https://x.com` di browser (Chrome / Edge / Firefox) yang sudah login ke akun Twitter.
   - Tekan **F12** (Developer Tools) ➔ Masuk ke tab **Application** (atau **Storage** di Firefox).
   - Di panel sebelah kiri, klik **Cookies** ➔ `https://x.com`.
   - Salin nilai (*Value*) dari **`auth_token`** dan **`ct0`** ke file `.env`.

3. **Rate Limit (HTTP 429) & Keamanan Akun**:
   - Program dilengkapi **Random Delay** (default 3 - 6 detik) antar request untuk menyerupai perilaku manusia.
   - Dilengkapi **Dynamic Rate Limit Handler**: Program membaca timestamp *real-time* dari server Twitter (`x-rate-limit-reset`) dan melakukan hitung mundur otomatis (*countdown*). Begitu masa cooldown selesai, program **secara otomatis melanjutkan scraping** tanpa crash.
   - **Auto-Checkpoint Backup**: Data yang sudah didapat otomatis disimpan secara berkala ke folder `data/checkpoint_...csv` sehingga aman dari gangguan koneksi/listrik.

4. **Format Output Data**:
   - **CSV**: Encoding `utf-8-sig` (langsung terbaca rapi di Microsoft Excel, mendukung karakter bahasa Indonesia dan emoji).
   - **JSON**: Terstruktur rapi dengan seluruh metadata tweet dan profil user.
   - Kolom `row_type` membedakan `main_tweet` dan `reply`. Komentar ditautkan dengan `parent_tweet_id`.
   - File output otomatis disimpan di folder `data/`.

---

## 📁 Struktur Proyek

```
WX-Scrapper/
├── .env.example          # Template konfigurasi kredensial
├── requirements.txt      # Daftar pustaka dependensi
├── config.py             # Pengaturan konfigurasi & environment variable
├── client_manager.py     # Autentikasi & manajemen cookies sesi
├── parser.py             # Parser metadata Tweet, Replies, & User
├── scraper.py            # Mesin scraping (Search, Search + Replies per tweet, Tweet Detail)
├── exporter.py           # Ekspor data ke CSV & JSON serta auto-checkpoint
├── main.py               # Entrypoint (Menu interaktif & CLI arguments)
└── data/                 # Folder hasil penyimpanan data scraping & checkpoint
```

---

## 🚀 Panduan Setup & Cara Menjalankan (Step-by-Step)

### Prasyarat: Instalasi Python (Jika Belum Terpasang)
Program ini membutuhkan **Python 3.10 atau versi yang lebih baru**. Jika Anda belum menginstall Python di komputer Anda:

- **Windows:**
  - Unduh installer resmi dari situs [python.org/downloads](https://www.python.org/downloads/).
  - ⚠️ **PENTING:** Saat menjalankan installer di Windows, pastikan mencentang opsi **"Add python.exe to PATH"** di bagian bawah sebelum menekan tombol *Install Now*.
  - Atau install versi terbaru langsung melalui terminal Windows:
    ```cmd
    winget install Python.Python.3
    ```
- **Linux (Ubuntu / Debian):**
  ```bash
  sudo apt update && sudo apt install python3 python3-pip python3-venv -y
  ```
- **macOS (via Homebrew):**
  ```bash
  brew install python
  ```

*Cek apakah Python sudah terpasang dengan menjalankan: `python --version` atau `python3 --version`.*

---

### Langkah 1: Clone Repositori & Masuk ke Direktori Proyek
Buka terminal (PowerShell / Command Prompt / Bash), clone repositori ini, lalu masuk ke folder proyek:
```bash
git clone https://github.com/W1ld/WX-Scrapper.git
cd WX-Scrapper
```

### Langkah 2: (Opsional tapi Disarankan) Buat & Aktifkan Virtual Environment
Membuat virtual environment memastikan pustaka Python terisolasi dengan rapi:

- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
- **Windows (CMD):**
  ```cmd
  python -m venv venv
  venv\Scripts\activate.bat
  ```
- **Linux / macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### Langkah 3: Install Semua Dependensi
Pastikan Python 3.10+ telah terpasang, lalu instal paket yang dibutuhkan:
```bash
pip install -r requirements.txt
```

### Langkah 4: Konfigurasi File Lingkungan (`.env`)
Salin file template `.env.example` menjadi file `.env`:

- **Windows PowerShell / Linux / Mac:**
  ```bash
  cp .env.example .env
  ```
- **Windows CMD:**
  ```cmd
  copy .env.example .env
  ```

Buka file **`.env`** dengan text editor (VS Code, Notepad, dll) dan isi cookie `auth_token` dan `ct0` Anda:
```ini
AUTH_TOKEN=isi_auth_token_dari_browser_anda
CT0=isi_ct0_dari_browser_anda

# Pengaturan Delay antar request (detik)
DELAY_MIN=3.0
DELAY_MAX=6.0

# Bahasa antarmuka (id-ID atau en-US)
DEFAULT_LANG=id-ID
```

### Langkah 5: Jalankan Program
Jalankan program menggunakan menu interaktif:
```bash
python main.py
```
*(Program akan memvalidasi sesi cookie Anda dan langsung siap digunakan).*

---

## 🖥️ Cara Menjalankan

### Mode 1: Menu Interaktif (Terminal UI)
Jalankan perintah:
```bash
python main.py
```

Pilihan menu yang tersedia:
```
==================================================
  WX-Scrapper (Twitter / X Data Extraction Suite) 
==================================================
Pilih Fitur Scraping:
  1. Cari Tweet berdasarkan Kata Kunci / Hashtag (Hanya Tweet Utama)
  2. Ambil Detail Tweet Tunggal & Balasan / Komentar (dari URL / Tweet ID)
  3. Cari Tweet + Ambil Komentar/Replies untuk Setiap Tweet (Kombinasi Fitur 1 & 2)
  4. Login Ulang & Perbarui file cookies.json
  5. Keluar (Exit)
```

> **Contoh Penggunaan Menu 3 (Kombinasi)**:
> Jika Anda memilih menu **3**, masukkan kata kunci `Monas`, pilih urutan `top`, jumlah tweet `100`, dan jumlah komentar per tweet `5`:
> - Program akan mencari 100 post `top` dengan kata `Monas`.
> - Untuk setiap tweet:
>   - Jika tidak ada komentar (0), tidak diambil apa-apa.
>   - Jika ada 1 - 5 komentar, diambil semuanya.
>   - Jika ada lebih dari 5 komentar, diambil 5 komentar teratas.
> - Hasilnya akan diekspor rapi ke CSV & JSON di folder `data/`.

---

### Mode 2: Command Line (Headless / Otomatisasi Skrip)

#### A. Cari Tweet + Ambil Komentar per Tweet (Kombinasi)
```bash
# Mengambil 100 tweet 'langit' urutan top beserta maks 5 komentar untuk setiap tweet
python main.py --mode combo --query "langit" --sort top --count 100 --replies-per-tweet 5 --format csv
```

#### B. Cari Tweet Saja (Hanya Tweet Utama)
```bash
python main.py --mode search --query "AI Indonesia" --sort latest --count 50 --format csv
```

#### C. Detail Tweet Tunggal & Komentar
```bash
python main.py --mode tweet --id "https://x.com/username/status/1234567890123456789" --replies 50 --format csv
```

#### D. Perbarui Sesi Cookies
```bash
python main.py --mode login
```

---

## 📊 Data Metadata yang Diambil

File CSV dan JSON yang diekspor memuat kolom data berikut:
- **Tipe & Relasi Data**:
  - `row_type`: `main_tweet` (tweet utama) atau `reply` (komentar).
  - `parent_tweet_id`: ID tweet utama tempat komentar berada.
- **Informasi Tweet**:
  - `tweet_id`: ID unik status tweet.
  - `url`: Link lengkap ke tweet (`https://x.com/.../status/...`).
  - `created_at`: Waktu tweet diposting.
  - `text`: Isi teks tweet secara utuh (*untruncated*).
  - `lang`: Kode bahasa tweet.
  - `likes`, `retweets`, `replies`, `quotes`, `bookmarks`, `views`: Metrik interaksi tweet.
  - `is_reply`, `in_reply_to_tweet_id`: Status balasan/thread.
  - `is_quote`, `quoted_tweet_id`: Status quote tweet.
  - `hashtags`, `urls`, `media_types`, `media_urls`: Tautan dan lampiran media (foto/video/gif).
- **Informasi Penulis (User)**:
  - `user_id`: ID unik pengguna Twitter.
  - `username`: Handle/Screen name (contoh: `@elonmusk`).
  - `name`: Nama tampilan (*Display Name*).
  - `user_bio`: Bio profil user.
  - `user_followers_count`, `user_following_count`: Jumlah follower dan following.
  - `user_verified`: Status verifikasi akun (centang biru/verified).
  - `user_location`: Lokasi pengguna.
  - `user_avatar`: URL gambar profil pengguna.
