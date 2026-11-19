"""Historical source outcomes must be archived even if photo-unobservable."""
from __future__ import annotations
import hashlib
import unittest

from scripts.cangjie_historical_claim_ledger import validate_relations
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256


class HistoricalClaimsContract(unittest.TestCase):
    def setUp(self):
        self.quote = "synthetic sample passage, not a historical citation"
        self.record = {
            "relation_id": "synthetic:R01",
            "source_passage_id": "synthetic:P01",
            "edition_id": "1925-wenming-qin",
            "source_id": "nlc-44091",
            "source_pdf_sha256": KNOWN_SCAN_SHA256["nlc-44091"],
            "pdf_page_zero_based": 86,
            "quote_original": self.quote,
            "quote_sha256": hashlib.sha256(self.quote.encode()).hexdigest(),
            "transcription_review_status": "source_unverified",
            "morphology_original": "synthetic morphology",
            "historical_claim_original": "synthetic claimed fortune",
            "conditions_original": "",
            "exception_original": "",
            "context_original": "",
            "traditional_relation_type": "explicit_in_source",
            "historical_claim_domains": ["wealth", "fortune"],
            "photo_observability": "unavailable",
            "report_eligibility": "archive_only",
            "conflicting_sources": [],
            "modern_explanation": "",
            "eligible_for_Faceface_live_rules": False,
            "claims_real_person_outcome": False,
        }
        self.document = {"schema": "faceface-historical-claims-v1", "relations": [self.record]}

    def validate(self):
        return validate_relations(self.document)

    def test_unobservable_wealth_claim_is_preserved_in_archive(self):
        result = self.validate()
        self.assertEqual(result["relation_count"], 1)
        self.assertEqual(result["historical_domain_membership_counts"]["wealth"], 1)
        self.assertEqual(result["runtime_rules_created"], 0)

    def test_lifetime_and_character_can_be_preserved_as_archival_only(self):
        self.record["historical_claim_domains"] = ["longevity", "moral_character"]
        self.assertEqual(self.validate()["relation_count"], 1)

    def test_no_outcome_must_be_explicitly_marked_none(self):
        self.record["historical_claim_original"] = None
        self.record["traditional_relation_type"] = "not_linked"
        self.record["historical_claim_domains"] = ["none"]
        self.assertEqual(self.validate()["relation_count"], 1)

    def test_unverified_cannot_enter_report(self):
        self.record["report_eligibility"] = "research_candidate"
        with self.assertRaisesRegex(ValueError, "Unverified original"):
            self.validate()

    def test_no_live_rule_or_personal_verdict(self):
        for key in ("eligible_for_Faceface_live_rules", "claims_real_person_outcome"):
            self.record[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate()
            self.record[key] = False

    def test_tampering_and_unsupported_domains_fail(self):
        self.record["quote_original"] = "changed"
        with self.assertRaisesRegex(ValueError, "SHA256"):
            self.validate()
        self.record["quote_original"] = self.quote
        self.record["historical_claim_domains"] = ["invented_domain"]
        with self.assertRaisesRegex(ValueError, "Unknown historical domain"):
            self.validate()

    def test_duplicate_ids_and_source_errors_fail(self):
        self.document["relations"].append(dict(self.record))
        with self.assertRaisesRegex(ValueError, "Duplicate relation"):
            self.validate()
        self.document["relations"].pop()
        self.record["pdf_page_zero_based"] = 153
        with self.assertRaisesRegex(ValueError, "Unpinned source"):
            self.validate()

    def test_empty_ledger_does_not_fabricate_source_coverage(self):
        self.document["relations"] = []
        result = self.validate()
        self.assertEqual(result["relation_count"], 0)
        self.assertFalse(result["full_book_coverage_proven"])


if __name__ == "__main__":
    unittest.main()
