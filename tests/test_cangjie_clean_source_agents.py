"""M16.13 clean-source actual pinned Cangjie prompt + strict quote-ID gate."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch

from scripts.cangjie_clean_source_agents import (
    ADLER_FORMAT,ROLE_FORMAT,MODEL,ROLE_FILES,
    SOURCE_REVIEW_LABEL, OllamaClient,source_short_catalog,
    official_role_texts,accept_role_candidates,run_agents,
)
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256
from scripts.cangjie_working_corpus import PINNED_CANGJIE_COMMIT


class FixedSources:
    def __init__(self):
        self.sources={
            "nlc-44091":{"pdf_sha256":KNOWN_SCAN_SHA256["nlc-44091"]},
            "nlc-44092":{"pdf_sha256":KNOWN_SCAN_SHA256["nlc-44092"]},
        }
    def page_paths(self,source,index):
        if source!="nlc-44091" or type(index) is not int or not 0<=index<153:
            raise ValueError("Unexpected original source page")
        return {}


class TestModel:
    model=MODEL
    def __init__(self):
        self.requests=[]
    def installed(self):
        return {"model":self.model,"model_digest":"test-simulated-LOCAL-MOCK"}
    def infer(self,system,user,schema):
        self.requests.append((system,user,schema))
        if schema==ADLER_FORMAT:
            return {"hypothesis":"十三则短句只能说明局部历史术语",
                    "terms":["口形","三停"],
                    "limitations":["不是整书","历史描述不等于现实人格"]}
        if "framework" in system or "case" in system or "counter_example" in system:
            return {"candidates":[]}
        return {"candidates":[{
            "quote_id":1,"title":"口部历史形状描述",
            "interpreted_morphology_or_historical_concept":"历史上提及口宽，不是现代人格预测",
            "photo_observability":"partial_photo_observable",
            "interference_or_limit":"表情和镜头"}]}


class CleanShortSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads(Path(
            "src/knowledge/maiyi-source-checked-v5.json"
        ).read_text(encoding="utf-8"))
        cls.workspace=FixedSources()

    def test_13_short_existing_legacy_sources_with_pdf_SHA_and_exact_quote(self):
        entries=source_short_catalog(self.source,self.workspace)
        self.assertEqual(len(entries),13)
        self.assertEqual(sum(x["legacy_entry_kind"]=="card" for x in entries),10)
        self.assertEqual(sum(x["legacy_entry_kind"]=="framework_note" for x in entries),3)
        self.assertEqual(len(set(x["id"] for x in entries)),13)
        self.assertEqual(entries[1]["source_excerpt"],"口須方大")
        self.assertTrue(all(x["source_provenance_quality"]==SOURCE_REVIEW_LABEL
                            for x in entries))
        self.assertTrue(all(x["source_excerpt_newly_human_reviewed"] is False
                            and x["this_experiment_may_add_live_rule"] is False
                            for x in entries))

    def test_reject_wrong_pdf_or_unsafe_ancient_fate_policy(self):
        invalid=copy.deepcopy(self.source)
        invalid["policy"]["no_personality_health_fate_from_appearance"]=False
        with self.assertRaisesRegex(ValueError,"Unsafe"):
            source_short_catalog(invalid,self.workspace)
        invalid=copy.deepcopy(self.source)
        invalid["cards"][0]["source"]["pdf_page_zero_based"]=300
        with self.assertRaisesRegex(ValueError,"Unexpected"):
            source_short_catalog(invalid,self.workspace)
        invalid=copy.deepcopy(self.source)
        invalid["cards"][0]["source"]["source_url"]="https://example.org/fake.pdf"
        with self.assertRaisesRegex(ValueError,"Unexpected original PDF"):
            source_short_catalog(invalid,self.workspace)

    def test_actual_pinned_official_prompts_not_faked(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"extractors").mkdir()
            (root/"methodology").mkdir()
            (root/"SKILL.md").write_text("Official repository skill",encoding="utf-8")
            (root/"methodology"/"01-stage0-adler.md").write_text(
                "ADLER 官方原提示文字 "*70,encoding="utf-8"
            )
            for name in ROLE_FILES.values():
                (root/"extractors"/name).write_text(
                    "Official Cangjie actual extractor "*40,encoding="utf-8"
                )
            with patch("scripts.cangjie_clean_source_agents.subprocess.run",
                       return_value=MagicMock(stdout=PINNED_CANGJIE_COMMIT+"\n")):
                m,p=official_role_texts(root)
            self.assertEqual(set(p),{"adler",*ROLE_FILES})
            self.assertEqual(m["pinned_original_cangjie_commit"],PINNED_CANGJIE_COMMIT)
            self.assertEqual(len(m["official_upstream_files_sha256"]),7)
            with patch("scripts.cangjie_clean_source_agents.subprocess.run",
                       return_value=MagicMock(stdout="not-pinned\n")):
                with self.assertRaisesRegex(ValueError,"Unexpected official"):
                    official_role_texts(root)

    def test_real_model_quote_ID_must_map_to_existing_original_source_record(self):
        sources=source_short_catalog(self.source,self.workspace)
        row={
            "quote_id":1,"title":"口形",
            "interpreted_morphology_or_historical_concept":"古代形态词",
            "photo_observability":"partial_photo_observable",
            "interference_or_limit":"拍照表情"
        }
        approved,rejected=accept_role_candidates(
            {"candidates":[row]},"principle",sources
        )
        self.assertEqual(len(approved),1)
        self.assertFalse(rejected)
        self.assertEqual(approved[0]["source_quote_restored_from_prior_source_catalog"],"口須方大")
        self.assertEqual(approved[0]["original_pdf_sha256"],
                         KNOWN_SCAN_SHA256["nlc-44091"])
        self.assertFalse(approved[0]["auto_publish_to_Faceface"])
        self.assertTrue(approved[0]["not_independently_human_roi_checked"])
        row["quote_id"]=13
        approved,rejected=accept_role_candidates(
            {"candidates":[row]},"principle",sources
        )
        self.assertEqual(approved,[])
        self.assertEqual(rejected,["unknown_original_quote_ID"])
        row["quote_id"]="1"
        self.assertEqual(accept_role_candidates(
            {"candidates":[row]},"principle",sources
        )[1],["unknown_original_quote_ID"])

    def test_role_case_does_not_treat_pure_ancient_framework_as_a_case(self):
        sources=source_short_catalog(self.source,self.workspace)
        row={
            "quote_id":11,"title":"历史框架",
            "interpreted_morphology_or_historical_concept":"以水系喻五官",
            "photo_observability":"historical_framework_only",
            "interference_or_limit":"无人体事件案例"
        }
        accepted,errors=accept_role_candidates(
            {"candidates":[row]},"case",sources
        )
        self.assertEqual(accepted,[])
        self.assertEqual(errors,["historic_framework_note_not_a_case"])

    def test_five_independent_model_calls_only_clean_source_and_never_publish(self):
        sources=source_short_catalog(self.source,self.workspace)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            model=TestModel()
            with patch("scripts.cangjie_clean_source_agents.official_role_texts",
                       return_value=(
                           {"pinned_original_cangjie_commit":PINNED_CANGJIE_COMMIT,
                            "official_upstream_files_sha256":{"test":"a"*64}},
                           {"adler":"official Adler "*120,
                            **{r:"official "+r*100 for r in ROLE_FILES}}
                       )):
                public=root/"public.json"
                report=run_agents(
                    self.workspace,self.source,root/"pinned-official",
                    model,root/"private",public
                )
            self.assertEqual(len(model.requests),6)
            self.assertEqual(report["independent_real_extractor_role_calls_completed"],5)
            self.assertTrue(report["real_Adler_sample_model_completed"])
            self.assertEqual(report["total_LLM_candidate_concepts_source_quote_id_bound"],2)
            self.assertEqual(report["new_live_Faceface_rules"],0)
            self.assertEqual(report["actual_independently_human_signed_new_short_ROIs"],0)
            self.assertTrue(report["never_claimed_whole_book_agents_complete"])
            public_text=public.read_text(encoding="utf-8")
            self.assertNotIn("口須方大",public_text)
            self.assertNotIn("历史上提及口宽",public_text)
            self.assertIn("mouth",str(sources[1]["id"]).lower()) # source mapping
            private=(root/"private"/"five-roles-CLEAN-V5-CANDIDATES-not-reviewed.json")
            self.assertIn("口須方大",private.read_text("utf-8"))
            # Each role has only fixed source texts, never previous role's LLM answer.
            for system,user,schema in model.requests[1:]:
                self.assertIn("口須方大",user)
                self.assertNotIn("历史上提及口宽",user)

    def test_local_model_url_gated(self):
        for url in ("https://remote.ai:11434",
                    "http://example.com:11434",
                    "http://127.0.0.1:11434/path"):
            with self.subTest(url=url),self.assertRaisesRegex(ValueError,"loopback"):
                OllamaClient(url)


if __name__=="__main__":
    unittest.main()
