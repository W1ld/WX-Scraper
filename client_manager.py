import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
import httpx
import config

BEARER_TOKEN = "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

class TwitterClient:
    """
    Modern Twitter GraphQL Client authenticated via browser session cookies (auth_token & ct0).
    Bypasses broken client_transaction JS challenges.
    """
    def __init__(self, auth_token: str, ct0: str, proxy: Optional[str] = None):
        self.auth_token = auth_token
        self.ct0 = ct0
        self.proxy = proxy
        
        self.headers = {
            'authorization': BEARER_TOKEN,
            'x-csrf-token': self.ct0,
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'content-type': 'application/json',
            'referer': 'https://x.com/',
            'x-twitter-active-user': 'yes',
            'x-twitter-auth-type': 'OAuth2Session',
            'x-twitter-client-language': config.DEFAULT_LANG,
        }
        self.cookies = {
            'auth_token': self.auth_token,
            'ct0': self.ct0,
        }
        self._http: Optional[httpx.AsyncClient] = None

    def get_http_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                headers=self.headers,
                cookies=self.cookies,
                proxy=self.proxy,
                timeout=30.0,
                follow_redirects=True
            )
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def test_session(self) -> bool:
        """Tests if the cookies are valid."""
        url = 'https://x.com/i/api/graphql/5XShkXk2oO2J7SYmTu6pvw/Viewer'
        body = {
            'variables': {},
            'features': {
                "rweb_tipjar_consumption_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False
            },
            'queryId': '5XShkXk2oO2J7SYmTu6pvw'
        }
        http = self.get_http_client()
        try:
            r = await http.post(url, json=body)
            return r.status_code == 200
        except Exception:
            return False

async def get_twitter_client(force_login: bool = False) -> TwitterClient:
    """
    Initializes and authenticates the Twitter Client using browser session cookies.
    1. Loads existing cookies.json if valid.
    2. Otherwise uses AUTH_TOKEN & CT0 from .env or prompts interactively.
    """
    cookies_path = Path(config.COOKIES_FILE)

    # 1. Coba gunakan file cookies.json yang sudah tersimpan
    if not force_login and cookies_path.exists():
        try:
            with open(cookies_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            auth_token = saved.get("auth_token", "")
            ct0 = saved.get("ct0", "")
            if auth_token and ct0:
                print(f"[+] Memuat cookies dari: {cookies_path}")
                client = TwitterClient(auth_token=auth_token, ct0=ct0, proxy=config.PROXY)
                if await client.test_session():
                    print("[OK] Berhasil terhubung ke Twitter menggunakan session cookies.")
                    return client
                else:
                    print("[!] Cookies di cookies.json kedaluwarsa.")
        except Exception as e:
            print(f"[!] Gagal memuat cookies.json: {e}")

    # 2. Gunakan AUTH_TOKEN dan CT0 dari file .env jika ada
    if not force_login and config.AUTH_TOKEN and config.CT0:
        print("[+] Menggunakan AUTH_TOKEN & CT0 dari file .env...")
        client = TwitterClient(auth_token=config.AUTH_TOKEN, ct0=config.CT0, proxy=config.PROXY)
        if await client.test_session():
            print("[OK] Berhasil terhubung ke Twitter via .env!")
            # Simpan ke cookies.json agar ter-cache
            cookies_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cookies_path, "w", encoding="utf-8") as f:
                json.dump({"auth_token": config.AUTH_TOKEN, "ct0": config.CT0}, f, indent=2)
            return client
        else:
            print("[!] Cookies di .env tidak valid atau ditolak Twitter.")

    # 3. Jika belum diset di .env atau force_login=True, minta input cookies secara interaktif
    return await prompt_and_save_cookies(cookies_path)

async def prompt_and_save_cookies(cookies_path: Path | None = None) -> TwitterClient:
    """
    Panduan interaktif untuk memasukkan auth_token dan ct0 dari browser.
    """
    if cookies_path is None:
        cookies_path = Path(config.COOKIES_FILE)

    print("\n" + "="*70)
    print("AUTENTIKASI TWITTER / X (SESI COOKIES)")
    print("="*70)
    print("Masukkan 'auth_token' dan 'ct0' dari browser Anda:")
    print("\nCara mengambil dari browser (Hanya butuh 15 detik):")
    print("1. Buka https://x.com di browser (Chrome / Edge / Firefox) & pastikan sudah login.")
    print("2. Tekan tombol F12 (Developer Tools) -> Masuk ke tab 'Application' (atau 'Storage').")
    print("3. Di panel kiri, klik 'Cookies' -> 'https://x.com'.")
    print("4. Salin nilai (Value) dari cookie 'auth_token' dan 'ct0'.")
    print("="*70 + "\n")

    auth_token = input("Masukkan nilai 'auth_token': ").strip()
    ct0 = input("Masukkan nilai 'ct0': ").strip()

    if not auth_token or not ct0:
        raise ValueError("Nilai auth_token dan ct0 tidak boleh kosong!")

    print("\n[+] Menguji validitas cookies ke Twitter...")
    client = TwitterClient(auth_token=auth_token, ct0=ct0, proxy=config.PROXY)
    
    if await client.test_session():
        cookies_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump({"auth_token": auth_token, "ct0": ct0}, f, indent=2)
        print("[OK] Berhasil terhubung ke Twitter!")
        print(f"[OK] Sesi telah disimpan ke: {cookies_path}\n")
        return client
    else:
        raise ValueError("Cookies tidak valid atau ditolak oleh Twitter. Pastikan akun masih aktif login di browser.")
