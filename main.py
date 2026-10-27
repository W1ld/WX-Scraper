import argparse
import asyncio
import os
import sys
from typing import List, Optional

# Mengatur encoding konsol Windows untuk karakter UTF-8 dan emoji
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
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TaskProgressColumn,
    TimeElapsedColumn
)

from client_manager import get_instagram_client, prompt_and_save_cookies
from scraper import (
    get_user_profile,
    scrape_profile_posts,
    scrape_post_comments,
    scrape_multiple_posts_comments,
    scrape_hashtag_posts,
    extract_shortcode,
    scrape_profile_followers,
    scrape_profile_following
)
from exporter import export_data
import config

console = Console()

def create_scraper_progress() -> Progress:
    """Membuat progress bar Rich informatif dengan hitungan item real-time (contoh: 25/50)."""
    return Progress(
        SpinnerColumn("dots"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=25, complete_style="green", finished_style="bold green"),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TextColumn("[dim]{task.fields[detail]}[/dim]"),
        console=console,
        transient=False
    )

def display_banner():
    console.print(Panel.fit(
        "[bold magenta]WIG-Scraper (Instagram Data Extraction Suite)[/bold magenta]\n"
        "[dim]Tool Scraping Data Instagram: Profile Posts, Comments, 2-in-1 Drill-Down, & Hashtags[/dim]\n"
        "[bold yellow]Developer:[/bold yellow] [bold white]@W1ld[/bold white] | [bold yellow]Repository:[/bold yellow] [bold cyan]https://github.com/W1ld/WIG-Scraper[/bold cyan]",
        border_style="magenta"
    ))

def show_preview_table(data: List[dict], max_rows: int = 6):
    """Menampilkan tabel preview rapi data hasil scraping di terminal."""
    if not data:
        return
    
    first_type = data[0].get("row_type", "")
    if first_type in ("follower", "following"):
        table = Table(
            title=f"Preview Data Hasil Scraping ({'Followers' if first_type == 'follower' else 'Following'})",
            show_lines=True,
            header_style="bold magenta"
        )
        table.add_column("No", style="dim", width=4)
        table.add_column("Tipe", style="yellow", width=11)
        table.add_column("Username", style="cyan", width=18)
        table.add_column("Nama Lengkap", style="white", width=22)
        table.add_column("Privasi", justify="center", width=10)
        table.add_column("Verified", justify="center", width=11)
        table.add_column("Story Aktif", justify="center", width=12)

        for i, item in enumerate(data[:max_rows], 1):
            type_str = "[magenta]Follower[/magenta]" if item.get("row_type") == "follower" else "[yellow]Following[/yellow]"
            uname = item.get("username", "")
            fname = item.get("full_name", "") or "-"
            is_priv = "[red]Private[/red]" if item.get("is_private") else "[green]Public[/green]"
            is_ver = "[cyan]✓ Ya[/cyan]" if item.get("is_verified") else "[dim]Tidak[/dim]"
            has_story = "[green]🟢 Ada[/green]" if item.get("has_active_story") else "[dim]-[/dim]"

            table.add_row(
                str(i),
                type_str,
                f"@{uname}" if uname else "@unknown",
                fname[:20],
                is_priv,
                is_ver,
                has_story
            )

        try:
            console.print(table)
        except Exception:
            for i, item in enumerate(data[:max_rows], 1):
                print(f"[{i}] @{item.get('username')} ({item.get('full_name')})")

        if len(data) > max_rows:
            console.print(f"[dim]... dan {len(data) - max_rows} baris data lainnya tersimpan di file output.[/dim]\n")
        return

    table = Table(title="Preview Data Hasil Scraping", show_lines=True, header_style="bold magenta")
    table.add_column("No", style="dim", width=4)
    table.add_column("Tipe", style="yellow", width=10)
    table.add_column("Username", style="cyan", width=18)
    table.add_column("Konten / Teks (Preview)", style="white")
    table.add_column("Likes", justify="right", width=8)
    table.add_column("Komentar", justify="right", width=9)

    for i, item in enumerate(data[:max_rows], 1):
        row_type = item.get("row_type", "post")
        if row_type == "post":
            type_str = "[green]Post[/green]"
            username = item.get("owner_username", "")
            text_preview = (item.get("caption", "") or "").replace("\n", " ")
            comments_num = str(item.get("comments_count", 0))
        elif row_type == "comment":
            type_str = "[blue]Comment[/blue]"
            username = item.get("comment_author_username", "")
            text_preview = (item.get("comment_text", "") or "").replace("\n", " ")
            comments_num = str(item.get("comments_count", 0))
        else:
            type_str = "[cyan]Reply[/cyan]"
            username = item.get("comment_author_username", "")
            text_preview = (item.get("comment_text", "") or "").replace("\n", " ")
            comments_num = "-"
        
        if len(text_preview) > 55:
            text_preview = text_preview[:52] + "..."
            
        table.add_row(
            str(i),
            type_str,
            f"@{username}" if username else "@unknown",
            text_preview,
            str(item.get("likes_count", 0)),
            comments_num
        )

    try:
        console.print(table)
    except Exception:
        for i, item in enumerate(data[:max_rows], 1):
            print(f"[{i}] {item.get('row_type')}: {item.get('caption') or item.get('comment_text', '')[:50]}")

    if len(data) > max_rows:
        console.print(f"[dim]... dan {len(data) - max_rows} baris data lainnya tersimpan di file output.[/dim]\n")

