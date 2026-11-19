"""Strict short literal links are archived without inventing model interpretation."""
import json
from pathlib import Path
import unittest

from scripts.cangjie_literal_claim_fallback import scan_catalog


class LiteralClaimFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(Path("src/knowledge/maiyi-source-checked-v5.json").read_text(encoding="utf-8"))

    def test_actual_legacy_short_source_yields_longevity_archive_only(self):
        result = scan_catalog(self.catalog)
        self.assertEqual(result["stats"]["source_count"], 10)
        self.assertGreaterEqual(result["audit"]["historical_domain_membership_counts"]["longevity"], 1)
        self.assertTrue(any(
            r["source_passage_id"] == "MY25-NOSE-LONG-01"
            and r["morphology_original"] == "鼻長"
            and r["historical_claim_original"] == "有壽"
            and r["report_eligibility"] == "archive_only"
            and r["transcription_review_status"] == "source_unverified"
            and r["eligible_for_Faceface_live_rules"] is False
            for r in result["ledger"]["relations"]
        ))
        self.assertEqual(result["audit"]["runtime_rules_created"], 0)

    def test_does_not_invent_outcomes_on_shape_only_phrases(self):
        result = scan_catalog(self.catalog)
        source_ids = {r["source_passage_id"] for r in result["ledger"]["relations"]}
        self.assertNotIn("MY25-MOUTH-01", source_ids)
        self.assertNotIn("MY25-NOSE-01", source_ids)

    def test_contextual_claims_cannot_be_invented_from_legacy_commentary(self):
        result = scan_catalog(self.catalog)
        source_ids = {r["source_passage_id"] for r in result["ledger"]["relations"]}
        # The OX mouth card mentions auspicious livelihood in the modern
        # commentary, but its short quote only says 雙唇厚且豐.
        self.assertNotIn("MY25-MOUTH-OX-01", source_ids)

    def test_unknown_catalog_rejected(self):
        with self.assertRaisesRegex(ValueError, "Expected"):
            scan_catalog({"dataset": "invented", "cards": []})


if __name__ == "__main__":
    unittest.main()
