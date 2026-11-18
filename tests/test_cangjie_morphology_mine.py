"""M16.9: prove source-bound morphology preselection is not fake source evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.cangjie_morphology_mine import (
    ALL_REGIONS, ENGINE, OCR_ID, candidates_for_line, mine_page, mine_shard
)
from scripts.cangjie_morphology_audit import aggregate
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256


PDF_HASH = "a" * 64
OCR_HASH = "b" * 64


class MorphoMiningTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)
        self.scans=self.root/"scans"
        self.scans.mkdir()
        self.pdf=self.scans/"part1.pdf"
        self.pdf.write_bytes(b"%PDF synthetic (not source original)")
        self.sha=hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.ocr=self.root/"ocr"
        self.out=self.root/"out"

    def put_candidate(self,index,text):
        stem=self.ocr/"transcripts"/"nlc-44091"/f"{index:03d}"
        stem.parent.mkdir(parents=True,exist_ok=True)
        txt=stem.with_suffix(".txt")
        txt.write_text(text,encoding="utf-8")
        meta={
            "source_id":"nlc-44091","page_id":f"nlc-44091:p{index:03d}",
            "pdf_page_zero_based":index,
            "source_pdf_sha256":self.sha,
            "ocr_version":OCR_ID,"engine":ENGINE,
            "requires_manual_page_review":True,
            "eligible_for_cangjie_verified_corpus":False,
            "state":"ocr_candidate",
            "candidate_text_sha256":hashlib.sha256(txt.read_bytes()).hexdigest(),
            "han_char_count":sum("\u3400"<=x<="\u9fff" for x in text)
        }
        stem.with_suffix(".ocr.json").write_text(
            json.dumps(meta,ensure_ascii=False),encoding="utf-8"
        )
        return txt,stem.with_suffix(".ocr.json")

    def test_multi_region_and_single_character_descriptor_hits(self):
        lines=[
            "口須方大",
            "眉尾上翹",
            "鼻梁端直",
            "眼尾細長",
            "耳輪厚",
            "天庭飽滿",
        ]
        observed=set()
        for text in lines:
            hits=candidates_for_line(text,0,"nlc-44091",27,PDF_HASH,OCR_HASH)
            self.assertEqual(len(hits),1,text)
            self.assertFalse(hits[0]["original_image_reviewed"])
            self.assertFalse(hits[0]["is_a_substantial_book_rule"])
            self.assertFalse(hits[0]["cangjie_semantic_agent_executed"])
            self.assertFalse(hits[0]["auto_activated_faceface_rule"])
            observed.update(hits[0]["matched_regions"])
        self.assertEqual(observed,set(ALL_REGIONS))

    def test_generic_or_single_character_without_shape_is_not_morphology(self):
        for line in ["人口出入口", "目的目前項目", "我去前面", "口", "眼",
                     "鼻", "耳", "眉", "山川河流"]:
            with self.subTest(line=line):
                self.assertEqual(candidates_for_line(
                    line,0,"nlc-44091",27,PDF_HASH,OCR_HASH
                ),[])
        self.assertEqual(mine_page("或細長\n數字三", "nlc-44091",27,PDF_HASH,OCR_HASH),[])

    def test_repeated_page_lines_are_deduplicated_but_coverage_is_per_region(self):
        hits=mine_page("眼尾細長\n眼尾細長\n口須方大\n","nlc-44091",27,PDF_HASH,OCR_HASH)
        self.assertEqual(len(hits),2)
        self.assertNotEqual(hits[0]["candidate_id"],hits[1]["candidate_id"])
        self.assertTrue(all(h["source_id"]=="nlc-44091" and
                            h["original_pdf_sha256"]==PDF_HASH for h in hits))
        self.assertTrue(all(h["OCR_short_fragment_UNVERIFIED"] for h in hits))

    def test_real_candidate_metadata_contract_and_private_vs_public(self):
        self.put_candidate(27,"口須方大\n眼尾細長\n")
        self.put_candidate(28,"人口出口\n")
        with patch("scripts.cangjie_morphology_mine.pdf_pages",return_value=153):
            stats=mine_shard(self.scans,self.ocr,self.out,"nlc-44091",27,28,
                             expected_hash_override=self.sha)
        self.assertEqual(stats["original_pages_scanned"],2)
        self.assertEqual(stats["pages_with_at_least_one_lexical_hit"],1)
        self.assertGreaterEqual(stats["short_fragment_lexical_hits"],2)
        self.assertEqual(stats["human_reviewed_original_pages"],0)
        self.assertEqual(stats["new_live_faceface_rules"],0)
        private=(self.out/"private"/"nlc-44091"/"p027-028.jsonl").read_text("utf-8")
        public=(self.out/"metadata"/"nlc-44091-p027-028.json").read_text("utf-8")
        self.assertIn("口須方大",private)
        self.assertNotIn("口須方大",public)
        self.assertNotIn("眼尾細長",public)
        self.assertEqual(json.loads(public)["pages"][0]["page_id"],"nlc-44091:p027")
        self.assertEqual(len(stats["pages"][0]["OCR_text_sha256"]),64)

    def test_changed_candidate_text_is_detected_instead_of_mined(self):
        txt,_=self.put_candidate(27,"口須方大\n")
        txt.write_text("鼻梁端直\n",encoding="utf-8")
        with patch("scripts.cangjie_morphology_mine.pdf_pages",return_value=153):
            with self.assertRaisesRegex(ValueError,"tampering"):
                mine_shard(self.scans,self.ocr,self.out,"nlc-44091",27,27,
                           expected_hash_override=self.sha)
        self.assertFalse((self.out/"metadata"/"nlc-44091-p027-027.json").exists())

    def test_wrong_source_hash_refused(self):
        self.put_candidate(27,"口須方大\n")
        with patch("scripts.cangjie_morphology_mine.pdf_pages",return_value=153):
            with self.assertRaisesRegex(ValueError,"SHA256"):
                mine_shard(self.scans,self.ocr,self.out,"nlc-44091",27,27)


class MorphoAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def reports(self):
        regions=tuple(ALL_REGIONS)
        paths=[]
        for sid,count in (("nlc-44091",153),("nlc-44092",115)):
            pages=[]
            for i in range(count):
                positive=i==27
                pages.append({
                    "page_id":f"{sid}:p{i:03d}","source_id":sid,
                    "pdf_page_zero_based":i,
                    "original_pdf_sha256":KNOWN_SCAN_SHA256[sid],
                    "OCR_state":"ocr_candidate",
                    "OCR_han_count":200,
                    "OCR_text_sha256":"f"*64,
                    "morphology_short_fragment_hits":1 if positive else 0,
                    "region_labels":["mouth"] if positive else [],
                    "candidate_id_hashes":["a"*20] if positive else [],
                    "lexical_match_only_not_verified_rule":True
                })
            data={
                "kind":"M16.9_REAL_ORIGINAL_SCAN_OCR_LEXICAL_PRESELECTION",
                "version":"M16.9_original_OCR_source_phrase_mine_v1",
                "source_id":sid,
                "source_pdf_sha256":KNOWN_SCAN_SHA256[sid],
                "first_pdf_page_zero_based":0,"last_pdf_page_zero_based":count-1,
                "original_pages_scanned":count,
                "candidate_OCR_han_chars":count*200,
                "short_fragment_lexical_hits":1,
                "pages_with_at_least_one_lexical_hit":1,
                "lexical_hit_count_by_region":{r:1 if r=="mouth" else 0 for r in regions},
                "page_count_with_hit_by_region":{r:1 if r=="mouth" else 0 for r in regions},
                "human_reviewed_original_pages":0,
                "real_Cangjie_AI_extractor_calls":0,
                "new_live_faceface_rules":0,
                "original_text_in_this_metadata":False,
                "pages":pages
            }
            path=self.root/f"{sid}.json"
            path.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
            paths.append(path)
        return paths

    def test_exact_268_lexical_count_and_per_source_totals(self):
        report=aggregate(self.reports())
        self.assertEqual(report["actual_1925_original_pages_processed"],268)
        self.assertEqual(report["pages_with_any_lexical_morphology_cue"],2)
        self.assertEqual(report["short_fragment_lexical_hits_total"],2)
        self.assertEqual(report["distinct_pages_by_facial_region"]["mouth"],2)
        self.assertEqual(report["new_live_faceface_rules"],0)
        self.assertFalse(report["official_Cangjie_semantic_AI_extraction_executed"])

    def test_missing_page_fails_closed(self):
        paths=self.reports()
        data=json.loads(paths[0].read_text("utf-8"))
        data["pages"].pop()
        data["original_pages_scanned"]-=1
        data["last_pdf_page_zero_based"]-=1
        data["candidate_OCR_han_chars"]-=200
        paths[0].write_text(json.dumps(data),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Not complete 268"):
            aggregate(paths)

    def test_forged_verified_status_not_accepted(self):
        paths=self.reports()
        data=json.loads(paths[0].read_text("utf-8"))
        data["human_reviewed_original_pages"]=153
        paths[0].write_text(json.dumps(data),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"source provenance"):
            aggregate(paths)


if __name__=="__main__":
    unittest.main()