def pause_prompt(msg: str = "\nTekan Enter untuk kembali ke menu utama..."):
    try:
        input(msg)
    except (EOFError, KeyboardInterrupt):
        pass

# ==============================================================================
# MENU HANDLERS
# ==============================================================================

async def handle_menu_profile_posts(client, drill_down: bool = False):
    """Menangani scraping postingan akun/profil pengguna."""
    console.print("\n[bold cyan]=== SCRAPE POSTINGAN PROFIL AKUN ===[/bold cyan]")
    username = Prompt.ask("Masukkan username target (contoh: [green]natgeo[/green] atau [green]@kemnaker[/green])").strip()
    if not username:
        return

    limit = IntPrompt.ask("Jumlah postingan yang ingin diambil", default=30)
    
    max_comments = 20
    if drill_down:
        max_comments = IntPrompt.ask("Maksimal komentar per postingan yang diambil (drill-down)", default=20)

    format_choice = Prompt.ask("Format ekspor data", choices=["both", "csv", "json"], default="csv")

    with create_scraper_progress() as progress:
        task_id = progress.add_task(f"Mengambil data @{username}", total=limit, detail="Menghubungi...")

        def on_progress(current: int, total: int, detail: str):
            progress.update(task_id, completed=current, total=total, detail=detail)

        data = await scrape_profile_posts(
            client=client,
            username=username,
            limit=limit,
            fetch_comments=drill_down,
            max_comments_per_post=max_comments,
            progress_callback=on_progress
        )
        progress.update(task_id, completed=len(data), total=len(data), detail="Selesai")

    if data:
        show_preview_table(data)
        prefix = f"profile_{username.lstrip('@')}" + ("_with_comments" if drill_down else "")
        export_data(data, prefix=prefix, export_format=format_choice)
    else:
        console.print("[yellow]Tidak ada postingan yang berhasil diambil.[/yellow]")

    pause_prompt()

