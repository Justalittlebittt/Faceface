#!/usr/bin/env python3
"""M16.7 private, explicitly UNVERIFIED whole-book OCR working corpus.

Bridges source-validated PP-OCRv5 candidates to official pinned Cangjie
deterministic build_chunks.py. Source-unverified extraction hypotheses are
permitted internally, never as verified original quotations or online rules.
Neither the original scans nor these texts are uploaded to public GitHub.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from scripts.cangjie_review_core import ReviewWorkspace, atomic_write

PINNED_CANGJIE_COMMIT = "a28de55ba881b9928956a55048f743f7a9e3b23e"
SOURCE_ID = "faceface-maiyi-1925-268-page-OCR-UNVERIFIED"


def compile_corpus(workspace: ReviewWorkspace, out_dir: Path) -> dict:
    entries = []
    body = [
        "# Faceface 1925 《麻衣相法》 UNVERIFIED OCR WORKING CORPUS",
        "",
        "EVIDENCE WARNING: Most text is machine OCR from vertical classical"
        " Chinese scans, NOT original-image-reviewed source. This is for"
        " internal candidate discovery; never publish rules from OCR alone.",
        ""
    ]
    statuses = {"reviewed": 0, "ocr_unreviewed": 0, "missing_or_invalid": 0}
    chars = {"reviewed": 0, "ocr_unreviewed": 0}
    for sid, scan in workspace.sources.items():
        for index in range(scan["page_count"]):
            info = workspace.page_info(sid, index)
            if info["is_reviewed_full_page"]:
                state, page_text = "reviewed", info["reviewed_text"].strip()
            elif info["ocr_candidate_provenance_ok"]:
                state, page_text = "ocr_unreviewed", info["ocr_candidate"].strip()
            else:
                state, page_text = "missing_or_invalid", ""
            statuses[state] += 1
            entries.append({
                "page_id": f"{sid}:p{index:03d}",
                "source_id": sid,
                "pdf_page_zero_based": index,
                "source_pdf_sha256": scan["pdf_sha256"],
                "source_text_state": state,
                "in_private_working_text": bool(page_text),
                "cannot_activate_without_original_image_review": state != "reviewed"
            })
            if not page_text:
                continue
            chars[state] += len(page_text)
            body.extend([
                f"## ORIGINAL SCAN PAGE {sid}:p{index:03d}",
                "",
                f"- Source URL: {scan['source_url']}",
                f"- Source PDF SHA256: {scan['pdf_sha256']}",
                f"- PDF zero-based page: {index}",
                f"- Evidence status: {state}",
                f"- Original-image reviewed: {'YES' if state=='reviewed' else 'NO'}",
                "",
                page_text,
                ""
            ])
    if sum(statuses.values()) != 268:
        raise ValueError("Expected exactly 268 source page records")
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(
        out_dir/"working-corpus-OCR-UNVERIFIED.md",
        ("\n".join(body)+"\n").encode("utf-8")
    )
    audit = {
        "kind": "FACEFACE_M16_7_PRIVATE_WORKING_CORPUS_NOT_VERIFIED_ORIGINAL",
        "original_pdf_count": len(workspace.sources),
        "original_pages": sum(statuses.values()),
        "text_states": statuses,
        "private_working_text_pages": statuses["reviewed"]+statuses["ocr_unreviewed"],
        "characters_by_source_status": chars,
        "official_cangjie_agent_extraction_executed": False,
        "published_faceface_rules_added": 0,
        "original_page_status_ledger": entries,
        "warning": "OCR unreviewed corpus is for source-unverified discovery ONLY."
    }
    atomic_write(
        out_dir/"working-corpus-audit.json",
        (json.dumps(audit,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    )
    print(json.dumps(
        {k:v for k,v in audit.items() if k != "original_page_status_ledger"},
        ensure_ascii=False
    ))
    return audit


def official_chunks(cangjie_root: Path, out_dir: Path) -> dict:
    script = cangjie_root/"scripts"/"build_chunks.py"
    skill = cangjie_root/"SKILL.md"
    if not script.is_file() or not skill.is_file():
        raise ValueError("Official Cangjie checkout must include SKILL.md and build_chunks.py")
    try:
        git = subprocess.run(
            ["git","-C",str(cangjie_root),"rev-parse","HEAD"],
            check=True,capture_output=True,text=True
        ).stdout.strip()
    except (OSError,subprocess.CalledProcessError):
        raise ValueError("Official Cangjie checkout must be pinned in git") from None
    if git != PINNED_CANGJIE_COMMIT:
        raise ValueError(
            f"Wrong Cangjie commit {git}, expected {PINNED_CANGJIE_COMMIT}"
        )
    corpus = out_dir/"working-corpus-OCR-UNVERIFIED.md"
    if not corpus.is_file():
        raise ValueError("Private working corpus must exist first")
    sidecar = out_dir/"cangjie-working-sidecar"
    subprocess.run(
        [sys.executable,str(script),str(corpus),"--sidecar",str(sidecar),
         "--source-id",SOURCE_ID,"--max-chars","2000"],
        check=True
    )
    return {
        "official_cangjie_pinned_commit": git,
        "actual_upstream_build_chunks_executed": True,
        "sidecar_directory": str(sidecar),
        "Adler_agent_extraction_executed": False,
        "five_semantic_agent_extractors_executed": False
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-dir",type=Path,required=True)
    parser.add_argument("--ocr-dir",type=Path,required=True)
    parser.add_argument("--reviewed-dir",type=Path,required=True)
    parser.add_argument("--out-dir",type=Path,required=True)
    parser.add_argument("--cangjie-root",type=Path)
    a = parser.parse_args()
    w = ReviewWorkspace(a.scan_dir,a.ocr_dir,a.reviewed_dir)
    audit = compile_corpus(w,a.out_dir)
    if a.cangjie_root:
        if not audit["private_working_text_pages"]:
            raise SystemExit("No actual source OCR text to chunk; refusing false progress")
        print(json.dumps(official_chunks(a.cangjie_root,a.out_dir),ensure_ascii=False))


if __name__ == "__main__":
    main()
