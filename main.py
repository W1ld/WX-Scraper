import argparse
import asyncio
import sys
from typing import List

# Fix Windows console encoding for UTF-8 characters and emojis
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt

from client_manager import get_twitter_client, prompt_and_save_cookies
from scraper import search_tweets, search_tweets_with_replies, get_tweet_detail_and_replies
from exporter import export_data
import config

console = Console()

def display_banner():
    console.print(Panel.fit(
        "[bold cyan]WX-Scrapper (Twitter / X Data Extraction Suite)[/bold cyan]\n"
        "[dim]Tool Scraping Data Twitter: Search Query, Search + Replies per Tweet, & Tweet Details[/dim]\n"
        "[bold yellow]Developer:[/bold yellow] [bold white]@W1ld[/bold white] | [bold yellow]GitHub:[/bold yellow] [bold green]https://github.com/W1ld/WX-Scrapper[/bold green]",
        border_style="cyan"
    ))

def show_preview_table(data: List[dict], max_rows: int = 5):
    """Menampilkan tabel preview data hasil scraping di terminal."""
    if not data:
        return
    
    table = Table(title="Preview Data Hasil Scraping", show_lines=True, header_style="bold magenta")
    table.add_column("No", style="dim", width=4)
    table.add_column("Tipe", style="yellow", width=10)
    table.add_column("Username", style="cyan", width=18)
    table.add_column("Text (Preview)", style="white")
    table.add_column("Likes", justify="right", width=7)
    table.add_column("Replies", justify="right", width=8)

    for i, item in enumerate(data[:max_rows], 1):
        row_type = item.get("row_type", "main_tweet")
        type_str = "[green]Tweet[/green]" if row_type == "main_tweet" else "[blue]Reply[/blue]"
        
        text_preview = (item.get("text", "") or "").replace("\n", " ")
        if len(text_preview) > 55:
            text_preview = text_preview[:52] + "..."
            
        username_str = item.get('username', '')
        table.add_row(
            str(i),
            type_str,
            f"@{username_str}" if username_str else "@unknown",
            text_preview,
            str(item.get("likes", 0)),
            str(item.get("replies", 0))
        )

    try:
        console.print(table)
    except Exception:
        # Fallback print if console fails
        for i, item in enumerate(data[:max_rows], 1):
            print(f"[{i}] @{item.get('username')}: {item.get('text', '')[:60]}... (Likes: {item.get('likes')})")

    if len(data) > max_rows:
        console.print(f"[dim]... dan {len(data) - max_rows} baris data lainnya tersimpan di file output.[/dim]\n")

def pause_prompt(msg: str = "\nTekan Enter untuk melanjutkan..."):
    try:
        input(msg)
    except (EOFError, KeyboardInterrupt):
        pass

