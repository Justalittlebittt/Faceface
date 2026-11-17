#!/usr/bin/env python3
"""M16.3: compare OCR configurations against already checked scan-page phrases.

Benchmarks are *diagnostic*, NOT ground truth accuracy: historical excerpt
snippets do not represent full-page transcription, and reference phrasing may
not appear contiguously in the scan. No OCR candidates are approved.
"""
from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import hashlib
import json
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

HAN_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
ANCHOR_SPLIT = re.compile(r"[·；;，,、。]+")

CONFIGS = (
    ("baseline_chi_vert_170", 170, "chi_tra_vert", 5, False),
    ("crop_chi_vert_220", 220, "chi_tra_vert", 5, True),
    ("crop_chi_vert_psm3_220", 220, "chi_tra_vert", 3, True),
    ("crop_hant_vert_220", 220, "script/HanT_vert", 5, True),
)
SECOND_SCAN_TEST_PAGES = (10, 40, 80)


def only_han(text: str) -> str:
    return "".join(HAN_RE.findall(text))


def reference_anchors(catalog: dict, source_id: str) -> dict[int, list[str]]:
    anchors: dict[int, list[str]] = defaultdict(list)
    for card in catalog["cards"] + catalog.get("framework_notes", []):
        source = card["source"]
        sid = "nlc-44091" if "44091" in source["source_url"] else \
              "nlc-44092" if "44092" in source["source_url"] else None
        if sid != source_id:
            continue
        phrase = card.get("source_phrase") or card.get("quote") or ""
        for part in ANCHOR_SPLIT.split(phrase):
            normalized = only_han(part)
            if len(normalized) >= 2 and normalized not in anchors[source["pdf_page_zero_based"]]:
                anchors[source["pdf_page_zero_based"]].append(normalized)
    return dict(anchors)


def anchor_probe(ocr_text: str, anchors: list[str]) -> dict:
    text = only_han(ocr_text)
    if not anchors:
        return {"reference_phrase_count": 0, "exact_phrase_count": 0,
                "mean_longest_contiguous_ratio": None}
    exact = sum(phrase in text for phrase in anchors)
    scores = []
    for phrase in anchors:
        match = SequenceMatcher(a=phrase, b=text, autojunk=False).find_longest_match(
            0, len(phrase), 0, len(text))
        scores.append(match.size / len(phrase))
    return {
        "reference_phrase_count": len(anchors),
        "exact_phrase_count": exact,
        "mean_longest_contiguous_ratio": round(sum(scores) / len(scores), 3),
    }


def shell(args: list[str]) -> None:
    p = subprocess.run(args, capture_output=True, text=True, errors="replace")
    if p.returncode:
        raise RuntimeError(f"{args[0]} failed: {p.stderr[-450:]}")


def crop_ink(image: Path, output: Path) -> None:
    from PIL import Image, ImageOps
    with Image.open(image) as im:
        gray = ImageOps.autocontrast(im.convert("L"))
        inverted = gray.point(lambda v: 255 if v < 190 else 0)
        box = inverted.getbbox()
        if box:
            l, t, r, b = box
            if r - l > 80 and b - t > 80:
                pad = 28
                gray = gray.crop((
                    max(0, l - pad), max(0, t - pad),
                    min(gray.width, r + pad), min(gray.height, b + pad)
                ))
        gray.save(output)


def recognize(image: Path, target: Path, language: str, psm: int) -> tuple[str, float | None]:
    from scripts.cangjie_ocr_candidates import tsv_confidence
    shell(["tesseract", str(image), str(target), "-l", language,
           "--psm", str(psm), "-c", "preserve_interword_spaces=1", "txt", "tsv"])
    text = target.with_suffix(".txt").read_text(encoding="utf-8", errors="replace")
    _, conf = tsv_confidence(target.with_suffix(".tsv"))
    return text, conf


def benchmark(pdf: Path, source_id: str, catalog: dict, out: Path) -> dict:
    from scripts.cangjie_corpus_stage import SCANS, pdf_pages
    source = next(s for s in SCANS if s["id"] == source_id)
    if pdf_pages(pdf) != source["expected_pages"]:
        raise ValueError("Original PDF page count mismatch")
    anchor_by_page = reference_anchors(catalog, source_id)
    page_ids = sorted(anchor_by_page) if anchor_by_page else list(SECOND_SCAN_TEST_PAGES)
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    observations: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="faceface-ocr-benchmark-") as temp:
        work = Path(temp)
        for page in page_ids:
            for label, dpi, language, psm, crop in CONFIGS:
                original = work / f"{source_id}-{page:03d}-{dpi}.png"
                if not original.exists():
                    shell(["pdftoppm", "-f", str(page+1), "-l", str(page+1),
                           "-r", str(dpi), "-gray", "-singlefile", "-png",
                           str(pdf), str(original.with_suffix(""))])
                image = original
                if crop:
                    image = work / f"{source_id}-{page:03d}-{dpi}-cropped.png"
                    if not image.exists():
                        crop_ink(original, image)
                target = work / f"{source_id}-{page:03d}-{label}"
                recognized, confidence = recognize(image, target, language, psm)
                anchors = anchor_by_page.get(page, [])
                results = anchor_probe(recognized, anchors)
                observations.append({
                    "source_id": source_id, "page_id": f"{source_id}:p{page:03d}",
                    "pdf_page_zero_based": page, "configuration": label,
                    "ocr_han_characters": len(only_han(recognized)),
                    "ocr_mean_word_confidence": confidence,
                    "reference_anchor_probe": results,
                    "reviewed_source_page": False,
                })
    comparisons = []
    for label, *_ in CONFIGS:
        rows = [o for o in observations if o["configuration"] == label]
        confidences = [r["ocr_mean_word_confidence"] for r in rows
                       if r["ocr_mean_word_confidence"] is not None]
        anchor_rows = [r for r in rows if r["reference_anchor_probe"]["reference_phrase_count"]]
        comparisons.append({
            "configuration": label,
            "pages_sampled": len(rows),
            "mean_word_confidence": round(sum(confidences)/len(confidences), 1)
                if confidences else None,
            "total_ocr_han_chars": sum(r["ocr_han_characters"] for r in rows),
            "anchor_exact_hits": sum(r["reference_anchor_probe"]["exact_phrase_count"]
                                     for r in anchor_rows),
            "reference_anchor_count": sum(r["reference_anchor_probe"]["reference_phrase_count"]
                                          for r in anchor_rows),
            "anchor_mean_longest_contiguous_ratio": round(
                sum(r["reference_anchor_probe"]["mean_longest_contiguous_ratio"]
                    for r in anchor_rows)/len(anchor_rows), 3)
                if anchor_rows else None,
        })
    result = {
        "status": "sample_ocr_configuration_probe_only",
        "source_id": source_id, "source_pdf_sha256": sha,
        "sample_pages_zero_based": page_ids,
        "number_of_reference_pages": len(anchor_by_page),
        "comparisons": comparisons, "per_page_stats": observations,
        "full_transcription_reliability_verified": False,
        "agent_cangjie_extraction_performed": False,
        "note": ("Source phrases are short previously checked excerpts. Exact substring and "
                 "longest-contiguous metrics are DIAGNOSTIC PROXIES, not OCR accuracy. "
                 "Do not auto-select or publish a model without page image review.")
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "per_page_stats"},
                     ensure_ascii=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", type=Path, required=True)
    parser.add_argument("--source", required=True, choices=["nlc-44091", "nlc-44092"])
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    benchmark(args.scan, args.source,
              json.loads(args.catalog.read_text(encoding="utf-8")), args.out)


if __name__ == "__main__":
    main()
