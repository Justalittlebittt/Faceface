"""M16.17: exact ancient phrase evidence gate and real-model client orchestration."""
import hashlib
import unittest

from scripts.cangjie_real_historical_relations import (
    RELATION_FORMAT, translate_model_relations, run_relation_agents
)
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256


class FakeModel:
    def __init__(self, replies):
        self.replies = replies
        self.calls = []
    def infer(self, system, user, schema):
        self.calls.append((system, user, schema))
        return self.replies.pop(0)


class HistoricalRelationExtractionTests(unittest.TestCase):
    def setUp(self):
        self.source = [{
            "id": "synthetic-existing:1", "source_id": "nlc-44091",
            "pdf_page_zero_based": 27,
            "original_pdf_sha256": KNOWN_SCAN_SHA256["nlc-44091"],
            "source_excerpt": "鼻豐者富貴口端正"
        }]
        self.row = {
            "quote_id": 0, "morphology_span": "鼻豐",
            "claim_span": "富貴", "condition_span": "", "exception_span": "",
            "relation_type": "explicit_in_source", "claim_domain": "wealth"
        }

    def test_exact_spans_map_to_archive_only_relation(self):
        accepted, rejected = translate_model_relations(
            {"relations": [self.row]}, self.source)
        self.assertEqual(rejected, [])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["historical_claim_original"], "富貴")
        self.assertEqual(accepted[0]["historical_claim_domains"], ["wealth"])
        self.assertEqual(accepted[0]["transcription_review_status"], "source_unverified")
        self.assertFalse(accepted[0]["eligible_for_Faceface_live_rules"])

    def test_model_fabricated_wealth_or_longevity_rejected(self):
        self.row["claim_span"] = "長壽"
        accepted, rejected = translate_model_relations({"relations": [self.row]}, self.source)
        self.assertEqual(accepted, [])
        self.assertEqual(rejected[0]["reason"], "model_span_not_literal_original")

    def test_lifespan_phrase_must_not_be_labeled_moral_character(self):
        self.source[0]["source_excerpt"] = "鼻長有壽"
        self.row["morphology_span"] = "鼻長"
        self.row["claim_span"] = "有壽"
        self.row["claim_domain"] = "moral_character"
        accepted, rejected = translate_model_relations({"relations": [self.row]}, self.source)
        self.assertEqual(accepted, [])
        self.assertEqual(rejected[0]["reason"], "claim_domain_not_supported_by_literal_span")
        self.row["claim_domain"] = "longevity"
        accepted, rejected = translate_model_relations({"relations": [self.row]}, self.source)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(rejected, [])

    def test_classical_moral_claim_without_moral_words_is_rejected(self):
        self.row["claim_domain"] = "moral_character"
        accepted, rejected = translate_model_relations({"relations": [self.row]}, self.source)
        self.assertEqual(accepted, [])
        self.assertEqual(rejected[0]["reason"], "claim_domain_not_supported_by_literal_span")

    def test_only_shape_does_not_invent_outcome(self):
        self.row["claim_span"] = ""
        self.row["claim_domain"] = "none"
        self.row["relation_type"] = "not_linked"
        accepted, rejected = translate_model_relations({"relations": [self.row]}, self.source)
        self.assertEqual(rejected, [])
        self.assertIsNone(accepted[0]["historical_claim_original"])
        self.assertEqual(accepted[0]["historical_claim_domains"], ["none"])

    def test_explicit_link_requires_both_literal_sides(self):
        self.row["claim_span"] = ""
        self.row["claim_domain"] = "none"
        _, rejected = translate_model_relations({"relations": [self.row]}, self.source)
        self.assertEqual(rejected[0]["reason"], "explicit_link_requires_two_spans")

    def test_unknown_quote_and_cross_source_ids_are_rejected(self):
        self.row["quote_id"] = 1
        _, rejected = translate_model_relations({"relations": [self.row]}, self.source)
        self.assertEqual(rejected[0]["reason"], "unknown_quote_id")

    def test_model_client_actually_called_per_source_and_no_extra_quote(self):
        model = FakeModel([{"relations": [self.row]}])
        result = run_relation_agents(self.source, model, {"glossary": "G", "principle": "P"})
        self.assertEqual(result["real_requests_attempted"], 1)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(model.calls[0][2], RELATION_FORMAT)
        self.assertEqual(len(result["relations"]), 1)
        self.assertEqual(result["relations"][0]["source_passage_id"], self.source[0]["id"])

    def test_empty_model_output_is_not_a_fake_success(self):
        model = FakeModel([{"relations": []}])
        result = run_relation_agents(self.source, model, {"glossary": "G", "principle": "P"})
        self.assertEqual(result["relations"], [])
        self.assertEqual(result["real_requests_attempted"], 1)


if __name__ == "__main__":
    unittest.main()
