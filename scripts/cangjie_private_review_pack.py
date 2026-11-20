#!/usr/bin/env python3
"""M16.24: create a private, reproducible original-image review packet.

Input is a genuine M16.22 private per-shard Qwen result (NOT a public aggregate).
Outputs per-page original scan PNG, model/OCR candidates, review worksheet and
a self-contained local HTML index. Every record remains source_unverified.
Neither rendering an image nor a reviewer noting a short span constitutes
complete-page transcription or production-rule approval.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from html import escape
import hashlib
import json
from pathlib import Path
import re

from scripts.cangjie_historical_claim_ledger import validate_relations
from scripts.cangjie_private_ocr_semantic_batch import BATCH_KIND
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, ReviewWorkspace, atomic_write

HEX24 = re.compile(r"^[0-9a-f]{24}$")


def assemble_review_items(private: dict) -> tuple[list[dict], dict]:
    if (private.get("kind") != BATCH_KIND
        or private.get("full_book_source_text_verified") is not False
        or private.get("no_live_rules_created") is not True):
        raise ValueError("Only a real M16.22 unverified private record is accepted")
    sources = private.get("source_records_UNVERIFIED")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Actual source excerpts are required; public aggregates cannot reconstruct them")
    byid = {}
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("Invalid private source")
        sid, page, cid = (source.get("source_id"), source.get("pdf_page_zero_based"),
                          source.get("id"))
        excerpt = source.get("source_excerpt")
        if (sid not in KNOWN_SCAN_SHA256
            or type(page) is not int or not 0 <= page < (153 if sid=="nlc-44091" else 115)
            or source.get("original_pdf_sha256") != KNOWN_SCAN_SHA256[sid]
            or not isinstance(cid,str) or not cid.startswith("m1622-ocr:")
            or not HEX24.fullmatch(cid[10:])
            or cid in byid
            or not isinstance(excerpt,str) or not 2 <= len(excerpt) <= 80
            or source.get("source_excerpt_sha256") != hashlib.sha256(excerpt.encode()).hexdigest()
            or source.get("source_excerpt_newly_human_reviewed") is not False
            or source.get("this_experiment_may_add_live_rule") is not False):
            raise ValueError("Invalid original source/short OCR excerpt provenance")
        byid[cid] = source
    ledger = private.get("archival_ledger_SOURCE_UNVERIFIED")
    audit = validate_relations(ledger)
    records = {}
    for source in sources:
        records[source["id"]] = {
            "candidate_id": source["id"],
            "source_id": source["source_id"],
            "original_pdf_sha256": source["original_pdf_sha256"],
            "pdf_page_zero_based": source["pdf_page_zero_based"],
            "page_id": source["page_id"],
            "unreviewed_OCR_excerpt": source["source_excerpt"],
            "unreviewed_OCR_excerpt_sha256": source["source_excerpt_sha256"],
            "unreviewed_OCR_full_page_sha256": source["unreviewed_ocr_text_sha256"],
            "lexical_domain_hints": source["candidate_lexical_domains"],
            "accepted_model_relations_unverified": [],
            "model_rejections": [],
            "human_short_excerpt_review_state": "pending",
            "human_complete_page_transcription_verified": False,
            "eligible_for_live_rules": False,
        }
    for relation in ledger["relations"]:
        cid = relation["source_passage_id"]
        src = byid.get(cid)
        if (not src
            or relation["source_id"] != src["source_id"]
            or relation["pdf_page_zero_based"] != src["pdf_page_zero_based"]
            or relation["source_pdf_sha256"] != src["original_pdf_sha256"]
            or relation["quote_original"] != src["source_excerpt"]
            or relation["transcription_review_status"] != "source_unverified"
            or relation["report_eligibility"] != "archive_only"):
            raise ValueError("Model relation is not literally traceable to this private OCR source")
        records[cid]["accepted_model_relations_unverified"].append(relation)
    for rejection in private.get("rejections_private", []):
        if not isinstance(rejection,dict) or rejection.get("source_id") not in byid:
            raise ValueError("Model rejection lacks a matching private source")
        # Preserve reason for review; never treat a rejected model suggestion as evidence.
        records[rejection["source_id"]]["model_rejections"].append(rejection)
    if private.get("actual_model_requests_attempted") != len(sources):
        raise ValueError("Model attempt count does not match source candidates")
    items = sorted(records.values(), key=lambda x: (
        x["source_id"], x["pdf_page_zero_based"], x["candidate_id"]))
    count = Counter(x["source_id"] for x in items)
    summary = {
        "schema":"M16.24_PRIVATE_ORIGINAL_PAGE_REVIEW_PACK_V1",
        "source_count":len(items),
        "distinct_original_pages":len({x["page_id"] for x in items}),
        "source_counts_by_scan":dict(count),
        "literal_OCR_model_drafts":audit["relation_count"],
        "rejected_model_events":sum(len(x["model_rejections"]) for x in items),
        "human_short_spans_reviewed_by_this_build":0,
        "human_full_page_reviews_by_this_build":0,
        "verified_historical_relations":0,
        "live_rules_added":0,
        "original_text_in_public_metadata":False,
        "review_workbook_is_private_only":True,
    }
    return items, summary


def make_review_html(items: list[dict], summary: dict) -> str:
    by_page = defaultdict(list)
    for item in items:
        by_page[item["page_id"]].append(item)
    sections = []
    for page_id, rows in by_page.items():
        source, index = rows[0]["source_id"], rows[0]["pdf_page_zero_based"]
        image = f"pages/{source}-p{index:03d}.png"
        cards = []
        for row in rows:
            excerpts = escape(row["unreviewed_OCR_excerpt"])
            relations = "".join(
                "<li>形态："+escape(str(x.get("morphology_original") or "（未给出）"))
                +"｜传统断语："+escape(str(x.get("historical_claim_original") or "（未给出）"))
                +"｜领域："+escape(",".join(x["historical_claim_domains"]))
                +"｜关系："+escape(x["traditional_relation_type"])+"</li>"
                for x in row["accepted_model_relations_unverified"])
            reasons = ", ".join(escape(str(x["reason"])) for x in row["model_rejections"])
            cards.append(
                "<article><p><code>"+escape(row["candidate_id"])+"</code></p>"
                +"<p>OCR 原文候选（未校勘）：<strong>"+excerpts+"</strong></p>"
                +"<p>模型候选（未证实）：</p><ul>"+relations+"</ul>"
                +"<p>模型拒绝原因："+(reasons or "无")+"</p>"
                +"<p>核验操作：对照左侧原版整页图，记录到 private-review-decisions.json；"
                +"不得凭OCR字面匹配自动签认。</p></article>"
            )
        sections.append("<section><h2>"+escape(page_id)+"（PDF第"+str(index+1)+"页）</h2>"
                        +"<div class='pair'><img alt='1925年原书页面扫描' src='"+image+"'>"
                        +"<div>"+"".join(cards)+"</div></div></section>")
    return """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'">
