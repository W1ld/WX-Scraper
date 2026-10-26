import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
import config

def sanitize_filename(name: str) -> str:
    """Membersihkan karakter ilegal untuk penamaan file yang aman di Windows/Linux."""
    return re.sub(r'[\\/*?:"<>| ]', "_", name).strip("_")

def export_data(
    data: List[Dict[str, Any]],
    prefix: str = "instagram_data",
    export_format: str = "csv",
    output_dir: Path | None = None
) -> Dict[str, str]:
    """
    Mengekspor list data dictionary Instagram ke CSV, JSON, atau keduanya.
    
    Args:
        data: List dictionary hasil parsing.
        prefix: Awalan nama file output (misal username atau shortcode).
        export_format: 'csv', 'json', atau 'both'.
        output_dir: Direktori tujuan (default: config.DATA_DIR).
        
    Returns:
        Dict berisi path file yang berhasil disimpan.
    """
    if not data:
        print("[!] Tidak ada data untuk diekspor.")
        return {}

    target_dir = output_dir or config.DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_prefix = sanitize_filename(prefix)[:40]
    base_name = f"{clean_prefix}_{timestamp}"
    
    saved_files = {}

    # Ekspor ke CSV
    if export_format.lower() in ("csv", "both", "all"):
        csv_path = target_dir / f"{base_name}.csv"
        df = pd.DataFrame(data)
        # utf-8-sig memastikan karakter Indonesia & emoji terbaca sempurna di Microsoft Excel Windows
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        saved_files["csv"] = str(csv_path)
        print(f"[✓] Data berhasil disimpan ke CSV: {csv_path} ({len(data)} baris)")

    # Ekspor ke JSON
    if export_format.lower() in ("json", "both", "all"):
        json_path = target_dir / f"{base_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        saved_files["json"] = str(json_path)
        print(f"[✓] Data berhasil disimpan ke JSON: {json_path}")

    return saved_files

def save_checkpoint(
    data: List[Dict[str, Any]],
    prefix: str = "checkpoint",
    output_dir: Path | None = None
) -> str:
    """
    Menyimpan cadangan sementara (checkpoint) ke format CSV agar data tidak hilang saat sesi panjang.
    """
    if not data:
        return ""
    target_dir = output_dir or config.DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    clean_prefix = sanitize_filename(prefix)[:30]
    checkpoint_file = target_dir / f"checkpoint_{clean_prefix}.csv"
    try:
        df = pd.DataFrame(data)
        df.to_csv(checkpoint_file, index=False, encoding="utf-8-sig")
        return str(checkpoint_file)
    except Exception:
        return ""
