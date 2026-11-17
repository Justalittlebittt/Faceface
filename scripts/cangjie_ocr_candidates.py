#!/usr/bin/env python3
"""M16.2: batch OCR candidate transcriptions of the 1925 vertical Chinese scans.

The output is NEVER reviewed text and must not enter Cangjie verified sources
without page-specific manual review. Expected tools: pdfinfo, pdftoppm,
tesseract with chi_tra_vert. Uses existing SCANS as source IDs/page counts.

Examples:
  python scripts/cangjie_ocr_candidates.py --scan-dir scans --out-dir corpus-work --source nlc-44091
  python scripts/cangjie_ocr_candidates.py --scan-dir scans --out-dir corpus-work --source nlc-44092 --start 0 --end 38
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from cangjie_corpus_stage import SCANS, pdf_pages

HAN_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
VERSION = "m16.2-ocr-v1"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True, errors="replace")
    if result.returncode:
        raise RuntimeError(
            f"Command failed (exit={result.returncode}): {args[0]}; "
            f"{result.stderr.strip()[-500:]}"
        )


def tsv_confidence(path: Path) -> tuple[int, float | None]:
    # Level 5 is Tesseract's individual OCR word; ignore invalid confidences.
    samples: list[float] = []
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        for item in csv.DictReader(f, delimiter="\t"):
            if item.get("level") != "5" or not item.get("text", "").strip():
                continue
            try:
                confidence = float(item["conf"])
            except (KeyError, ValueError, TypeError):
                continue
            if 0 <= confidence <= 100:
                samples.append(confidence)
    return len(samples), round(sum(samples) / len(samples), 1) if samples else None


def ocr_page(pdf: Path, source_id: str, page: int, out_dir: Path,
             pdf_hash: str, dpi: int = 170, lang: str = "chi_tra_vert") -> dict:
    if dpi < 100 or dpi > 400:
        raise ValueError("OCR DPI must be within 100..400")
    dest = out_dir / "transcripts" / source_id
    dest.mkdir(parents=True, exist_ok=True)
    page_str = f"{page:03d}"
    text_out = dest / f"{page_str}.txt"
    meta_out = dest / f"{page_str}.ocr.json"
    with tempfile.TemporaryDirectory(prefix="faceface-ocr-") as tmp:
        tmp_path = Path(tmp)
        image = tmp_path / "page.png"
        # Poppler uses ONE-BASED page indices; Faceface index is ZERO-BASED.
        run(["pdftoppm", "-f", str(page + 1), "-l", str(page + 1),
             "-r", str(dpi), "-gray", "-singlefile", "-png",
             str(pdf), str(image.with_suffix(""))])
        if not image.exists() or not image.stat().st_size:
            raise ValueError(f"No rendered PDF image: {source_id} page {page}")
        target = tmp_path / "page-ocr"
        run(["tesseract", str(image), str(target), "-l", lang,
             "--psm", "5", "-c", "preserve_interword_spaces=1", "txt", "tsv"])
        recognized = target.with_suffix(".txt").read_text(
            encoding="utf-8", errors="replace").strip()
        word_count, mean_confidence = tsv_confidence(target.with_suffix(".tsv"))
    han_count = len(HAN_RE.findall(recognized))
    state = "ocr_candidate" if recognized else "empty_ocr_candidate"
    # Never persist empty txt: the M16.1 strict staging gate rejects blanks.
    if recognized:
        text_out.write_text(recognized + "\n", encoding="utf-8")
    elif text_out.exists():
        text_out.unlink()
    metadata = {
        "page_id": f"{source_id}:p{page_str}",
        "source_id": source_id,
        "pdf_page_zero_based": page,
        "source_pdf_sha256": pdf_hash,
        "ocr_version": VERSION,
        "engine": "tesseract",
        "language": lang,
        "page_segmentation_mode": 5,
        "render_dpi": dpi,
        "state": state,
        "candidate_text_sha256": digest(text_out) if recognized else None,
        "han_char_count": han_count,
        "ocr_word_count": word_count,
        "mean_word_confidence": mean_confidence,
        "requires_manual_page_review": True,
        "eligible_for_cangjie_verified_corpus": False,
        "warning": "OCR-only, possibly out-of-order vertical columns; not proofread",
    }
    meta_out.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def batch(scan_dir: Path, out_dir: Path, source_id: str,
          start: int = 0, end: int | None = None, dpi: int = 170) -> dict:
    scan = next((x for x in SCANS if x["id"] == source_id), None)
    if scan is None:
        raise ValueError("Unknown source ID; use one of " + ", ".join(x["id"] for x in SCANS))
    pdf = scan_dir / scan["file"]
    count = pdf_pages(pdf)
    if count != scan["expected_pages"]:
        raise ValueError(f"{source_id}: page count changed, expected {scan['expected_pages']}, got {count}")
    if end is None:
        end = count - 1
    if not (0 <= start <= end < count):
        raise ValueError(f"Invalid zero-based inclusive page range {start}..{end} of {count}")
    pdf_hash = digest(pdf)
    pages = [ocr_page(pdf, source_id, page, out_dir, pdf_hash, dpi=dpi)
             for page in range(start, end + 1)]
    summary = {
        "source_id": source_id,
        "source_pdf_sha256": pdf_hash,
        "total_pdf_pages": count,
        "first_pdf_page_zero_based": start,
        "last_pdf_page_zero_based": end,
        "expected_processed_pages": end - start + 1,
        "processed_pages": len(pages),
        "pages_with_candidate_text": sum(p["state"] == "ocr_candidate" for p in pages),
        "pages_without_candidate_text": sum(p["state"] == "empty_ocr_candidate" for p in pages),
        "candidate_han_character_count": sum(p["han_char_count"] for p in pages),
        "candidate_characters_are_unreviewed": True,
        "human_reviewed_pages_from_this_run": 0,
        "cangjie_agent_extraction_performed": False,
        "cangjie_active_rules_created": 0,
        "pages": pages,
    }
    manifest = out_dir / "reports" / f"{source_id}-p{start:03d}-{end:03d}.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "pages"},
                     ensure_ascii=False))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--source", required=True, choices=[x["id"] for x in SCANS])
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int)
    parser.add_argument("--dpi", type=int, default=170)
    args = parser.parse_args()
    batch(args.scan_dir, args.out_dir, args.source, args.start, args.end, args.dpi)


if __name__ == "__main__":
    main()
