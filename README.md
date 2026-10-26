# Instagram Scraper (WIG-Scraper)

> **Developer:** [@W1ld](https://github.com/W1ld)  
> **Repository:** [https://github.com/W1ld/WIG-Scraper](https://github.com/W1ld/WIG-Scraper)

Aplikasi scraper Instagram modern berbasis Python dengan antarmuka CLI interaktif, penanganan pembatasan kuota (*Rate Limit*) otomatis, sistem *auto-checkpointing*, dan dukungan eksekusi otomatis (*headless / CLI arguments*).

---

## ✨ Keunggulan & Fitur Utama

- 💰 **100% Gratis & Tanpa API Berbayar:** Tidak memerlukan persetujuan Meta Developer App ataupun langganan Graph API yang rumit dan dibatasi izin bisnisnya.
- 🚀 **Akses Cepat & Ringan (Async Engine):** Mengakses endpoint web internal Instagram langsung via HTTP/2 dengan `asyncio` & `httpx`. Jauh lebih ringan (<50MB RAM) dan stabil tanpa membebani laptop dengan browser Selenium/Puppeteer.
- 🎯 **Scrape Profil (@username):** Mengambil daftar postingan feed & reels dari akun publik/privat (yang telah difollow) lengkap dengan metrik interaksi (likes, comments, views, caption, timestamp).
- 💬 **Pencarian 2-in-1 (Postingan + Komentar Sekaligus):** Mampu menarik postingan profil sekaligus otomatis menggali (*drill-down*) seluruh komentar & balasan komentar (*threaded replies*) pada masing-masing post secara relasional.
- 🔗 **Scrape Komentar Spesifik (URL / Shortcode):** Mengambil seluruh komentar dan balasan dari tautan postingan Instagram manapun (`/p/`, `/reel/`, atau `/tv/`).
- 🏷️ **Scrape Berdasarkan Hashtag (#hashtag):** Mengambil postingan publik terindeks pada hashtag tertentu.
- 👥 **Scrape Daftar Pengikut & Following (Followers / Following):** Mampu menarik daftar pengikut (*followers*) maupun daftar akun yang diikuti (*following*) dari akun publik mana pun secara lengkap dengan deteksi centang biru, status privat, foto profil kosong (*bot check*), dan status keaktifan Instagram Story.
- ⏱️ **Jeda Acak Humanis (*Configurable Random Delay*):** Dilengkapi jeda waktu acak yang dapat dikonfigurasi (`DELAY_MIN` & `DELAY_MAX` di `.env`, default 3–6 detik) untuk mensimulasikan perilaku penjelajahan manusia asli (*human-like browsing*), meminimalkan risiko tantangan keamanan Meta.
- 🛡️ **Manajemen Rate Limit & Auto-Checkpoint:** Jika terkena batas kuota (HTTP 429), program akan melakukan hitung mundur (*cooldown*) secara dinamis dan data yang sudah ditarik otomatis diamankan ke disk (`data/checkpoint_...csv`).
- 🔒 **Aman (Session Cookies Auth):** Menggunakan token sesi browser resmi (`sessionid` & `csrftoken`) tanpa perlu memasukkan password akun ke dalam skrip.
- 📊 **Dataset Lengkap & Siap Analisis:** Menyediakan metadata komprehensif mulai dari caption utuh, timestamp ISO & Unix, URLs media (foto, thumbnail video, video reels, slide carousel), daftar hashtag, mention user, hingga detail komentator.
- 📁 **Ekspor Fleksibel (Excel/CSV & JSON):** Mendukung format CSV `utf-8-sig` (langsung terbuka rapi di Microsoft Excel Windows dengan dukungan emoji lengkap) serta format JSON hierarkis.
- 💻 **Dual Mode Penggunaan:** Mendukung **Menu Interaktif (Terminal UI Rich)** untuk pemakaian harian yang ramah pemula, serta **Mode Command-Line (CLI Flags)** untuk otomasi skrip / data pipeline.

---

## 📊 Tabel Perbandingan Metode Scraping Instagram

| Fitur / Parameter | **Octoparse** | **Selenium / Playwright** | **Instaloader / Instagrapi** | **WIG-Scraper (Tool Ini)** |
| :--- | :---: | :---: | :---: | :---: |
| **Biaya & Batasan** | ❌ Berbayar ($89–$249/bln) | ✅ Gratis | ✅ Gratis | ✅ **100% Gratis & Open-Source** |
| **Kecepatan & Penggunaan RAM** | ❌ Lambat & Boros RAM (500MB+) | ❌ Berat & Boros RAM (400MB+) | ⚠️ Sedang | ⚡ **Sangat Cepat & Ringan (<50MB)** |
| **Scrape Postingan + Komentar** | ❌ Sangat Rumit | ⚠️ Perlu konfigurasi DOM rumit | ⚠️ Perlu loop manual | 🎯 **2-in-1 Otomatis (Relasional)** |
| **Bebas Masalah Driver Browser** | ⚠️ Terikat Browser Internal | ❌ Sering error ChromeDriver | ✅ Ya | ✅ **Bebas Driver (Pure Async HTTP)** |
| **Simulasi Jeda Humanis** | ⚠️ Manual | ⚠️ Manual Scripting | ⚠️ Terbatas | ⏱️ **Bawaan & Dapat Diatur (.env)** |
| **Risiko Kehilangan Data** | ⚠️ Rentan Task Error | ❌ Rentan crash di tengah jalan | ❌ Tanpa auto-save | 🛡️ **Auto-Checkpoint ke Disk** |
| **Kesiapan Ekspor Excel Windows** | ⚠️ Sering rusak encoding emoji | ⚠️ Perlu scripting export | ⚠️ Format teks dasar | 📊 **Bawaan `utf-8-sig` Siap Excel** |

---

## ⚠️ Hal-Hal Penting yang Perlu Diperhatikan

### 1. Cara Mengambil `sessionid` dari Browser (Hanya Butuh 15 Detik)
Instagram mewajibkan sesi login aktif untuk membaca detail profil dan komentar. Program ini memanfaatkan **Session Cookie** dari browser Anda:

1. Buka [https://www.instagram.com](https://www.instagram.com) di browser (Chrome / Edge / Firefox) dan pastikan Anda sudah login.
2. Tekan tombol **F12** (Developer Tools) pada keyboard Anda.
3. Masuk ke tab **Application** (atau tab **Storage** pada Firefox).
4. Pada panel sebelah kiri, pilih **Cookies** ➔ klik `https://www.instagram.com`.
5. Cari dan salin nilai (*Value*) dari:
   - **`sessionid`** (Wajib)
   - **`csrftoken`** (Disarankan)
   - **`ds_user_id`** (Opsional)
6. Tempelkan ke dalam file `.env` atau masukkan saat diminta oleh program di terminal.

> [!TIP]
> **Rekomendasi Keamanan:** Disarankan menggunakan akun sekunder / akun cadangan (*dummy account*) saat melakukan scraping data dalam volume besar untuk menjaga keamanan akun utama Anda dari tantangan verifikasi Meta (*checkpoint*).

### 2. Format Output Data
* **CSV (`utf-8-sig`)**: Dapat langsung dibuka dengan rapi di Microsoft Excel, Google Sheets, atau diimpor ke Pandas/R. Mendukung karakter khusus bahasa Indonesia dan emoji tanpa berantakan (*mojibake*).
* **JSON**: Struktur data hierarkis lengkap dengan metadata media dan interaksi.
* File hasil scraping otomatis tersimpan di folder `data/`.

---

## 📁 Struktur Proyek

```
WIG-Scraper/
├── .env.example          # Template konfigurasi kredensial Instagram
├── .env                  # Konfigurasi aktif (sessionid, csrftoken, delay)
├── requirements.txt      # Daftar pustaka dependensi (httpx, pandas, rich, dll.)
├── config.py             # Pengaturan konfigurasi & environment variable
├── client_manager.py     # Autentikasi sesi & manajemen cookies Instagram
├── parser.py             # Parser metadata Postingan, Komentar, & Profil
├── scraper.py            # Mesin scraping (Profile, Drill-down, Comments, Hashtag)
├── exporter.py           # Ekspor data ke CSV & JSON serta auto-checkpoint
├── main.py               # Entrypoint (Menu interaktif Rich & CLI arguments)
└── data/                 # Folder penyimpanan hasil data scraping & checkpoint
```

---

## 🚀 Panduan Setup & Cara Menjalankan (Step-by-Step)

### Langkah 1: Prasyarat Python
Pastikan komputer Anda sudah terpasang **Python 3.10 atau versi yang lebih baru**.
Jika belum terpasang di Windows, pasang melalui terminal:
```cmd
winget install Python.Python.3
```
*(Atau unduh installer resmi dari [python.org/downloads](https://www.python.org/downloads/) dan pastikan mencentang **"Add python.exe to PATH"**).*

---

### Langkah 2: Buat & Aktifkan Virtual Environment (Disarankan)
Sangat disarankan menggunakan Virtual Environment (`.venv`) agar seluruh dependensi terisolasi rapi dan tidak bentrok dengan library Python lain di sistem Anda.

1. **Buat Virtual Environment:**
   Buka terminal di folder proyek ini (`WIG-Scraper`), lalu jalankan:
   ```bash
   python -m venv .venv
   ```

2. **Aktifkan Virtual Environment:**
   * **Windows (PowerShell):**
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
     > [!TIP]
     > Jika muncul pesan error *Execution Policy* di PowerShell, jalankan perintah ini sekali saja:
     > ```powershell
     > Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
     > ```
   * **Windows (Command Prompt / CMD):**
     ```cmd
     .\.venv\Scripts\activate.bat
     ```
   * **Linux / macOS:**
     ```bash
     source .venv/bin/activate
     ```

   *Tanda berhasil:* Akan muncul teks indikator `(.venv)` di sebelah kiri prompt terminal Anda.

---

### Langkah 3: Install Dependensi Library
Setelah virtual environment aktif `(.venv)`, pasang seluruh pustaka yang dibutuhkan:

```bash
pip install -r requirements.txt
```

---

### Langkah 4: Konfigurasi Kredensial `.env`
Buka file `.env` di teks editor, lalu masukkan nilai cookie yang sudah disalin dari browser:

```env
IG_SESSION_ID=nilai_sessionid_dari_browser
IG_CSRF_TOKEN=nilai_csrftoken_dari_browser
IG_DS_USER_ID=nilai_ds_user_id_dari_browser

# Jeda acak antar request (detik)
DELAY_MIN=3.0
DELAY_MAX=6.0
```

---

### Langkah 5: Menjalankan Program

#### Mode 1: Menu Interaktif Terminal (Sangat Mudah Digunakan)
Jalankan program tanpa argumen tambahan:
```bash
python main.py
```

Anda akan disajikan menu interaktif yang elegan:
```
==================================================
WIG-Scraper (Instagram Data Extraction Suite)
==================================================
1. Scrape Postingan dari Profil / Akun (@username)
2. Scrape Postingan Profil + Komentar (2-in-1 Drill-Down)
3. Scrape Seluruh Komentar dari Link / URL Postingan
4. Scrape Komentar dari Beberapa URL Sekaligus (Batch)
5. Scrape Postingan Berdasarkan Hashtag (#hashtag)
6. Scrape Daftar Pengikut Akun Publik (Followers) [BARU]
7. Scrape Daftar Akun yang Diikuti (Following) [BARU]
8. Uji / Perbarui Cookies Sesi Instagram
0. Keluar dari Aplikasi
```

---

#### Mode 2: Mode Baris Perintah (CLI Arguments untuk Otomasi)
Bagi Anda yang ingin mengintegrasikan scraper ini ke dalam skrip otomatis atau cron job:

1. **Scrape Postingan Profil Akun:**
   ```bash
   python main.py --profile natgeo --limit 50 --format both
   ```

2. **Scrape Postingan Profil + Seluruh Komentar (2-in-1 Drill-down):**
   ```bash
   python main.py --profile kemnaker --limit 20 --drill-down --max-comments 30
   ```

3. **Scrape Komentar dari Tautan Postingan Spesifik:**
   ```bash
   python main.py --comments https://www.instagram.com/p/DBabc123/ --limit 100
   ```
   *(Atau cukup masukkan shortcode: `python main.py --comments DBabc123 --limit 100`)*

4. **Scrape Komentar Beberapa Post Sekaligus (Batch URLs):**
   ```bash
   python main.py --batch-urls "DBabc123,DBxyz789" --limit 50
   ```
   *(Atau gunakan file teks yang berisi daftar URL: `python main.py --batch-urls links.txt --limit 50`)*

5. **Scrape Postingan Berdasarkan Hashtag:**
   ```bash
   python main.py --hashtag teknologi --limit 40
   ```

6. **Scrape Daftar Followers (Pengikut) Akun Publik:**
   ```bash
   python main.py --followers cnnindonesia --limit 100
   ```
   *(Secara otomatis diekspor ke format CSV secara default).*

7. **Scrape Daftar Following (Akun yang Diikuti):**
   ```bash
   python main.py --following cnnindonesia --limit 50
   ```

8. **Paksa Input Ulang Cookies:**
   ```bash
   python main.py --force-login
   ```

---

## 📊 Daftar Atribut Metadata Output (CSV / JSON)

Dataset yang dihasilkan mencakup lebih dari 20 atribut lengkap untuk kebutuhan analitik, sentimen, dan riset:

| Nama Kolom | Tipe | Deskripsi |
| :--- | :--- | :--- |
| `row_type` | String | Jenis baris data (`post`, `comment`, atau `reply`). |
| `post_id` | String | ID numerik unik postingan Instagram. |
| `shortcode` | String | Kode unik URL postingan (misal `DBabc123`). |
| `post_url` | String | URL lengkap menuju postingan (`https://www.instagram.com/p/...`). |
| `post_type` | String | Format postingan (`image`, `video`, `carousel`, atau `reel`). |
| `caption` | String | Teks caption lengkap dari postingan. |
| `created_at` | String | Tanggal dan jam pembuatan format ISO UTC (`YYYY-MM-DD HH:MM:SS UTC`). |
| `timestamp` | Integer | Waktu pembuatan dalam format Unix Epoch timestamp. |
| `likes_count` | Integer | Jumlah penyuka (*likes*) pada postingan atau komentar. |
| `comments_count`| Integer | Jumlah komentar pada post, atau jumlah balasan (*child replies*) pada komentar. |
| `views_count` | Integer | Jumlah tayangan video/reels (jika format video). |
| `is_video` | Boolean | Menandakan apakah postingan berupa video atau bukan. |
| `display_url` | String | Tautan URL resolusi tinggi gambar utama atau thumbnail video. |
| `video_url` | String | Tautan langsung file video (jika postingan berupa video/reels). |
| `carousel_media_urls`| String | Daftar URL seluruh slide gambar/video jika berupa album *carousel*. |
| `hashtags` | String | Daftar hashtag yang diekstrak dari caption postingan. |
| `tagged_users` | String | Daftar username yang di-mention atau di-tag dalam caption. |
| `location` | String | Nama lokasi geotagging yang disematkan pada postingan. |
| `owner_username`| String | Username pembuat postingan. |
| `owner_full_name`| String | Nama lengkap pemilik akun pembuat postingan. |
| `owner_id` | String | ID unik pengguna Instagram pembuat postingan. |
| `parent_post_id`| String | ID postingan induk (untuk baris komentar/reply). |
| `parent_comment_id`| String | ID komentar induk jika baris ini merupakan balasan (*reply*). |
| `comment_id` | String | ID unik komentar. |
| `comment_text` | String | Isi teks komentar pengguna. |
| `comment_author_username`| String | Username dari pengguna yang menulis komentar. |
| `comment_author_name` | String | Nama profil pengguna yang menulis komentar. |
| `comment_author_id` | String | ID unik pengguna yang menulis komentar. |
| `comment_author_pic` | String | URL foto profil dari pengguna yang berkomentar. |
| `comment_author_verified`| Boolean | Status centang biru / verifikasi dari akun komentator. |

### 👥 Atribut Khusus Data Pengikut (Followers & Following)

| Nama Kolom | Tipe | Deskripsi |
| :--- | :--- | :--- |
| `row_type` | String | Jenis baris data (`follower` atau `following`). |
| `target_username` | String | Username akun target publik yang di-scrape. |
| `target_user_id` | String | ID numerik unik akun target yang di-scrape. |
| `user_id` | String | ID unik Instagram (PK) dari akun pengikut / following. |
| `username` | String | Handle username pengguna (`@username`). |
| `full_name` | String | Nama lengkap atau nama tampilan pengguna. |
| `profile_url` | String | Tautan langsung menuju laman profil pengikut. |
| `is_private` | Boolean | Status akun privat (`True`) atau publik (`False`). |
| `is_verified` | Boolean | Status lencana centang biru resmi (*verified badge*). |
| `has_anonymous_profile_picture` | Boolean | Menandakan apakah pengguna memakai foto default/kosong (*indikator bot*). |
| `has_active_story` | Boolean | Menandakan apakah pengguna sedang memiliki Instagram Story aktif (24 jam terakhir). |
| `latest_reel_media` | Integer | Unix timestamp media Story terbaru. |
| `profile_pic_url` | String | Tautan gambar foto profil pengikut. |
| `fbid_v2` | String | ID akun Facebook yang terhubung (*jika ada*). |

---

## 🛠️ Pemecahan Masalah (Troubleshooting & FAQ)

1. **Muncul pesan `"Akun terkena checkpoint tantangan verifikasi"`:**
   - Meta mendeteksi aktivitas login yang tidak biasa dan meminta verifikasi pemilik akun.
   - **Solusi:** Buka browser Anda, akses [instagram.com](https://www.instagram.com), dan selesaikan tantangan verifikasi (SMS/Email/CAPTCHA) yang muncul. Setelah akun normal kembali, salin nilai `sessionid` terbaru ke `.env`.

2. **Muncul pesan `"Terkena Rate Limit Instagram (HTTP 429)"`:**
   - Anda melakukan permintaan data terlalu cepat dalam waktu singkat.
   - **Solusi:** Biarkan program berjalan. Program memiliki sistem *auto-cooldown* otomatis yang akan menunggu hingga kuota pulih dan langsung melanjutkan penarikan data tanpa kehilangan progres berkat *auto-checkpoint*. Anda juga bisa menaikkan `DELAY_MIN` dan `DELAY_MAX` di `.env` (misalnya menjadi `4.0` dan `8.0`).

3. **Status akun privat:**
   - Postingan akun privat hanya dapat ditarik jika akun Instagram yang Anda gunakan di browser sudah mem-follow akun target tersebut.

---

## ⚖️ Lisensi & Disclaimer

Proyek ini dibuat untuk tujuan edukasi, riset data, dan analisis akademis. Penggunaan program ini harus mematuhi Ketentuan Layanan (*Terms of Service*) platform terkait. Pengembang tidak bertanggung jawab atas penyalahgunaan atau tindakan penegakan akun oleh pihak ketiga.