<title>Faceface 私有原图与OCR候选校勘</title><style>
body{font:15px/1.65 system-ui,sans-serif;max-width:1300px;margin:0 auto;padding:24px;color:#20252c;background:#f7f5ef}
h1{font-size:26px}h2{margin-top:28px}.pair{display:grid;grid-template-columns:minmax(260px,1fr) minmax(320px,1fr);gap:20px}
img{width:100%;border:1px solid #aaa;background:white}article{padding:12px 16px;background:white;border:1px solid #ddd;margin-bottom:12px;overflow-wrap:anywhere}
.notice{border:2px solid #9e6c33;padding:12px;background:#fff8e6}
@media(max-width:720px){.pair{grid-template-columns:1fr}}</style></head><body>
<h1>Faceface｜1925年《麻衣相法》私有原图校勘工作包</h1>
<p class="notice">以下文本均来自未人工校勘的OCR和模型。此页面只供私有核对，不等于历史断语已证实，更不能把富贵、寿命、品德预测用于真人。</p>
<p>OCR候选数："""+str(summary["source_count"])+"；待核对原图页数："+str(summary["distinct_original_pages"])+"""。完整页签认数：0。</p>
"""+"".join(sections)+"</body></html>"


def build_pack(record_path: Path, scan_dir: Path, out_dir: Path, dpi: int=150) -> dict:
    if dpi not in (120,150,200,250):
        raise ValueError("Unsupported source preview DPI")
    input_path, output = record_path.resolve(), out_dir.resolve()
    if output == input_path or output.is_relative_to(input_path.parent) and output.name == input_path.name:
        raise ValueError("Private input must not be overwritten")
    if output.exists():
        raise ValueError("Review bundle destination exists; never silently replace manual notes")
    private = json.loads(input_path.read_text(encoding="utf-8"))
    items, summary = assemble_review_items(private)
    workspace = ReviewWorkspace(scan_dir, output/"_ocr_absent",output/"_review_absent")
    # Verify every source original SHA and render actual page image; do not
    # invent a page view from OCR or static catalog labels.
    for item in items:
        sid, index = item["source_id"],item["pdf_page_zero_based"]
        if workspace.sources[sid]["pdf_sha256"] != item["original_pdf_sha256"]:
            raise ValueError("Original image PDF changed after OCR run")
        image = workspace.image_path(sid,index,dpi)
        dest = output/"pages"/f"{sid}-p{index:03d}.png"
        atomic_write(dest, image.read_bytes())
    decisions = {
        "schema":"M16.24_PRIVATE_SHORT_EXCERPT_DECISIONS_TEMPLATE_V1",
        "must_be_manually_filled_after_image_comparison":True,
        "full_page_transcription_reviewed":False,
        "items":[{
            "candidate_id":x["candidate_id"],
            "source_id":x["source_id"],
            "pdf_page_zero_based":x["pdf_page_zero_based"],
            "original_pdf_sha256":x["original_pdf_sha256"],
            "ocr_excerpt_sha256":x["unreviewed_OCR_excerpt_sha256"],
            "status":"pending",
            "manually_corrected_original_text":"",
            "reviewer":"",
            "confirmed_against_original_page_image":False,
            "review_notes":"",
        } for x in items],
    }
    atomic_write(output/"private-OCR-model-evidence.json",
                 (json.dumps(items,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    atomic_write(output/"private-review-decisions.json",
                 (json.dumps(decisions,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    atomic_write(output/"index.html", make_review_html(items,summary).encode("utf-8"))
    files = sorted((output/"pages").glob("*.png"))
    summary["real_original_PDF_images_rendered"] = len(files)
    summary["source_original_PDF_sha256"] = dict(KNOWN_SCAN_SHA256)
    summary["source_proofreading_still_required"] = True
    atomic_write(output/"private-pack-manifest.json",
                 (json.dumps(summary,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    # Only this *summary* may be copied to public repository; private pack
    # intentionally contains OCR words and model text and MUST NEVER upload.
    print(json.dumps(summary,ensure_ascii=False))
    return summary


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-record",type=Path,required=True)
    p.add_argument("--scan-dir",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--dpi",type=int,default=150)
    a=p.parse_args()
    build_pack(a.private_record,a.scan_dir,a.out_dir,a.dpi)


if __name__=="__main__":
    main()
