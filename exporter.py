import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
import config

def sanitize_filename(name: str) -> str:
    """Sanitizes strings for safe file naming."""
    return re.sub(r'[\\/*?:"<>| ]', "_", name).strip("_")

def export_data(
    data: List[Dict[str, Any]],
    prefix: str = "tweets",
    export_format: str = "both",
    output_dir: Path | None = None
) -> Dict[str, str]:
    """
    Exports a list of parsed tweet dictionaries into CSV, JSON, or both.
    
    Args:
        data: List of tweet dictionaries.
        prefix: Prefix name for the output file (e.g. search keyword or username).
        export_format: 'csv', 'json', or 'both'.
        output_dir: Custom output directory (defaults to config.DATA_DIR).
        
    Returns:
        Dict with paths of saved files.
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

    # Export to CSV
    if export_format.lower() in ("csv", "both", "all"):
        csv_path = target_dir / f"{base_name}.csv"
        df = pd.DataFrame(data)
        # Using utf-8-sig ensures Excel on Windows displays Indonesian characters & emojis properly
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        saved_files["csv"] = str(csv_path)
        print(f"[✓] Data berhasil disimpan ke CSV: {csv_path} ({len(data)} baris)")

    # Export to JSON
    if export_format.lower() in ("json", "both", "all"):
        json_path = target_dir / f"{base_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        saved_files["json"] = str(json_path)
    return saved_files

def save_checkpoint(
    data: List[Dict[str, Any]],
    prefix: str = "checkpoint",
    output_dir: Path | None = None
) -> str:
    """
    Saves an intermediate checkpoint to CSV so data is not lost during long scraping sessions.
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

