#!/usr/bin/env python3
"""M16.9: mine page-bound classical facial MORPHOLOGY PHRASE CANDIDATES.

No LLM calls. Works on the *actual* 1925 original-PDF-source-hashed PP-OCRv5
candidate lines, including all 268 pages in six CI shards. An occurrence of a
facial keyword does NOT establish a meaningful ancient rule. This is a cheap
lexical shortlist for original-image inspection, not Cangjie distillation.

PRIVATE: output candidate-shortlist.jsonl contains short UNVERIFIED OCR
fragments. NEVER upload it to public GitHub Actions artifacts. CI may upload
only aggregate counts, page IDs, SHA256 and region labels.
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
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write, file_sha256

MINE_VERSION = "M16.9_original_OCR_source_phrase_mine_v1"
HAN_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")

# Strong anchors are at least 2 characters; single characters are allowed
# ONLY when there is a morphology descriptor close to that character.
REGIONS = {
    "eye": {
        "strong": ("眼尾", "眼角", "眼珠", "眼形", "眼神", "雙眼", "雙目",
                   "三白", "四白", "魚尾", "監察官", "目光", "目形", "目清"),
        "weak": ("眼", "目", "眸"),
    },
    "nose": {
        "strong": ("鼻梁", "鼻樑", "鼻根", "鼻孔", "鼻頭", "鼻尖", "山根",
                   "準頭", "蘭臺", "廷尉", "年壽", "審辨官", "鼻形"),
        "weak": ("鼻",),
    },
    "mouth": {
        "strong": ("口形", "口角", "唇厚", "唇薄", "厚唇", "薄唇",
                   "嘴角", "口唇", "出納官", "人中", "口大", "口小"),
        "weak": ("口", "唇", "嘴"),
    },
    "ear": {
        "strong": ("耳輪", "耳廓", "耳珠", "耳垂", "垂珠", "采聽官",
                   "耳門", "耳形", "耳厚"),
        "weak": ("耳",),
    },
    "brow": {
        "strong": ("眉尾", "眉頭", "眉梢", "眉形", "眉毛", "眉骨",
                   "雙眉", "保壽官", "眉濃", "眉清"),
        "weak": ("眉",),
    },
    "face_structure": {
        "strong": ("面形", "面型", "臉形", "臉型", "面圓", "面方",
                   "額角", "額頭", "額骨", "顴骨", "頰骨", "腮骨",
                   "下頷", "下顎", "地閣", "天庭", "印堂", "三停",
                   "五嶽", "骨相", "面骨", "兩頰", "下停"),
        "weak": ("額", "顴", "頰", "腮", "頦", "臉", "面"),
    },
}
DESCRIPTORS = frozenset("長短方圓闊寬窄直曲細粗濃淡薄厚高低突陷露藏垂平尖大小齊清秀峻深淺黑白紅黃青潤枯端正斜上翹下陷削凸凹須")
WEAK_FALSE_NEIGHBORS = {"目的", "目錄", "項目", "目前", "門口", "入口", "出口", "人口",
                        "口述", "口傳", "表面", "方面", "前面", "後面", "面前"}
ALL_REGIONS = tuple(REGIONS)


def han_only(text: str) -> str:
    return "".join(HAN_RE.findall(text))


def weak_match(text: str, index: int, token: str) -> bool:
    if len(text) < 4:
        return False
    # Reject common non-physical words that happen to contain a face character.
    if any(text[max(0,index-2):min(len(text), index+len(token)+2)].find(word)>=0
           for word in WEAK_FALSE_NEIGHBORS if token in word):
        return False
    near = text[max(0,index-5):min(len(text),index+len(token)+6)]
    return any(char in DESCRIPTORS for char in near)


def candidates_for_line(line: str, line_index: int,
                        source_id: str, index: int, pdf_hash: str,
                        ocr_hash: str) -> list[dict]:
    normalized = han_only(line)
    if len(normalized)<3:
        return []
    tokens_by_region={}
    occurrence_positions=[]
    evidence_classes={}
    for region,terms in REGIONS.items():
        found=[]
        for term in terms["strong"]:
            pos=normalized.find(term)
            if pos>=0:
                found.append(term)
                occurrence_positions.append(pos)
                evidence_classes[region]="strong_multicharacter_anchor"
        for term in terms["weak"]:
            for match in re.finditer(re.escape(term),normalized):
                if weak_match(normalized,match.start(),term):
                    if term not in found:
                        found.append(term)
                    occurrence_positions.append(match.start())
                    evidence_classes.setdefault(region,"weak_with_nearby_descriptor")
        if found:
            tokens_by_region[region]=found
    if not tokens_by_region:
        return []
    # A short context window, NEVER a complete page. Single OCR line only.
    low=max(0,min(occurrence_positions)-8)
    high=min(len(normalized),max(occurrence_positions)+18)
    snippet=normalized[low:high]
    if len(snippet)>44:
        snippet=snippet[:44]
    if len(snippet)<3:
        return []
    raw_line_sha=hashlib.sha256(line.encode("utf-8")).hexdigest()
    quote_sha=hashlib.sha256(snippet.encode("utf-8")).hexdigest()
    candidate_id=hashlib.sha256(
        f"{source_id}:p{index:03d}|{ocr_hash}|{line_index}|{quote_sha}".encode("utf-8")
    ).hexdigest()[:20]
    signal_points=sum(3 if evidence_classes[r]=="strong_multicharacter_anchor" else 1
                      for r in tokens_by_region)
    risk_flags=["OCR_UNREVIEWED", "READING_ORDER_NOT_VERIFIED"]
    if any(v=="weak_with_nearby_descriptor" for v in evidence_classes.values()):
        risk_flags.append("WEAK_SINGLE_CHARACTER_MORPHOLOGY_CUE")
    if len(normalized)>65:
        risk_flags.append("LONG_OR_POSSIBLY_MERGED_OCR_LINE")
    if len(normalized)<=8:
        risk_flags.append("POSSIBLE_FIGURE_LABEL_OR_SHORT_HEADING")
    if len(tokens_by_region)>1:
        risk_flags.append("MULTIPLE_FACIAL_REGIONS_ONE_OCR_LINE")
    return [{
        "candidate_id":candidate_id,
        "page_id":f"{source_id}:p{index:03d}",
        "source_id":source_id,
        "pdf_page_zero_based":index,
        "original_pdf_sha256":pdf_hash,
        "ocr_candidate_sha256":ocr_hash,
        "ocr_line_index_zero_based":line_index,
        "raw_OCR_line_sha256":raw_line_sha,
        "snippet_sha256":quote_sha,
        "OCR_short_fragment_UNVERIFIED":snippet,
        "matched_regions":sorted(tokens_by_region),
        "matched_anchor_terms_UNVERIFIED":tokens_by_region,
        "lexical_signal_by_region":evidence_classes,
        "heuristic_review_priority_not_accuracy":signal_points,
        "risk_flags":risk_flags,
        "is_a_substantial_book_rule":False,
        "original_image_reviewed":False,
        "cangjie_semantic_agent_executed":False,
        "auto_activated_faceface_rule":False,
    }]


def mine_page(text: str, source_id: str, index: int,
              pdf_sha: str, ocr_sha: str) -> list[dict]:
    shortlist=[]
    seen_quotes=set()
    for i,line in enumerate(text.splitlines()):
        for item in candidates_for_line(line,i,source_id,index,pdf_sha,ocr_sha):
            dedup=(item["snippet_sha256"],tuple(item["matched_regions"]))
            if dedup in seen_quotes:
                continue
            seen_quotes.add(dedup)
            shortlist.append(item)
    return shortlist


def mine_shard(scan_dir: Path, ocr_dir: Path, out_dir: Path,
               sid: str, first: int, last: int,
               expected_hash_override: str | None = None) -> dict:
    source=next((s for s in SCANS if s["id"]==sid),None)
    if source is None:
        raise ValueError("Unknown original scan")
    scan_path=scan_dir/source["file"]
    if pdf_pages(scan_path)!=source["expected_pages"]:
        raise ValueError("Wrong original PDF page count")
    pdf_hash=file_sha256(scan_path)
    if pdf_hash != (expected_hash_override or KNOWN_SCAN_SHA256[sid]):
        raise ValueError("Original PDF SHA256 mismatch")
    if not 0<=first<=last<source["expected_pages"]:
        raise ValueError("Requested PDF page range invalid")
    private_rows=[]
    pages=[]
    total_han=0
    for index in range(first,last+1):
        stem=ocr_dir/"transcripts"/sid/f"{index:03d}"
        text_path=stem.with_suffix(".txt")
        meta_path=stem.with_suffix(".ocr.json")
        if not meta_path.is_file():
            raise ValueError(f"Missing OCR provenance for {sid}:p{index:03d}")
        meta=json.loads(meta_path.read_text(encoding="utf-8"))
        if (meta.get("source_id") != sid
            or meta.get("page_id") != f"{sid}:p{index:03d}"
            or type(meta.get("pdf_page_zero_based")) is not int
            or meta["pdf_page_zero_based"]!=index
            or meta.get("source_pdf_sha256")!=pdf_hash
            or meta.get("ocr_version")!=OCR_ID
            or meta.get("engine")!=ENGINE
            or meta.get("requires_manual_page_review") is not True
            or meta.get("eligible_for_cangjie_verified_corpus") is not False):
            raise ValueError(f"Invalid or altered OCR source for {sid}:p{index:03d}")
        status=meta.get("state")
        if status not in ("ocr_candidate","empty_ocr_candidate"):
            raise ValueError("Unknown OCR status")
        if status=="ocr_candidate":
            if not text_path.is_file() or meta.get("candidate_text_sha256")!=file_sha256(text_path):
                raise ValueError(f"OCR text tampering or stale metadata {sid}:p{index:03d}")
            text=text_path.read_text(encoding="utf-8")
            if len(han_only(text))!=meta.get("han_char_count"):
                raise ValueError(f"OCR candidate Han count mismatch: {sid}:p{index:03d}")
        else:
            if text_path.exists() or meta.get("candidate_text_sha256") is not None:
                raise ValueError("Stale candidate for empty OCR page")
            text=""
        total_han+=len(han_only(text))
        shortlist=mine_page(text,sid,index,pdf_hash,
                            meta.get("candidate_text_sha256") or "")
        private_rows.extend(shortlist)
        region_hits=sorted({region for hit in shortlist for region in hit["matched_regions"]})
        pages.append({
            "page_id":f"{sid}:p{index:03d}",
            "source_id":sid,
            "pdf_page_zero_based":index,
            "original_pdf_sha256":pdf_hash,
            "OCR_text_sha256":meta.get("candidate_text_sha256"),
            "OCR_han_count":meta["han_char_count"],
            "OCR_state":status,
            "morphology_short_fragment_hits":len(shortlist),
            "region_labels":region_hits,
            "candidate_id_hashes":[x["candidate_id"] for x in shortlist],
            "lexical_match_only_not_verified_rule":True,
        })
    private_base=out_dir/"private"/sid/f"p{first:03d}-{last:03d}"
    private_file=private_base.with_suffix(".jsonl")
    atomic_write(private_file,
                 ("\n".join(json.dumps(x,ensure_ascii=False) for x in private_rows)
                  + ("\n" if private_rows else "")).encode("utf-8"))
    count_by_region=Counter(r for item in private_rows for r in item["matched_regions"])
    pages_by_region=Counter(r for page in pages for r in page["region_labels"])
    summary={
        "kind":"M16.9_REAL_ORIGINAL_SCAN_OCR_LEXICAL_PRESELECTION",
        "version":MINE_VERSION,
        "source_id":sid,"source_pdf_sha256":pdf_hash,
        "first_pdf_page_zero_based":first,"last_pdf_page_zero_based":last,
        "original_pages_scanned":len(pages),
        "candidate_OCR_han_chars":total_han,
        "short_fragment_lexical_hits":len(private_rows),
        "pages_with_at_least_one_lexical_hit":sum(p["morphology_short_fragment_hits"]>0 for p in pages),
        "lexical_hit_count_by_region":{k:count_by_region[k] for k in ALL_REGIONS},
        "page_count_with_hit_by_region":{k:pages_by_region[k] for k in ALL_REGIONS},
        "pages":pages,
        "human_reviewed_original_pages":0,
        "real_Cangjie_AI_extractor_calls":0,
        "new_live_faceface_rules":0,
        "original_text_in_this_metadata":False,
        "notice":"Keyword/descriptor hits in UNREVIEWED OCR only. Not facial rules or scan-verified quotes."
    }
    meta_file=out_dir/"metadata"/f"{sid}-p{first:03d}-{last:03d}.json"
    atomic_write(meta_file,(json.dumps(summary,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({k:v for k,v in summary.items() if k!="pages"},ensure_ascii=False),
          flush=True)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan-dir",type=Path,required=True)
    p.add_argument("--ocr-dir",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--source",choices=[s["id"] for s in SCANS],required=True)
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--end",type=int,required=True)
    a=p.parse_args()
    mine_shard(a.scan_dir,a.ocr_dir,a.out_dir,a.source,a.start,a.end)


if __name__=="__main__":
    main()
