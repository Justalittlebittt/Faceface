#!/usr/bin/env python3
"""M16.21: real 268-page OCR lexical audit of traditional outcome themes.

Works on original-PDF-hashed *unreviewed* PP-OCRv5 page transcripts. The
historical fate/virtue/wealth terminology is preserved for archival research,
including pages with NO facial morphology cue. Even same OCR-line proximity is
NOT proof that a text links a particular face to an outcome. Never publish
original OCR text or candidate snippets from this tool.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from scripts.cangjie_corpus_stage import SCANS, pdf_pages
from scripts.cangjie_paddleocr_candidates import OCR_ID, ENGINE
from scripts.cangjie_morphology_mine import REGIONS, DESCRIPTORS, weak_match, han_only
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write, file_sha256

VERSION = "M16.21_REAL_1925_UNREVIEWED_OCR_TRADITIONAL_OUTCOME_V1"
# Lexical research signals only. "壽" can be part of anatomical term 年壽;
# "貴" can be part of an unrelated name; neither is a verified assertion.
OUTCOME_TERMS = {
    "wealth": ("富貴", "富裕", "貧賤", "貧窮", "財帛", "財運", "財富", "衣祿", "祿位", "富", "貧", "財", "祿"),
    "longevity": ("長壽", "短壽", "壽夭", "夭壽", "壽數", "壽命", "不壽", "早夭", "壽", "夭"),
    "moral_character": ("忠厚", "仁義", "賢愚", "善惡", "奸邪", "仁", "德", "忠", "孝", "賢", "愚"),
    "temperament": ("性情", "性急", "剛毅", "柔和", "暴躁", "脾氣", "性格"),
    "marriage": ("婚姻", "夫妻", "妻妾", "配偶", "夫婦"),
    "family": ("家運", "家業", "六親", "父母", "兄弟", "家庭"),
    "offspring": ("子嗣", "子孫", "子女", "兒女"),
    "career": ("官祿", "官運", "功名", "仕途", "事業", "官"),
    "social_status": ("顯達", "尊貴", "權勢", "地位", "貴人"),
    "fortune": ("吉凶", "福禍", "禍福", "災厄", "福氣", "凶", "吉"),
}
# Ignore frequent anatomy word 年壽 as *standalone longevity signal*. It may
# describe the nose bridge region rather than a claim about lifespan.
LONGEVITY_ANATOMY_ONLY = re.compile(r"年壽")


def outcome_terms_for_line(line: str) -> dict[str, list[str]]:
    text = han_only(line)
    # A single-component "壽" that appears only in 年壽 is not outcome proof.
    filtered = LONGEVITY_ANATOMY_ONLY.sub("", text)
    found = {}
    for domain, terms in OUTCOME_TERMS.items():
        haystack = filtered if domain == "longevity" else text
        matches = sorted({term for term in terms if term in haystack})
        if matches:
            found[domain] = matches
    return found


def morphology_regions_for_line(line: str) -> list[str]:
    text = han_only(line)
    found = []
    for region, config in REGIONS.items():
        if any(term in text for term in config["strong"]):
            found.append(region)
            continue
        if any(weak_match(text, m.start(), weak)
               for weak in config["weak"] for m in re.finditer(re.escape(weak), text)):
            found.append(region)
    return sorted(found)


def audit_source_page(text: str, sid: str, page: int, pdf_hash: str,
                      ocr_hash: str) -> tuple[dict, list[dict]]:
    domains = Counter()
    proximity = Counter()
    cues = []
    morphological_lines = 0
    outcome_lines = 0
    for line_index, line in enumerate(text.splitlines()):
        outcomes = outcome_terms_for_line(line)
        shapes = morphology_regions_for_line(line)
        if shapes:
            morphological_lines += 1
        if outcomes:
            outcome_lines += 1
        for domain in outcomes:
            domains[domain] += 1
            if shapes:
                proximity[domain] += 1
        if not outcomes:
            continue
        # Private and source-hashed OCR candidate text; not an original quote.
        normalized = han_only(line)
        cue_id = hashlib.sha256(
            f"{sid}:p{page:03d}|{ocr_hash}|{line_index}|{normalized}".encode()
        ).hexdigest()[:24]
        cues.append({
            "cue_id": cue_id,
            "source_id": sid, "pdf_page_zero_based": page,
            "source_pdf_sha256": pdf_hash,
            "unreviewed_ocr_text_sha256": ocr_hash,
            "ocr_line_index_zero_based": line_index,
            "short_ocr_line_unverified": normalized[:80],
            "outcome_terms_UNVERIFIED": outcomes,
            "same_OCR_line_morphology_regions": shapes,
            "source_image_human_verified": False,
            "historical_relation_established": False,
            "eligible_for_live_rules": False,
        })
    page_record = {
        "source_id": sid,
        "page_id": f"{sid}:p{page:03d}",
        "pdf_page_zero_based": page,
        "source_pdf_sha256": pdf_hash,
        "ocr_text_sha256": ocr_hash or None,
        "outcome_ocr_line_hits_by_domain": dict(domains),
        "outcome_ocr_line_with_morphology_proximity_by_domain": dict(proximity),
        "lines_with_outcome_lexemes": outcome_lines,
        "lines_with_morphology_lexemes": morphological_lines,
        "historical_relation_confirmed": False,
        "human_reviewed": False,
    }
    return page_record, cues


def audit_shard(scan_dir: Path, ocr_dir: Path, private_dir: Path, metadata_dir: Path,
                sid: str, first: int, last: int) -> dict:
    scan = next((s for s in SCANS if s["id"] == sid), None)
    if not scan or not 0 <= first <= last < scan["expected_pages"]:
        raise ValueError("Unknown source or invalid page range")
    pdf = scan_dir / scan["file"]
    if pdf_pages(pdf) != scan["expected_pages"]:
        raise ValueError("Original PDF page count changed")
    pdf_hash = file_sha256(pdf)
    if pdf_hash != KNOWN_SCAN_SHA256[sid]:
        raise ValueError("Original scan SHA256 changed")
    pages, private_cues = [], []
    for page in range(first, last + 1):
        stem = ocr_dir / "transcripts" / sid / f"{page:03d}"
        meta_path = stem.with_suffix(".ocr.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if (meta.get("source_id") != sid
            or meta.get("pdf_page_zero_based") != page
            or meta.get("page_id") != f"{sid}:p{page:03d}"
            or meta.get("source_pdf_sha256") != pdf_hash
            or meta.get("ocr_version") != OCR_ID
            or meta.get("engine") != ENGINE
            or meta.get("requires_manual_page_review") is not True
            or meta.get("eligible_for_cangjie_verified_corpus") is not False):
            raise ValueError("Unverified/OCR provenance or index mismatch")
        text_path = stem.with_suffix(".txt")
        if meta.get("state") == "ocr_candidate":
            if (not text_path.is_file()
                or meta.get("candidate_text_sha256") != file_sha256(text_path)
                or len(han_only(text_path.read_text(encoding="utf-8"))) != meta.get("han_char_count")):
                raise ValueError("Stale or tampered OCR original candidate")
            raw = text_path.read_text(encoding="utf-8")
        elif meta.get("state") == "empty_ocr_candidate":
            if text_path.exists() or meta.get("candidate_text_sha256") is not None:
                raise ValueError("Inconsistent empty OCR page")
            raw = ""
        else:
            raise ValueError("Invalid OCR page state")
        record, cues = audit_source_page(
            raw, sid, page, pdf_hash, meta.get("candidate_text_sha256") or ""
        )
        record["OCR_state"] = meta["state"]
        pages.append(record)
        private_cues.extend(cues)
    totals = Counter()
    proximity = Counter()
    unique_domain_pages = Counter()
    for page in pages:
        for domain, n in page["outcome_ocr_line_hits_by_domain"].items():
            totals[domain] += n
            unique_domain_pages[domain] += 1
        for domain, n in page["outcome_ocr_line_with_morphology_proximity_by_domain"].items():
            proximity[domain] += n
    report = {
        "kind": VERSION,
        "source_id": sid,
        "source_pdf_sha256": pdf_hash,
        "first_pdf_page_zero_based": first,
        "last_pdf_page_zero_based": last,
        "processed_original_pages": len(pages),
        "pages_with_any_outcome_lexical_signal": sum(bool(p["outcome_ocr_line_hits_by_domain"]) for p in pages),
        "pages_with_no_outcome_lexical_signal": sum(not p["outcome_ocr_line_hits_by_domain"] for p in pages),
        "pages_by_domain": dict(unique_domain_pages),
        "OCR_line_hits_by_domain": dict(totals),
        "same_OCR_line_morphology_cooccurrence_by_domain": dict(proximity),
        "unreviewed_ocr_cues_private_count": len(private_cues),
        "pages": pages,
        "actual_human_confirmed_historical_relations": 0,
        "official_Cangjie_model_calls": 0,
        "new_live_Faceface_rules": 0,
        "metadata_contains_ancient_ocr_text": False,
        "warning": "UNREVIEWED OCR lexical signals, including false positives; NO verified linkage.",
    }
    stem = f"{sid}-p{first:03d}-{last:03d}"
    atomic_write(private_dir / (stem + ".jsonl"),
                 ("\n".join(json.dumps(x, ensure_ascii=False) for x in private_cues) + "\n").encode())
    atomic_write(metadata_dir / (stem + ".json"),
                 (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({k:v for k,v in report.items() if k != "pages"}, ensure_ascii=False))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-dir", type=Path, required=True)
    parser.add_argument("--ocr-dir", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--metadata-dir", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    args = parser.parse_args()
    audit_shard(args.scan_dir, args.ocr_dir, args.private_dir,
                args.metadata_dir, args.source, args.start, args.end)


if __name__ == "__main__":
    main()