async def handle_menu_post_comments(client):
    """Menangani scraping komentar dari satu postingan (URL / shortcode)."""
    console.print("\n[bold cyan]=== SCRAPE KOMENTAR DARI POSTINGAN ===[/bold cyan]")
    post_input = Prompt.ask(
        "Masukkan URL postingan atau Shortcode\n(contoh: [green]https://www.instagram.com/p/DBabc123/[/green] atau [green]DBabc123[/green])"
    ).strip()
    if not post_input:
        return

    shortcode = extract_shortcode(post_input)
    limit = IntPrompt.ask("Jumlah komentar maksimal yang ingin diambil", default=50)
    format_choice = Prompt.ask("Format ekspor data", choices=["both", "csv", "json"], default="csv")

    with create_scraper_progress() as progress:
        task_id = progress.add_task(f"Mengambil komentar post {shortcode}", total=limit, detail="Menghubungi...")

        def on_progress(current: int, total: int, detail: str):
            progress.update(task_id, completed=current, total=total, detail=detail)

        comments = await scrape_post_comments(
            client=client,
            post_input=shortcode,
            limit=limit,
            progress_callback=on_progress
        )
        progress.update(task_id, completed=len(comments), total=len(comments), detail="Selesai")

    if comments:
        show_preview_table(comments)
        export_data(comments, prefix=f"comments_{shortcode}", export_format=format_choice)
    else:
        console.print("[yellow]Tidak ada komentar yang ditemukan atau post bersifat privat/nonaktif.[/yellow]")

    pause_prompt()

