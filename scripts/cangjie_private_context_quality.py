#!/usr/bin/env python3
"""M16.26: inspect real OCR line neighborhood behind each saved Cangjie claim.

All source OCR/model text stays in a new PRIVATE review sidecar. Reject wrong
PDF fingerprints, altered OCR pages, stale line indexes and mismatched model
sources. A contextual neighbor is NOT textual proof that a face feature causes
a classical outcome; ancient vertical reading order remains unverified.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import hashlib
import json
from pathlib import Path
import re

from scripts.cangjie_outcome_ocr_audit import (
    morphology_regions_for_line, outcome_terms_for_line
)
from scripts.cangjie_morphology_mine import han_only
from scripts.cangjie_private_ocr_semantic_batch import read_private_cues
from scripts.cangjie_private_review_pack import assemble_review_items
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write, file_sha256
from scripts.cangjie_paddleocr_candidates import OCR_ID, ENGINE


def audit_context(selected_path: Path, model_path: Path, ocr_root: Path,
                  neighbor_radius: int=2) -> tuple[list[dict],dict]:
    if type(neighbor_radius) is not int or not 1 <= neighbor_radius <= 4:
        raise ValueError("Neighbor radius must be 1..4 OCR lines")
    selected_sources, _ = read_private_cues([selected_path])
    raw = [json.loads(line) for line in selected_path.read_text(encoding="utf-8").splitlines()
           if line.strip()]
    model = json.loads(model_path.read_text(encoding="utf-8"))
    items, model_audit = assemble_review_items(model)
    expected = {"m1622-ocr:" + x["cue_id"]:x for x in raw}
    actual = {x["candidate_id"]:x for x in items}
    if set(actual) != set(expected) or len(selected_sources) != len(items):
        raise ValueError("Saved model source IDs and actual selected OCR lines disagree")
    model_sources={x["id"]:x for x in model["source_records_UNVERIFIED"]}
    pages={}
    records=[]
    alerts=Counter()
    priorities=Counter()
    for item in items:
        cid=item["candidate_id"]
        r=expected[cid]
        s=model_sources[cid]
        sid,page=r["source_id"],r["pdf_page_zero_based"]
        if (sid not in KNOWN_SCAN_SHA256
            or s["source_id"] != sid or s["pdf_page_zero_based"] != page
            or r["source_pdf_sha256"] != KNOWN_SCAN_SHA256[sid]
            or s["original_pdf_sha256"] != KNOWN_SCAN_SHA256[sid]
            or s["unreviewed_ocr_text_sha256"] != r["unreviewed_ocr_text_sha256"]
            or s["source_excerpt"] != r["short_ocr_line_unverified"]):
            raise ValueError("OCR/model/page provenance mismatch")
        key=(sid,page)
        if key not in pages:
            base=ocr_root/"transcripts"/sid/f"{page:03d}"
            path=base.with_suffix(".txt")
            meta_path=base.with_suffix(".ocr.json")
            if not path.is_file() or not meta_path.is_file():
                raise ValueError("Cannot contextualize without original OCR full page")
            meta=json.loads(meta_path.read_text(encoding="utf-8"))
            if (meta.get("source_id")!=sid or meta.get("pdf_page_zero_based")!=page
                or meta.get("source_pdf_sha256")!=KNOWN_SCAN_SHA256[sid]
                or meta.get("ocr_version")!=OCR_ID or meta.get("engine")!=ENGINE
                or meta.get("eligible_for_cangjie_verified_corpus") is not False
                or meta.get("requires_manual_page_review") is not True
                or meta.get("state")!="ocr_candidate"
                or meta.get("candidate_text_sha256")!=file_sha256(path)):
                raise ValueError("Tampered or non-original unreviewed OCR full page")
            lines=path.read_text(encoding="utf-8").splitlines()
            pages[key]=(lines,meta["candidate_text_sha256"])
        lines,ocr_hash=pages[key]
        index=r.get("ocr_line_index_zero_based")
        if type(index) is not int or not 0<=index<len(lines):
            raise ValueError("Missing/invalid real OCR line index")
        raw_line=han_only(lines[index])
        expected_id=hashlib.sha256(
            f"{sid}:p{page:03d}|{ocr_hash}|{index}|{raw_line}".encode()
        ).hexdigest()[:24]
        if (expected_id != r["cue_id"]
            or raw_line[:80]!=r["short_ocr_line_unverified"]
            or ocr_hash != r["unreviewed_ocr_text_sha256"]):
            raise ValueError("OCR line/index/Cue ID does not match actual OCR bytes")
        first,last=max(0,index-neighbor_radius),min(len(lines),index+neighbor_radius+1)
        before=lines[first:index]
        after=lines[index+1:last]
        adjacent=before+after
        flags=[]
        if len(raw_line)>80:
            flags.append("OCR_line_truncated_at_80_Han")
        if len(raw_line)<5:
            flags.append("very_short_OCR_line")
        if not morphology_regions_for_line(lines[index]):
            flags.append("no_morphology_on_same_OCR_line")
        if len(outcome_terms_for_line(lines[index]))>1:
            flags.append("multiple_outcome_lexical_domains_on_one_line")
        if any(morphology_regions_for_line(x) for x in adjacent):
            flags.append("neighboring_OCR_line_contains_morphology")
        if any(outcome_terms_for_line(x) for x in adjacent):
            flags.append("neighboring_OCR_line_contains_outcome")
        if sum(han_only(x)==raw_line for x in lines)>1:
            flags.append("duplicate_OCR_line_on_page")
        if any(x["traditional_relation_type"]=="explicit_in_source"
               for x in item["accepted_model_relations_unverified"]):
            flags.append("model_asserts_explicit_link_not_human_verified")
        # Not proof of source claim. OCR order is engine output order, not
        # confidently reconstructed right-to-left text reading order.
        priority="manual_first" if any(x in flags for x in (
            "OCR_line_truncated_at_80_Han",
            "multiple_outcome_lexical_domains_on_one_line",
            "very_short_OCR_line",
            "no_morphology_on_same_OCR_line"
        )) else "manual_normal"
        alerts.update(flags)
        priorities[priority]+=1
        records.append({
            "candidate_id":cid,
            "source_id":sid,
            "original_pdf_sha256":KNOWN_SCAN_SHA256[sid],
            "pdf_page_zero_based":page,
            "ocr_line_index_zero_based":index,
            "full_page_unreviewed_OCR_sha256":ocr_hash,
            "exact_target_OCR_line_unreviewed":lines[index],
            "preceding_OCR_lines_unreviewed":before,
            "following_OCR_lines_unreviewed":after,
            "unreviewed_OCR_line_SHA256":hashlib.sha256(lines[index].encode()).hexdigest(),
            "accepted_model_relations_unverified":item["accepted_model_relations_unverified"],
            "model_rejections":item["model_rejections"],
            "lexical_risk_flags_NOT_probabilities":flags,
            "manual_review_priority":priority,
            "human_reviewed_original_page":False,
            "traditional_semantic_link_human_verified":False,
            "live_Faceface_rule_eligibility":False,
        })
    summary={
        "schema":"M16.26_UNREVIEWED_ORIGINAL_OCR_CONTEXT_QUALITY_AUDIT_V1",
        "candidate_count":len(records),
        "distinct_source_pages":len(pages),
        "model_OCR_literal_drafts":model_audit["literal_OCR_model_drafts"],
        "priorities":dict(priorities),
        "lexical_risk_flag_counts":dict(alerts),
        "OCR_reading_order_human_verified":False,
        "verified_source_image_transcriptions":0,
        "historically_verified_claim_links":0,
        "new_live_Faceface_rules":0,
        "private_original_text_not_in_public_metadata":True,
    }
    return records,summary


def html_report(rows:list[dict],summary:dict) ->str:
    blocks=[]
    for row in rows:
        source,page=row["source_id"],row["pdf_page_zero_based"]
        image=f"pages/{source}-p{page:03d}.png"
        make=lambda xs:"".join("<li>"+escape(x)+"</li>" for x in xs)
        links=[]
        for rel in row["accepted_model_relations_unverified"]:
            links.append("形貌："+escape(str(rel["morphology_original"] or "无"))
                         +"；传统断语："+escape(str(rel["historical_claim_original"] or "无"))
                         +"；关系："+escape(rel["traditional_relation_type"])
                         +"；分类："+escape(",".join(rel["historical_claim_domains"])))
        blocks.append(
            "<section><h2>"+escape(row["candidate_id"])+"</h2>"
            +"<p>原书PDF第"+str(page+1)+"页；OCR第"+str(row["ocr_line_index_zero_based"]+1)+"行</p>"
            +"<div class='grid'><img alt='原书扫描图' src='"+image+"'><div>"
            +"<h3>上文（OCR输出顺序，非可靠古籍阅读顺序）</h3><ol>"+make(row["preceding_OCR_lines_unreviewed"])+"</ol>"
            +"<h3>目标OCR行（未经原图校勘）</h3><strong>"+escape(row["exact_target_OCR_line_unreviewed"])+"</strong>"
            +"<h3>下文（OCR输出顺序）</h3><ol>"+make(row["following_OCR_lines_unreviewed"])+"</ol>"
            +"<h3>模型候选（未校勘）</h3><ul>"+make(links)+"</ul>"
            +"<h3>优先复核信号</h3><ul>"+make(row["lexical_risk_flags_NOT_probabilities"])+"</ul>"
            +"<p>人工核对优先级："+escape(row["manual_review_priority"])+"。"
            +"不允许凭同行词汇或OCR上下文推断因果或正式断语。</p></div></div></section>")
    return ("""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline'">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Faceface 原书OCR上下文核验</title><style>
