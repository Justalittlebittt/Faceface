#!/usr/bin/env python3
"""M16: inventory the two 1925 scans and prepare audited Cangjie inputs.

This is a DETERMINISTIC source-staging tool, not an OCR engine or an AI agent.
No transcription is claimed until page text and a matching review record exist.
The ten already-checked legacy excerpts are a small preprocessing smoke fixture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

SCANS = (
    {
        "id": "nlc-44091",
        "file": "part1.pdf",
        "expected_pages": 153,
        "url": "https://commons.wikimedia.org/wiki/File:NLC416-12jh002690-44091_麻衣相法_第1卷.pdf",
    },
    {
        "id": "nlc-44092",
        "file": "part2.pdf",
        "expected_pages": 115,
        "url": "https://commons.wikimedia.org/wiki/File:NLC416-12jh002690-44092_麻衣相法_第2卷.pdf",
    },
)
EXTRACTORS = ("framework", "principle", "case", "counter-example", "glossary")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pdf_pages(path: Path) -> int:
    if not path.read_bytes()[:5] == b"%PDF-":
        raise ValueError(f"Not a PDF: {path}")
    result = subprocess.run(["pdfinfo", str(path)], check=True, capture_output=True, text=True)
    match = re.search(r"^Pages:\s+(\d+)$", result.stdout, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"Missing page count in pdfinfo: {path}")
    return int(match.group(1))


def verify_page_review(text_path: Path, pdf_hash: str, page: int) -> bool:
    """A separate reviewed record MUST match actual page text and PDF bytes."""
    review_path = text_path.with_suffix(".review.json")
    if not review_path.exists():
        return False
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if review.get("reviewed_by") in (None, "", "auto", "ocr"):
        raise ValueError(f"Review requires a named reviewer: {review_path}")
    if (review.get("source_pdf_sha256") != pdf_hash
            or review.get("pdf_page_zero_based") != page
            or review.get("text_sha256") != sha256(text_path.read_bytes())):
        raise ValueError(f"Review provenance/hash mismatch: {review_path}")
    return True


def index_scans(scan_dir: Path, transcripts_dir: Path) -> tuple[list[dict], list[dict], list[str]]:
    sources: list[dict] = []
    pages: list[dict] = []
    checked_text: list[str] = []
    for scan in SCANS:
        pdf = scan_dir / scan["file"]
        count = pdf_pages(pdf)
        if count != scan["expected_pages"]:
            raise ValueError(f"{scan['id']}: expected {scan['expected_pages']} pages, got {count}")
        pdf_hash = sha256(pdf.read_bytes())
        sources.append({
            "source_id": scan["id"], "source_url": scan["url"],
            "pdf_sha256": pdf_hash, "page_count": count,
            "printed_volumes": "not_yet_fully_mapped",
            "source_type": "1925_Wenming_Press_scanned_fascicle",
        })
        for page in range(count):
            key = f"{page:03d}"
            text_file = transcripts_dir / scan["id"] / (key + ".txt")
            state = "not_transcribed"
            if text_file.exists():
                content = text_file.read_text(encoding="utf-8").strip()
                if not content:
                    raise ValueError(f"Blank transcript file: {text_file}")
                is_reviewed = verify_page_review(text_file, pdf_hash, page)
                state = "reviewed" if is_reviewed else "unreviewed"
                if is_reviewed:
                    checked_text.append(
                        f"## {scan['id']} / PDF zero-based page {page}\n\n"
                        f"Original scan: {scan['url']}\n\n{content}\n"
                    )
            pages.append({
                "source_id": scan["id"], "pdf_page_zero_based": page,
                "page_id": f"{scan['id']}:p{key}", "scan_present": True,
                "text_status": state, "printed_volume": None, "section": None,
            })
    return sources, pages, checked_text


def pilot_from_existing_cards(catalog_path: Path, sources: list[dict]) -> tuple[str, int]:
    """Only existing human-checked short excerpts; NEVER whole-book transcription."""
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    known = {x["source_id"]: x for x in sources}
    snippets = []
    items = catalog["cards"] + catalog.get("framework_notes", [])
    for card in items:
        origin = card["source"]
        if "44091" in origin["source_url"]:
            sid = "nlc-44091"
        elif "44092" in origin["source_url"]:
            sid = "nlc-44092"
        else:
            raise ValueError(f"Unknown scan source: {card['id']}")
        if origin["pdf_page_zero_based"] >= known[sid]["page_count"]:
            raise ValueError(f"Source page out of bounds: {card['id']}")
        quote = card.get("source_phrase") or card.get("quote")
        if not quote:
            raise ValueError(f"Missing original phrase: {card['id']}")
        if len(quote) > 150:
            raise ValueError(f"Pilot source quote over Cangjie excerpt limit: {card['id']}")
        snippets.append(f"## {card['id']} / {sid} / page {origin['pdf_page_zero_based']}\n\n"
                        f"Quote: {quote}\n\n"
                        f"Scan reference: {origin['source_url']}\n")
    return (
        "# M16 PRE-EXISTING SHORT-EXCERPT PILOT — NOT THE WHOLE BOOK\n\n"
        "These quotations were already reviewed in Faceface V5; this document only "
        "tests official Cangjie deterministic document preprocessing. No OCR, "
        "new extraction, source-wide audit or distillation is claimed.\n\n"
        + "\n".join(snippets)
    ), len(snippets)


def agent_tasks() -> str:
    tasks = "\n".join(
        f"- {name}: run official upstream extractors/{name}-extractor.md "
        f"over ALL reviewed corpus chunks; save candidates/{name}.md and original page IDs"
        for name in EXTRACTORS
    )
    return (
        "# M16 Agent tasks — NOT RUN\n\n"
        "Requires actual reviewed source text, a whole-book Adler BOOK_OVERVIEW.md, "
        "and the pinned cangjie-skill SKILL.md / methodology. The upstream cangjie.py "
        "CLI does not run AI extractors automatically. Never present this checklist "
        "as completed output.\n\n"
        "1. Confirm source manifest and the two original 1925 scans; classify blank, "
        "figure and uncertain pages, map printed volumes and sections.\n"
        "2. Only send reviewed text to full-book extractors; preserve unreviewed "
        "material as explicit missing coverage, not fictitious quotes.\n"
        "3. Use cangjie-skill Stage 0 Adler to create BOOK_OVERVIEW.md, then five "
        "INDEPENDENT extractor passes (parallel when agent host supports it):\n"
        + tasks + "\n"
        "4. Perform Stage 1.5 source-sufficiency, executability and utility "
        "checks; route each candidate to verified/reference/needs_review/rejected, "
        "then create coverage-audit.md and source-bound page references.\n"
        "5. Map only original-scan-reviewed, photo-observable items into Faceface "
        "runtime candidates. Do NOT directly activate generated rules, infer "
        "personal outcomes or substitute numeric photo cutoffs for ancient criteria.\n"
    )


def stage(scan_dir: Path, transcripts_dir: Path, catalog: Path, out_dir: Path) -> dict:
    sources, pages, reviewed_text = index_scans(scan_dir, transcripts_dir)
    pilot, pilot_count = pilot_from_existing_cards(catalog, sources)
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {status: sum(1 for x in pages if x["text_status"] == status)
              for status in ("not_transcribed", "unreviewed", "reviewed")}
    report = {
        "project": "Faceface M16",
        "work": "1925 Wenming Press / Qin Shen'an collation",
        "source_file_count": len(sources),
        "scan_page_count": len(pages),
        "source_files": sources,
        "page_text_status_counts": counts,
        "verified_original_page_transcription_coverage": f"{counts['reviewed']}/{len(pages)}",
        "already_checked_short_excerpt_fixture_count": pilot_count,
        "agent_cangjie_extraction_performed": False,
        "candidate_count_from_full_book": 0,
        "ready_for_full_book_extraction": counts["reviewed"] == len(pages),
        "status": "source_pages_inventoried; full-book text/agent extraction NOT complete",
    }
    for name, doc in (
        ("scan-page-index.json", pages),
        ("corpus-audit.json", report),
    ):
        (out_dir / name).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
    (out_dir / "prechecked-excerpts-pilot.md").write_text(pilot, encoding="utf-8")
    (out_dir / "CANGJIE_AGENT_TASKS.md").write_text(agent_tasks(), encoding="utf-8")
    if reviewed_text:
        (out_dir / "reviewed-transcription.md").write_text(
            "# Reviewed 1925 scan transcription (page-bound excerpts)\n\n"
            + "\n".join(reviewed_text), encoding="utf-8")
    print(json.dumps({"pages": len(pages), "statuses": counts,
                      "prechecked_short_excerpts": pilot_count,
                      "full_book_agent_extraction": False}, ensure_ascii=False))
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan-dir", type=Path, required=True)
    p.add_argument("--transcripts-dir", type=Path, required=True)
    p.add_argument("--checked-cards", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args()
    stage(a.scan_dir, a.transcripts_dir, a.checked_cards, a.out_dir)


if __name__ == "__main__":
    main()