async def handle_menu_batch_comments(client):
    """Menangani scraping komentar dari beberapa link postingan sekaligus."""
    console.print("\n[bold cyan]=== SCRAPE KOMENTAR BATCH (BEBERAPA POST SEKALIGUS) ===[/bold cyan]")
    console.print("[dim]Masukkan daftar URL atau Shortcode (pisahkan dengan koma atau masukkan path file .txt):[/dim]")
    user_input = Prompt.ask("Input URLs atau File path").strip()
    if not user_input:
        return

    urls = []
    if os.path.exists(user_input):
        with open(user_input, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    else:
        urls = [u.strip() for u in user_input.split(",") if u.strip()]

    if not urls:
        console.print("[red]Tidak ada URL atau shortcode yang valid ditemukan.[/red]")
        pause_prompt()
        return

    limit_per_post = IntPrompt.ask("Batas komentar per masing-masing post", default=30)
    format_choice = Prompt.ask("Format ekspor data", choices=["both", "csv", "json"], default="csv")

    with console.status(f"[bold green]Memproses {len(urls)} postingan...[/bold green]"):
        all_comments = await scrape_multiple_posts_comments(
            client=client,
            post_inputs=urls,
            limit_per_post=limit_per_post
        )

    if all_comments:
        show_preview_table(all_comments)
        export_data(all_comments, prefix=f"batch_comments_{len(urls)}_posts", export_format=format_choice)
    else:
        console.print("[yellow]Tidak ada komentar yang berhasil diambil.[/yellow]")

    pause_prompt()

async def handle_menu_hashtag_posts(client):
    """Menangani scraping postingan berdasarkan hashtag."""
    console.print("\n[bold cyan]=== SCRAPE POSTINGAN BERDASARKAN HASHTAG ===[/bold cyan]")
    hashtag = Prompt.ask("Masukkan hashtag (contoh: [green]teknologi[/green] atau [green]#kuliner[/green])").strip()
    if not hashtag:
        return

    limit = IntPrompt.ask("Jumlah postingan maksimal yang ingin diambil", default=30)
    format_choice = Prompt.ask("Format ekspor data", choices=["both", "csv", "json"], default="csv")

    clean_tag = hashtag.lstrip("#")
    with create_scraper_progress() as progress:
        task_id = progress.add_task(f"Mencari postingan #{clean_tag}", total=limit, detail="Menghubungi...")

        def on_progress(current: int, total: int, detail: str):
            progress.update(task_id, completed=current, total=total, detail=detail)

        data = await scrape_hashtag_posts(
            client=client,
            hashtag=clean_tag,
            limit=limit,
            progress_callback=on_progress
        )
        progress.update(task_id, completed=len(data), total=len(data), detail="Selesai")

    if data:
        show_preview_table(data)
        export_data(data, prefix=f"hashtag_{clean_tag}", export_format=format_choice)
    else:
        console.print(f"[yellow]Tidak ada postingan yang ditemukan untuk hashtag #{clean_tag}.[/yellow]")

    pause_prompt()

async def handle_menu_followers(client):
    """Menangani scraping daftar pengikut (followers) akun Instagram publik."""
    console.print("\n[bold cyan]=== SCRAPE DAFTAR PENGIKUT (FOLLOWERS) AKUN PUBLIK ===[/bold cyan]")
    target = Prompt.ask("Masukkan username atau URL profil target (contoh: [green]cnnindonesia[/green] atau [green]@kemnaker[/green])").strip()
    if not target:
        return

    limit = IntPrompt.ask("Jumlah followers maksimal yang ingin diambil", default=50)
    format_choice = Prompt.ask("Format ekspor data", choices=["both", "csv", "json"], default="csv")

    with create_scraper_progress() as progress:
        task_id = progress.add_task(f"Mengambil followers {target}", total=limit, detail="Menghubungi...")

        def on_progress(current: int, total: int, detail: str):
            progress.update(task_id, completed=current, total=total, detail=detail)

        followers = await scrape_profile_followers(
            client=client,
            target=target,
            limit=limit,
            progress_callback=on_progress
        )
        progress.update(task_id, completed=len(followers), total=len(followers), detail="Selesai")

    if followers:
        show_preview_table(followers)
        clean_target = target.lstrip("@").replace("https://www.instagram.com/", "").strip("/ ")
        export_data(followers, prefix=f"followers_{clean_target}", export_format=format_choice)
    else:
        console.print(f"[yellow]Tidak ada follower yang berhasil diambil untuk {target}.[/yellow]")

    pause_prompt()

async def handle_menu_following(client):
    """Menangani scraping daftar akun yang diikuti (following) akun Instagram publik."""
    console.print("\n[bold cyan]=== SCRAPE DAFTAR FOLLOWING (AKUN YANG DIIKUTI) ===[/bold cyan]")
    target = Prompt.ask("Masukkan username atau URL profil target (contoh: [green]cnnindonesia[/green] atau [green]@kemnaker[/green])").strip()
    if not target:
        return

    limit = IntPrompt.ask("Jumlah following maksimal yang ingin diambil", default=50)
    format_choice = Prompt.ask("Format ekspor data", choices=["both", "csv", "json"], default="csv")

    with create_scraper_progress() as progress:
        task_id = progress.add_task(f"Mengambil following {target}", total=limit, detail="Menghubungi...")

        def on_progress(current: int, total: int, detail: str):
            progress.update(task_id, completed=current, total=total, detail=detail)

        following = await scrape_profile_following(
            client=client,
            target=target,
            limit=limit,
            progress_callback=on_progress
        )
        progress.update(task_id, completed=len(following), total=len(following), detail="Selesai")

    if following:
        show_preview_table(following)
        clean_target = target.lstrip("@").replace("https://www.instagram.com/", "").strip("/ ")
        export_data(following, prefix=f"following_{clean_target}", export_format=format_choice)
    else:
        console.print(f"[yellow]Tidak ada following yang berhasil diambil untuk {target}.[/yellow]")

    pause_prompt()

# ==============================================================================
# CLI ARGUMENT RUNNER (HEADLESS / SCRIPT AUTOMATION)
# ==============================================================================

async def run_cli_arguments(args, client):
    """Menjalankan mode CLI argumen untuk otomatisasi tanpa antarmuka interaktif."""
    if args.profile:
        with create_scraper_progress() as progress:
            task_id = progress.add_task(f"Scrape profil @{args.profile}", total=args.limit, detail="Menghubungi...")

            def on_progress(current: int, total: int, detail: str):
                progress.update(task_id, completed=current, total=total, detail=detail)

            data = await scrape_profile_posts(
                client=client,
                username=args.profile,
                limit=args.limit,
                fetch_comments=args.drill_down,
                max_comments_per_post=args.max_comments,
                progress_callback=on_progress
            )
            progress.update(task_id, completed=len(data), total=len(data), detail="Selesai")

        if data:
            prefix = f"profile_{args.profile.lstrip('@')}" + ("_with_comments" if args.drill_down else "")
            export_data(data, prefix=prefix, export_format=args.format)

    elif args.comments:
        shortcode = extract_shortcode(args.comments)
        with create_scraper_progress() as progress:
            task_id = progress.add_task(f"Scrape komentar post {shortcode}", total=args.limit, detail="Menghubungi...")

            def on_progress(current: int, total: int, detail: str):
                progress.update(task_id, completed=current, total=total, detail=detail)

            comments = await scrape_post_comments(
                client=client,
                post_input=shortcode,
                limit=args.limit,
                progress_callback=on_progress
            )
            progress.update(task_id, completed=len(comments), total=len(comments), detail="Selesai")

        if comments:
            export_data(comments, prefix=f"comments_{shortcode}", export_format=args.format)

    elif args.batch_urls:
        urls = []
        if os.path.exists(args.batch_urls):
            with open(args.batch_urls, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        else:
            urls = [u.strip() for u in args.batch_urls.split(",") if u.strip()]
        
        with console.status(f"[bold cyan]Memproses {len(urls)} postingan untuk penarikan komentar...[/bold cyan]", spinner="dots"):
            all_comments = await scrape_multiple_posts_comments(
                client=client,
                post_inputs=urls,
                limit_per_post=args.limit
            )
        if all_comments:
            export_data(all_comments, prefix=f"batch_comments_{len(urls)}_posts", export_format=args.format)

    elif args.hashtag:
        clean_tag = args.hashtag.lstrip("#")
        with create_scraper_progress() as progress:
            task_id = progress.add_task(f"Scrape hashtag #{clean_tag}", total=args.limit, detail="Menghubungi...")

            def on_progress(current: int, total: int, detail: str):
                progress.update(task_id, completed=current, total=total, detail=detail)

            data = await scrape_hashtag_posts(
                client=client,
                hashtag=clean_tag,
                limit=args.limit,
                progress_callback=on_progress
            )
            progress.update(task_id, completed=len(data), total=len(data), detail="Selesai")

        if data:
            export_data(data, prefix=f"hashtag_{clean_tag}", export_format=args.format)

    elif args.followers:
        clean_target = args.followers.lstrip("@").replace("https://www.instagram.com/", "").strip("/ ")
        with create_scraper_progress() as progress:
            task_id = progress.add_task(f"Scrape followers @{clean_target}", total=args.limit, detail="Menghubungi...")

            def on_progress(current: int, total: int, detail: str):
                progress.update(task_id, completed=current, total=total, detail=detail)

            followers = await scrape_profile_followers(
                client=client,
                target=args.followers,
                limit=args.limit,
                progress_callback=on_progress
            )
            progress.update(task_id, completed=len(followers), total=len(followers), detail="Selesai")

        if followers:
            export_data(followers, prefix=f"followers_{clean_target}", export_format=args.format)

    elif args.following:
        clean_target = args.following.lstrip("@").replace("https://www.instagram.com/", "").strip("/ ")
        with create_scraper_progress() as progress:
            task_id = progress.add_task(f"Scrape following @{clean_target}", total=args.limit, detail="Menghubungi...")

            def on_progress(current: int, total: int, detail: str):
                progress.update(task_id, completed=current, total=total, detail=detail)

            following = await scrape_profile_following(
                client=client,
                target=args.following,
                limit=args.limit,
                progress_callback=on_progress
            )
            progress.update(task_id, completed=len(following), total=len(following), detail="Selesai")

        if following:
            export_data(following, prefix=f"following_{clean_target}", export_format=args.format)

# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

async def async_main():
    parser = argparse.ArgumentParser(
        description="WIG-Scraper: Tool Scraping Data Instagram Modern (Profile, Comments, Hashtags, Followers)"
    )
    parser.add_argument("--profile", type=str, help="Username Instagram yang ingin di-scrape postingannya")
    parser.add_argument("--comments", type=str, help="URL atau shortcode postingan untuk di-scrape seluruh komentarnya")
    parser.add_argument("--batch-urls", type=str, help="Daftar URL postingan (file .txt atau dipisah koma) untuk batch komentar")
    parser.add_argument("--hashtag", type=str, help="Hashtag Instagram yang ingin dicari postingannya")
    parser.add_argument("--followers", type=str, help="Username atau URL profil untuk di-scrape daftar pengikutnya (followers)")
    parser.add_argument("--following", type=str, help="Username atau URL profil untuk di-scrape daftar following-nya")
    parser.add_argument("--drill-down", action="store_true", help="Gali komentar otomatis pada setiap postingan profil (fitur 2-in-1)")
    parser.add_argument("--limit", type=int, default=30, help="Jumlah maksimal data yang diambil (default: 30)")
    parser.add_argument("--max-comments", type=int, default=20, help="Batas maksimal komentar per post saat mode drill-down (default: 20)")
    parser.add_argument("--format", type=str, choices=["csv", "json", "both"], default="csv", help="Format ekspor file (default: csv)")
    parser.add_argument("--force-login", action="store_true", help="Paksa input ulang cookies sesi Instagram")

    args = parser.parse_args()

    display_banner()

    # Inisialisasi klien
    try:
        client = await get_instagram_client(force_login=args.force_login)
    except Exception as e:
        console.print(f"[bold red][!] Gagal inisialisasi sesi Instagram:[/bold red] {e}")
        return

    # Jika pengguna menggunakan argumen baris perintah
    has_cli_mode = any([args.profile, args.comments, args.batch_urls, args.hashtag, args.followers, args.following])
    if has_cli_mode:
        await run_cli_arguments(args, client)
        await client.close()
        return

    # Mode Interaktif Terminal Menu
    first_time = True
    while True:
        if not first_time:
            console.clear()
            display_banner()
        first_time = False

        menu_table = Table(title="Pilihan Menu Utama", show_header=False, border_style="cyan")
        menu_table.add_column("No", style="bold yellow", width=4)
        menu_table.add_column("Deskripsi Fitur")

        menu_table.add_row("1", "Scrape Postingan dari Profil / Akun (@username)")
        menu_table.add_row("2", "Scrape Postingan Profil + Komentar (2-in-1 Drill-Down)")
        menu_table.add_row("3", "Scrape Seluruh Komentar dari Link / URL Postingan")
        menu_table.add_row("4", "Scrape Komentar dari Beberapa URL Sekaligus (Batch)")
        menu_table.add_row("5", "Scrape Postingan Berdasarkan Hashtag (#hashtag)")
        menu_table.add_row("6", "Scrape Daftar Pengikut Akun Publik (Followers)")
        menu_table.add_row("7", "Scrape Daftar Akun yang Diikuti (Following)")
        menu_table.add_row("8", "Uji / Perbarui Cookies Sesi Instagram")
        menu_table.add_row("0", "Keluar dari Aplikasi")

        console.print(menu_table)
        pilihan = Prompt.ask("\nPilih nomor menu", choices=["1", "2", "3", "4", "5", "6", "7", "8", "0"], default="1")

        if pilihan == "1":
            await handle_menu_profile_posts(client, drill_down=False)
        elif pilihan == "2":
            await handle_menu_profile_posts(client, drill_down=True)
        elif pilihan == "3":
            await handle_menu_post_comments(client)
        elif pilihan == "4":
            await handle_menu_batch_comments(client)
        elif pilihan == "5":
            await handle_menu_hashtag_posts(client)
        elif pilihan == "6":
            await handle_menu_followers(client)
        elif pilihan == "7":
            await handle_menu_following(client)
        elif pilihan == "8":
            await client.close()
            client = await prompt_and_save_cookies()
            pause_prompt()
        elif pilihan == "0":
            console.print("[bold green]\nTerima kasih telah menggunakan WIG-Scraper![/bold green]")
            await client.close()
            break

def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n[!] Program dihentikan oleh pengguna.")

if __name__ == "__main__":
    main()