body{font:15px/1.6 system-ui,sans-serif;max-width:1350px;margin:0 auto;padding:20px;background:#f8f6f0;color:#252525}
.grid{display:grid;grid-template-columns:minmax(260px,1fr) minmax(300px,1fr);gap:16px}
img{max-width:100%;border:1px solid #aaa}section{border-top:1px solid #aaa;padding:18px 0}
ol,ul{background:#fff;padding:15px 15px 15px 32px;overflow-wrap:anywhere}
strong{display:block;padding:12px;background:#fff4d1;overflow-wrap:anywhere}
@media(max-width:760px){.grid{grid-template-columns:1fr}}
</style></head><body><h1>Faceface 原书页图、OCR上下文及模型候选复核</h1>
<p><strong>所有OCR内容与模型解释均未经原书人工校勘；OCR行顺序可能不符合竖排古籍阅读顺序。</strong></p>
<p>待人工核对OCR片段数："""+str(summary["candidate_count"])+"""。新增正式规则：0。</p>
"""+"".join(blocks)+"</body></html>")


def write_private_context(selected:Path, model:Path, ocr_root:Path,
                          pack_dir:Path, destination:Path, radius:int=2)->dict:
    out=destination.resolve()
    if out.exists():
        raise ValueError("Private quality workpack already exists; never overwrite reviewer work")
    selected,model,ocr_root,pack_dir=map(lambda x:x.resolve(),
                                        (selected,model,ocr_root,pack_dir))
    if out.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("No private OCR text inside public repository")
    rows,stats=audit_context(selected,model,ocr_root,radius)
    for source,page in {(x["source_id"],x["pdf_page_zero_based"]) for x in rows}:
        img=pack_dir/"pages"/f"{source}-p{page:03d}.png"
        if not img.is_file() or img.stat().st_size<100:
            raise ValueError("Missing original PDF page PNG from M16.25 private workpack")
    # Preserve original model and OCR evidence via separate immutable sidecar.
    atomic_write(out/"private-OCR-context-quality.json",
                 (json.dumps(rows,ensure_ascii=False,indent=2)+"\n").encode())
    atomic_write(out/"index.html",html_report(rows,stats).encode())
    for source,page in {(x["source_id"],x["pdf_page_zero_based"]) for x in rows}:
        name=f"{source}-p{page:03d}.png"
        image=(pack_dir/"pages"/name).read_bytes()
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Original scan page is not a valid PNG")
        atomic_write(out/"pages"/name,image)
    atomic_write(out/"quality-summary-metadata-only.json",
                 (json.dumps(stats,ensure_ascii=False,indent=2)+"\n").encode())
    print(json.dumps(stats,ensure_ascii=False))
    return stats


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selected",type=Path,required=True)
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--ocr-root",type=Path,required=True)
    p.add_argument("--review-pack",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--radius",type=int,default=2)
    a=p.parse_args()
    write_private_context(a.selected,a.model,a.ocr_root,a.review_pack,a.out_dir,a.radius)


if __name__=="__main__":
    main()