async def interactive_menu():
    """Menu CLI interaktif yang mudah digunakan."""
    client = None
    
    while True:
        display_banner()
        console.print("[bold yellow]Pilih Fitur Scraping:[/bold yellow]")
        console.print("  [bold green]1.[/bold green] Cari Tweet berdasarkan Kata Kunci / Hashtag (Hanya Tweet Utama)")
        console.print("  [bold green]2.[/bold green] Ambil Detail Tweet Tunggal & Balasan / Komentar (dari URL / Tweet ID)")
        console.print("  [bold green]3.[/bold green] Cari Tweet + Ambil Komentar/Replies untuk Setiap Tweet (Kombinasi Fitur 1 & 2)")
        console.print("  [bold green]4.[/bold green] Perbarui Sesi Login (Masukkan auth_token & ct0 baru)")
        console.print("  [bold red]5.[/bold red] Keluar (Exit)")

        choice = Prompt.ask("\n[?] Masukkan pilihan Anda", choices=["1", "2", "3", "4", "5"], default="1")

        if choice == "5":
            console.print("[bold green]Terima kasih telah menggunakan WX Scrapper![/bold green]")
            break

        # Pastikan client terautentikasi
        if client is None or choice == "4":
            try:
                client = await get_twitter_client(force_login=(choice == "4"))
            except Exception as e:
                console.print(f"[bold red][X] Gagal mengautentikasi: {e}[/bold red]")
                pause_prompt("\nTekan Enter untuk kembali ke menu...")
                continue
            if choice == "4":
                pause_prompt("\nTekan Enter untuk kembali ke menu...")
                continue

        # Option 1: Search Query Only
        if choice == "1":
            console.print("\n[bold cyan]--- [1] PENCARIAN TWEET (HANYA TWEET UTAMA) ---[/bold cyan]")
            query = Prompt.ask("[?] Masukkan kata kunci / hashtag (contoh: 'Monas' atau '#TimnasDay')")
            if not query.strip():
                console.print("[red]Kata kunci tidak boleh kosong.[/red]")
                continue

            sort_mode = Prompt.ask("[?] Urutan data", choices=["top", "latest", "media"], default="top")
            count = IntPrompt.ask("[?] Jumlah tweet yang ingin diambil", default=50)
            fmt = Prompt.ask("[?] Format ekspor", choices=["both", "csv", "json"], default="csv")

            with console.status("[bold green]Sedang melakukan scraping tweet...[/bold green]", spinner="dots"):
                tweets = await search_tweets(client, query=query, product=sort_mode.capitalize(), max_tweets=count)

            if tweets:
                show_preview_table(tweets)
                export_data(tweets, prefix=f"search_{query}", export_format=fmt)
            else:
                console.print("[yellow]Tidak ada tweet yang berhasil diambil.[/yellow]")

        # Option 2: Single Tweet Detail & Replies
        elif choice == "2":
            console.print("\n[bold cyan]--- [2] DETAIL TWEET TUNGGAL & REPLIES ---[/bold cyan]")
            tweet_input = Prompt.ask("[?] Masukkan URL Tweet atau Tweet ID")
            if not tweet_input.strip():
                console.print("[red]Input tidak boleh kosong.[/red]")
                continue

            max_replies = IntPrompt.ask("[?] Jumlah balasan / replies maksimal yang diambil", default=50)
            fmt = Prompt.ask("[?] Format ekspor", choices=["both", "csv", "json"], default="csv")

            with console.status("[bold green]Sedang mengambil detail tweet & replies...[/bold green]", spinner="dots"):
                result = await get_tweet_detail_and_replies(client, tweet_id_or_url=tweet_input, max_replies=max_replies)

            main_tweet = result.get("main_tweet")
            replies = result.get("replies", [])

            if main_tweet:
                all_data = [main_tweet] + replies
                show_preview_table(all_data)
                export_data(all_data, prefix=f"tweet_{main_tweet['tweet_id']}", export_format=fmt)
            else:
                console.print("[yellow]Tweet tidak ditemukan atau gagal diambil.[/yellow]")

        # Option 3: Search Query + Replies per Tweet
        elif choice == "3":
            console.print("\n[bold cyan]--- [3] CARI TWEET + AMBIL KOMENTAR SETIAP TWEET ---[/bold cyan]")
            query = Prompt.ask("[?] Masukkan kata kunci / hashtag (contoh: 'Monas' atau '#TimnasDay')")
            if not query.strip():
                console.print("[red]Kata kunci tidak boleh kosong.[/red]")
                continue

            sort_mode = Prompt.ask("[?] Urutan tweet", choices=["top", "latest", "media"], default="top")
            count = IntPrompt.ask("[?] Jumlah tweet utama yang ingin dicari", default=100)
            replies_per_tweet = IntPrompt.ask("[?] Jumlah komentar per tweet yang ingin diambil (maksimal)", default=5)
            fmt = Prompt.ask("[?] Format ekspor", choices=["both", "csv", "json"], default="csv")

            console.print(f"\n[dim]Memulai scraping {count} tweet '{query}' ({sort_mode}) dan maks {replies_per_tweet} komentar per tweet...[/dim]")
            tweets_data = await search_tweets_with_replies(
                client=client,
                query=query,
                product=sort_mode.capitalize(),
                max_tweets=count,
                replies_per_tweet=replies_per_tweet
            )

            if tweets_data:
                show_preview_table(tweets_data)
                export_data(tweets_data, prefix=f"search_with_replies_{query}", export_format=fmt)
            else:
                console.print("[yellow]Tidak ada data yang berhasil diambil.[/yellow]")

        pause_prompt("\nTekan Enter untuk melanjutkan...")

