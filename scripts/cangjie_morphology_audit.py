#!/usr/bin/env python3
"""M16.9: independent six-shard exact 268-page audit of OCR lexical shortlists.

Reads metadata-only JSON files; original book OCR fragments must NOT be uploaded.
Totals report SEARCH HITS, not verified historical prescriptions or face traits.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts.cangjie_corpus_stage import SCANS
from scripts.cangjie_morphology_mine import ALL_REGIONS, MINE_VERSION
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256


def aggregate(paths: list[Path]) -> dict:
    if not paths:
        raise ValueError("No real OCR-mine shard evidence")
    seen={}
    shards={}
    for path in paths:
        data=json.loads(path.read_text(encoding="utf-8"))
        sid=data.get("source_id")
        src=next((x for x in SCANS if x["id"]==sid),None)
        if not src or data.get("kind")!="M16.9_REAL_ORIGINAL_SCAN_OCR_LEXICAL_PRESELECTION":
            raise ValueError("Unrecognized source / wrong M16.9 metadata kind")
        if (data.get("version")!=MINE_VERSION
            or data.get("source_pdf_sha256")!=KNOWN_SCAN_SHA256[sid]
            or data.get("human_reviewed_original_pages")!=0
            or data.get("real_Cangjie_AI_extractor_calls")!=0
            or data.get("new_live_faceface_rules")!=0
            or data.get("original_text_in_this_metadata") is not False):
            raise ValueError("M16.9 source provenance or unreviewed status mismatch")
        first,last=data.get("first_pdf_page_zero_based"),data.get("last_pdf_page_zero_based")
        if (type(first) is not int or type(last) is not int
            or not 0<=first<=last<src["expected_pages"]):
            raise ValueError("Bad shard page range")
        key=(sid,first,last)
        if key in shards:
            raise ValueError("Duplicate original page range")
        shards[key]=data
        if len(data.get("pages",[]))!=last-first+1 or \
           data.get("original_pages_scanned")!=last-first+1:
            raise ValueError("Shard must cover every page declared in range")
        for offset,p in enumerate(data["pages"]):
            index=first+offset
            pid=f"{sid}:p{index:03d}"
            if pid in seen or p.get("page_id")!=pid:
                raise ValueError(f"Duplicate, reordered or incorrect page {pid}")
            if (p.get("source_id")!=sid or p.get("pdf_page_zero_based")!=index
                or p.get("original_pdf_sha256")!=KNOWN_SCAN_SHA256[sid]
                or p.get("lexical_match_only_not_verified_rule") is not True):
                raise ValueError("Bad source hash/page/verification status")
            if p.get("OCR_state") not in ("ocr_candidate","empty_ocr_candidate"):
                raise ValueError("Bad OCR state")
            if not isinstance(p.get("OCR_han_count"),int) or p["OCR_han_count"]<0:
                raise ValueError("Invalid per-page Han count")
            count=p.get("morphology_short_fragment_hits")
            if type(count) is not int or count<0:
                raise ValueError("Invalid lexical hit count")
            identifiers=p.get("candidate_id_hashes")
            if (not isinstance(identifiers,list) or len(identifiers)!=count
                or len(identifiers)!=len(set(identifiers))
                or any(not isinstance(x,str) or len(x)!=20 for x in identifiers)):
                raise ValueError("Inconsistent shortlist hash counts")
            regions=p.get("region_labels")
            if not isinstance(regions,list) or len(regions)!=len(set(regions)) or \
               not set(regions).issubset(ALL_REGIONS):
                raise ValueError("Invalid region labels")
            if bool(regions)!=bool(count):
                raise ValueError("Hit count and region labels disagree")
            if p["OCR_state"]=="empty_ocr_candidate" and \
               (p["OCR_han_count"] or count or p.get("OCR_text_sha256") is not None):
                raise ValueError("Empty OCR page must not contain invented hits")
            if p["OCR_state"]=="ocr_candidate" and \
               (not p.get("OCR_text_sha256") or len(p["OCR_text_sha256"])!=64):
                raise ValueError("Nonempty OCR page must have a matching SHA256")
            seen[pid]=p

    expected={f"{s['id']}:p{i:03d}" for s in SCANS
              for i in range(s["expected_pages"])}
    missing=sorted(expected-set(seen))
    if missing or len(seen)!=268:
        raise ValueError(f"Not complete 268 pages: missing {missing[:12]}, got {len(seen)}")
    per_source={}
    region_hit_totals=Counter()
    region_page_totals=Counter()
    for sid in KNOWN_SCAN_SHA256:
        pages=[v for v in seen.values() if v["source_id"]==sid]
        byreg=Counter(r for p in pages for r in p["region_labels"])
        for reg,count in byreg.items():
            region_page_totals[reg]+=count
        per_source[sid]={
            "pages":len(pages),
            "pages_with_lexical_hit":sum(p["morphology_short_fragment_hits"]>0 for p in pages),
            "lexical_hit_count":sum(p["morphology_short_fragment_hits"] for p in pages),
            "OCR_han_characters":sum(p["OCR_han_count"] for p in pages),
            "page_count_with_hit_by_region":{r:byreg[r] for r in ALL_REGIONS},
        }
    for data in shards.values():
        for r in ALL_REGIONS:
            region_hit_totals[r]+=data["lexical_hit_count_by_region"][r]
        if sum(p["morphology_short_fragment_hits"] for p in data["pages"]) != data["short_fragment_lexical_hits"]:
            raise ValueError("Shard count invented or missing shortlists")
        if sum(p["OCR_han_count"] for p in data["pages"]) != data["candidate_OCR_han_chars"]:
            raise ValueError("Shard OCR Han character sum inconsistent")
        for r in ALL_REGIONS:
            n=sum(r in p["region_labels"] for p in data["pages"])
            if n!=data["page_count_with_hit_by_region"][r]:
                raise ValueError("Shard region-to-page counts inconsistent")
    ordered=sorted(seen.values(),key=lambda p:(p["source_id"],p["pdf_page_zero_based"]))
    ranked=sorted((p for p in ordered if p["morphology_short_fragment_hits"]>0),
                  key=lambda p:(-len(p["region_labels"]),
                                -p["morphology_short_fragment_hits"],
                                p["source_id"],p["pdf_page_zero_based"]))
    return {
        "kind":"M16.9_ACTUAL_WHOLE_BOOK_OCR_LEXICAL_MINING_COVERAGE",
        "actual_1925_original_pages_processed":len(seen),
        "source_pdf_sha256":dict(KNOWN_SCAN_SHA256),
        "metadata_only_shard_count":len(shards),
        "OCR_han_chars_total":sum(p["OCR_han_count"] for p in ordered),
        "pages_with_any_lexical_morphology_cue":len(ranked),
        "short_fragment_lexical_hits_total":sum(p["morphology_short_fragment_hits"] for p in ordered),
        "lexical_hits_by_facial_region":{r:region_hit_totals[r] for r in ALL_REGIONS},
        "distinct_pages_by_facial_region":{r:region_page_totals[r] for r in ALL_REGIONS},
        "per_scan":per_source,
        "top_original_page_ids_for_image_review":[{
            "page_id":p["page_id"],
            "lexical_hits":p["morphology_short_fragment_hits"],
            "facial_regions":p["region_labels"],
            "candidate_id_hashes":p["candidate_id_hashes"][:8],
        } for p in ranked[:25]],
        "zero_lexical_hit_pages":sum(p["morphology_short_fragment_hits"]==0 for p in ordered),
        "human_verified_original_page_transcriptions_added":0,
        "official_Cangjie_semantic_AI_extraction_executed":False,
        "new_live_faceface_rules":0,
        "original_OCR_text_or_quotes_in_metadata":False,
        "warning":"LEXICAL SEARCH SIGNALS in unverified OCR; no count here proves an actual usable book rule."
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports",nargs="+",type=Path)
    parser.add_argument("--out",required=True,type=Path)
    a=parser.parse_args()
    result=aggregate(a.reports)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="top_original_page_ids_for_image_review"},
                     ensure_ascii=False))


if __name__=="__main__":
    main()
