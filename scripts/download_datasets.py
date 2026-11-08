#!/usr/bin/env python3
"""Download every original dataset listed in scripts/sources.py.

* Files land unmodified in data/raw/<category>/<filename>.
* For each attempt we record HTTP status, size, SHA-256, content type and UTC
  timestamp in data/metadata/source_registry.json.
* Failures are NEVER hidden: a failed download is recorded with status "failed"
  and the reason, and the script exits non-zero if a *required* file fails.
* Existing files are kept unless --force is given (originals are never silently
  modified).

Usage:  python scripts/download_datasets.py [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sources import NOT_ACQUIRED, SOURCES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
META = ROOT / "data" / "metadata"
UA = "ConferenceCarbonCalculator-dataset-fetcher/1.0 (+research use)"
OPTIONAL = {"SFC_INDIA_DEFAULTS", "OURAIRPORTS", "EPA_WARM_V16"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def looks_valid(path: Path, fmt: str) -> bool:
    head = path.read_bytes()[:8]
    if fmt == "pdf":
        return head.startswith(b"%PDF")
    if fmt in ("xlsx", "zip"):
        return head.startswith(b"PK")
    if fmt == "xls":
        return head.startswith(b"\xd0\xcf\x11\xe0") or head.startswith(b"PK")
    if fmt in ("csv", "json"):
        return not head.lstrip().lower().startswith(b"<!doc") and not head.lstrip().startswith(b"<html")
    return True


def fetch(src: dict, force: bool) -> dict:
    dest = RAW / src["category"] / src["filename"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    rec = {k: src.get(k) for k in (
        "source_id", "category", "name", "publisher", "url", "landing_page", "filename",
        "format", "version", "reporting_year", "geography", "licence", "notes")}
    rec["local_path"] = str(dest.relative_to(ROOT))
    if dest.exists() and not force and looks_valid(dest, src["format"]):
        rec.update(status="downloaded", note="already present; not re-downloaded",
                   size_bytes=dest.stat().st_size, sha256=sha256(dest),
                   downloaded_at=datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).isoformat())
        return rec
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        req = urllib.request.Request(src["url"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as f:
            ctype = r.headers.get("Content-Type", "")
            while chunk := r.read(1 << 20):
                f.write(chunk)
        if not looks_valid(tmp, src["format"]):
            tmp.unlink(missing_ok=True)
            raise ValueError(f"server returned content that is not a valid {src['format']} file ({ctype})")
        tmp.replace(dest)
        rec.update(status="downloaded", content_type=ctype, size_bytes=dest.stat().st_size,
                   sha256=sha256(dest), downloaded_at=datetime.now(timezone.utc).isoformat())
    except (urllib.error.URLError, ValueError, TimeoutError, OSError) as e:
        tmp.unlink(missing_ok=True)
        rec.update(status="failed", error=str(e), attempted_at=datetime.now(timezone.utc).isoformat())
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    args = ap.parse_args()
    META.mkdir(parents=True, exist_ok=True)
    results = []
    for src in SOURCES:
        rec = fetch(src, args.force)
        flag = "OK " if rec["status"] == "downloaded" else "FAIL"
        print(f"[{flag}] {src['source_id']:<28} {rec.get('size_bytes', '')!s:>10}  {rec.get('error', '')}")
        results.append(rec)
    registry = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": results,
        "not_acquired": NOT_ACQUIRED,
    }
    (META / "source_registry.json").write_text(json.dumps(registry, indent=2))
    hard_fail = [r for r in results if r["status"] != "downloaded" and r["source_id"] not in OPTIONAL]
    if hard_fail:
        print(f"\n{len(hard_fail)} REQUIRED dataset(s) failed - see data/metadata/source_registry.json")
        return 1
    print("\nAll required datasets present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
