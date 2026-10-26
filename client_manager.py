import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
import httpx
import config

from rich.console import Console

console = Console()

# ID Aplikasi Web Resmi Instagram
IG_APP_ID = "936619743392459"

class InstagramClient:
    """
    Klien Instagram Web Async berbasis cookie sesi peramban (sessionid & csrftoken).
    Berjalan langsung via HTTP/2 tanpa beban peramban Selenium/Playwright.
    """
    def __init__(
        self,
        session_id: str = "",
        csrf_token: str = "",
        ds_user_id: str = "",
        proxy: Optional[str] = None
    ):
        self.session_id = session_id
        self.csrf_token = csrf_token
        self.ds_user_id = ds_user_id
        self.proxy = proxy

        self.headers = {
            'authority': 'www.instagram.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,id;q=0.8',
            'referer': 'https://www.instagram.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'x-asbd-id': '129477',
            'x-csrftoken': self.csrf_token or '',
            'x-ig-app-id': IG_APP_ID,
            'x-ig-www-claim': '0',
            'x-requested-with': 'XMLHttpRequest',
            'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        }

        self.cookies = {}
        if self.session_id:
            self.cookies['sessionid'] = self.session_id
        if self.csrf_token:
            self.cookies['csrftoken'] = self.csrf_token
        if self.ds_user_id:
            self.cookies['ds_user_id'] = self.ds_user_id

        self._http: Optional[httpx.AsyncClient] = None

    def get_http_client(self) -> httpx.AsyncClient:
        """Mengembalikan instans httpx.AsyncClient yang digunakan kembali."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                headers=self.headers,
                cookies=self.cookies,
                proxy=self.proxy,
                timeout=30.0,
                follow_redirects=True,
                http2=True
            )
        return self._http

    async def close(self):
        """Menutup koneksi HTTP client."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def test_session(self) -> Tuple[bool, str]:
        """
        Menguji validitas cookie sesi ke endpoint Instagram.
        Mengembalikan (is_valid, message).
        """
        http = self.get_http_client()
        try:
            # Uji sesi melalui endpoint tags (sangat andal: mengembalikan HTTP 200 jika sesi aktif,
            # dan HTTP 302/redirect jika cookie invalid atau belum login).
            url = 'https://www.instagram.com/api/v1/tags/web_info/?tag_name=instagram'
            r = await http.get(url, headers={'referer': 'https://www.instagram.com/explore/tags/instagram/'}, timeout=15.0)
            if r.status_code == 200:
                data = r.json()
                if "data" in data or data.get("status") == "ok":
                    return True, "Sesi Instagram aktif dan terverifikasi."
                return False, "Format respon tidak sesuai."
            elif r.status_code == 302:
                return False, "Sesi login tidak valid atau sudah kedaluwarsa (diarahkan ke login)."
            elif r.status_code == 429:
                return False, "Rate limit terdeteksi saat uji koneksi. Tunggu sejenak."
            elif "checkpoint_required" in r.text:
                return False, "Akun terkena checkpoint tantangan verifikasi oleh Instagram."
            else:
                return False, f"Respon server HTTP {r.status_code}."
        except httpx.TimeoutException:
            return False, "Koneksi ke Instagram timeout (lambat). Periksa koneksi internet Anda."
        except Exception as e:
            return False, f"Koneksi gagal: {str(e)}"

async def get_instagram_client(force_login: bool = False) -> InstagramClient:
    """
    Inisialisasi klien Instagram:
    1. Cek file cookies.json yang sudah tersimpan.
    2. Cek variabel environment dari .env.
    3. Jika belum ada atau force_login=True, minta input interaktif.
    """
    cookies_path = Path(config.COOKIES_FILE)

    # 1. Coba gunakan file cookies.json
    if not force_login and cookies_path.exists():
        try:
            with open(cookies_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            session_id = saved.get("sessionid", "") or saved.get("IG_SESSION_ID", "")
            csrf_token = saved.get("csrftoken", "") or saved.get("IG_CSRF_TOKEN", "")
            ds_user_id = saved.get("ds_user_id", "") or saved.get("IG_DS_USER_ID", "")
            
            if session_id:
                console.print(f"[cyan][*][/cyan] Memuat cookies sesi dari: [bold]{cookies_path}[/bold]")
                client = InstagramClient(
                    session_id=session_id,
                    csrf_token=csrf_token,
                    ds_user_id=ds_user_id,
                    proxy=config.PROXY
                )
                with console.status("[bold cyan]Memverifikasi sesi cookies...[/bold cyan]", spinner="dots"):
                    valid, msg = await client.test_session()
                
                if valid:
                    console.print(f"[bold green][✓][/bold green] [green]{msg}[/green]\n")
                    return client
                else:
                    console.print(f"[bold yellow][!][/bold yellow] [yellow]Cookies di cookies.json tidak valid: {msg}[/yellow]")
        except Exception as e:
            console.print(f"[bold red][!][/bold red] Gagal membaca cookies.json: {e}")

    # 2. Gunakan variabel dari .env
    if not force_login and config.IG_SESSION_ID:
        console.print("[cyan][*][/cyan] Memuat [bold]IG_SESSION_ID[/bold] dari file [bold].env[/bold]...")
        client = InstagramClient(
            session_id=config.IG_SESSION_ID,
            csrf_token=config.IG_CSRF_TOKEN,
            ds_user_id=config.IG_DS_USER_ID,
            proxy=config.PROXY
        )
        with console.status("[bold cyan]Memverifikasi sesi .env...[/bold cyan]", spinner="dots"):
            valid, msg = await client.test_session()

        if valid:
            console.print(f"[bold green][✓][/bold green] [green]{msg}[/green]\n")
            # Simpan cache ke cookies.json
            cookies_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cookies_path, "w", encoding="utf-8") as f:
                json.dump({
                    "sessionid": config.IG_SESSION_ID,
                    "csrftoken": config.IG_CSRF_TOKEN,
                    "ds_user_id": config.IG_DS_USER_ID
                }, f, indent=2)
            return client
        else:
            console.print(f"[bold red][!][/bold red] [yellow]Cookies di .env ditolak Instagram: {msg}[/yellow]")

    # 3. Input interaktif
    return await prompt_and_save_cookies(cookies_path)

async def prompt_and_save_cookies(cookies_path: Optional[Path] = None) -> InstagramClient:
    """
    Panduan terminal interaktif untuk menginput cookie sesi dari peramban.
    """
    if cookies_path is None:
        cookies_path = Path(config.COOKIES_FILE)

    print("\n" + "=" * 72)
    print("AUTENTIKASI INSTAGRAM (SESI COOKIES BROWSER)")
    print("=" * 72)
    print("Program membutuhkan 'sessionid' dari browser Anda untuk membaca data.")
    print("\nCara mengambil dari browser (Hanya butuh 15 detik):")
    print("1. Buka https://www.instagram.com di browser (Chrome / Edge / Firefox).")
    print("2. Pastikan sudah login ke akun Instagram Anda.")
    print("3. Tekan F12 (Developer Tools) -> Masuk ke tab 'Application' (atau 'Storage').")
    print("4. Di panel kiri, klik 'Cookies' -> 'https://www.instagram.com'.")
    print("5. Salin nilai (Value) dari 'sessionid' dan 'csrftoken'.")
    print("=" * 72 + "\n")

    session_id = input("Masukkan nilai 'sessionid': ").strip()
    csrf_token = input("Masukkan nilai 'csrftoken' (opsional, tekan Enter jika dilewati): ").strip()
    ds_user_id = input("Masukkan nilai 'ds_user_id' (opsional, tekan Enter jika dilewati): ").strip()

    if not session_id:
        raise ValueError("Nilai 'sessionid' tidak boleh kosong!")

    print("\n[+] Menguji validitas cookies ke Instagram...")
    client = InstagramClient(
        session_id=session_id,
        csrf_token=csrf_token,
        ds_user_id=ds_user_id,
        proxy=config.PROXY
    )

    valid, msg = await client.test_session()
    if valid:
        cookies_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump({
                "sessionid": session_id,
                "csrftoken": csrf_token,
                "ds_user_id": ds_user_id
            }, f, indent=2)
        print(f"[OK] {msg}")
        print(f"[OK] Sesi tersimpan di: {cookies_path}\n")
        return client
    else:
        raise ValueError(f"Cookies ditolak Instagram: {msg}. Pastikan Anda login di browser dan akun tidak terkunci.")