async def run_cli_args(args):
    """Eksekusi scraping langsung menggunakan command line arguments."""
    client = await get_twitter_client(force_login=args.force_login)

    if args.mode == "search":
        if not args.query:
            console.print("[bold red]Error: Argumen --query (-q) wajib diisi untuk mode search.[/bold red]")
            sys.exit(1)
        sort_choice = args.sort.capitalize() if args.sort else "Top"
        tweets = await search_tweets(client, query=args.query, product=sort_choice, max_tweets=args.count)
        if tweets:
            show_preview_table(tweets)
            export_data(tweets, prefix=f"search_{args.query}", export_format=args.format)

    elif args.mode in ("search-replies", "combo"):
        if not args.query:
            console.print("[bold red]Error: Argumen --query (-q) wajib diisi untuk mode search-replies.[/bold red]")
            sys.exit(1)
        sort_choice = args.sort.capitalize() if args.sort else "Top"
        tweets = await search_tweets_with_replies(
            client=client,
            query=args.query,
            product=sort_choice,
            max_tweets=args.count,
            replies_per_tweet=args.replies_per_tweet
        )
        if tweets:
            show_preview_table(tweets)
            export_data(tweets, prefix=f"search_with_replies_{args.query}", export_format=args.format)

    elif args.mode == "tweet":
        if not args.id:
            console.print("[bold red]Error: Argumen --id (-i) wajib diisi untuk mode tweet.[/bold red]")
            sys.exit(1)
        result = await get_tweet_detail_and_replies(client, tweet_id_or_url=args.id, max_replies=args.replies)
        main_tweet = result.get("main_tweet")
        replies = result.get("replies", [])
        if main_tweet:
            all_data = [main_tweet] + replies
            show_preview_table(all_data)
            export_data(all_data, prefix=f"tweet_{main_tweet['tweet_id']}", export_format=args.format)

    elif args.mode == "login":
        await prompt_and_save_cookies(client)

def parse_arguments():
    parser = argparse.ArgumentParser(description="WX-Scrapper: Twitter / X Data Extraction CLI Tool")
    parser.add_argument("--mode", "-m", choices=["search", "search-replies", "combo", "tweet", "login", "menu"], default=None,
                        help="Mode operasi: search, search-replies (combo), tweet, login, atau menu interaktif")
    parser.add_argument("--query", "-q", type=str, help="Kata kunci atau hashtag untuk pencarian tweet")
    parser.add_argument("--sort", choices=["top", "latest", "media", "Top", "Latest", "Media"], default="top", help="Urutan pencarian tweet (default: top)")
    parser.add_argument("--count", "-c", type=int, default=50, help="Jumlah tweet utama yang diambil (default: 50)")
    parser.add_argument("--replies-per-tweet", "-rpt", type=int, default=5, help="Jumlah komentar per tweet untuk mode search-replies (default: 5)")
    parser.add_argument("--id", "-i", type=str, help="Tweet ID atau URL status tweet untuk mode tweet tunggal")
    parser.add_argument("--replies", "-r", type=int, default=50, help="Jumlah replies maksimal untuk mode tweet tunggal (default: 50)")
    parser.add_argument("--format", "-f", choices=["both", "csv", "json"], default="csv", help="Format output (default: csv)")
    parser.add_argument("--force-login", action="store_true", help="Paksa perbarui sesi login (auth_token & ct0)")
    return parser.parse_args()

async def main():
    args = parse_arguments()
    if args.mode is None or args.mode == "menu":
        await interactive_menu()
    else:
        await run_cli_args(args)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Proses dibatalkan oleh pengguna (KeyboardInterrupt).[/yellow]")
        sys.exit(0)
