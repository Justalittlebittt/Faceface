"""M16: provenance/coverage gates. Synthetic PDFs are only test fixtures."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import cangjie_corpus_stage as stage


class CorpusStagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scans = self.root / "scans"
        self.scans.mkdir()
        self.transcripts = self.root / "transcripts"
        self.scans.joinpath("part1.pdf").write_bytes(b"%PDF-test-one")
        self.scans.joinpath("part2.pdf").write_bytes(b"%PDF-test-two")
        self.catalog = self.root / "catalog.json"
        self.catalog.write_text(json.dumps({
            "cards": [{
                "id": "sample-one", "source_phrase": "口須方大",
                "source": {"source_url": stage.SCANS[0]["url"],
                           "pdf_page_zero_based": 27}
            }],
            "framework_notes": [{
                "id": "sample-two", "quote": "面上三停仔細看",
                "source": {"source_url": stage.SCANS[0]["url"],
                           "pdf_page_zero_based": 35}
            }],
        }, ensure_ascii=False), encoding="utf-8")

    def pdf_counts(self, path):
        return 153 if path.name == "part1.pdf" else 115

    def test_indexes_all_scanned_pages_without_claiming_transcription(self):
        with patch.object(stage, "pdf_pages", side_effect=self.pdf_counts):
            sources, pages, reviewed = stage.index_scans(self.scans, self.transcripts)
        self.assertEqual(len(sources), 2)
        self.assertEqual(len(pages), 268)
        self.assertEqual(len({p["page_id"] for p in pages}), 268)
        self.assertEqual(pages[-1]["pdf_page_zero_based"], 114)
        self.assertEqual({x["text_status"] for x in pages}, {"not_transcribed"})
        self.assertFalse(reviewed)

    def test_review_is_bound_to_exact_pdf_hash_text_hash_and_page_number(self):
        text = self.transcripts / "nlc-44091" / "027.txt"
        text.parent.mkdir(parents=True)
        text.write_text("口須方大", encoding="utf-8")
        self.assertFalse(stage.verify_page_review(text, "fake-hash", 27))
        review = text.with_suffix(".review.json")
        review.write_text(json.dumps({
            "reviewed_by": "human-reviewer",
            "source_pdf_sha256": "fake-hash",
            "pdf_page_zero_based": 27,
            "text_sha256": stage.sha256(text.read_bytes()),
        }), encoding="utf-8")
        self.assertTrue(stage.verify_page_review(text, "fake-hash", 27))
        text.write_text("口須方大漏字", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            stage.verify_page_review(text, "fake-hash", 27)

    def test_unreviewed_text_stays_out_of_agent_source_and_report(self):
        text = self.transcripts / "nlc-44091" / "027.txt"
        text.parent.mkdir(parents=True)
        text.write_text("OCR候选内容尚未核对", encoding="utf-8")
        with patch.object(stage, "pdf_pages", side_effect=self.pdf_counts):
            report = stage.stage(self.scans, self.transcripts, self.catalog, self.root / "out")
        self.assertEqual(report["scan_page_count"], 268)
        self.assertEqual(report["page_text_status_counts"]["unreviewed"], 1)
        self.assertEqual(report["page_text_status_counts"]["reviewed"], 0)
        self.assertFalse(report["agent_cangjie_extraction_performed"])
        self.assertFalse((self.root / "out" / "reviewed-transcription.md").exists())
        self.assertEqual(report["already_checked_short_excerpt_fixture_count"], 2)

    def test_pilot_keeps_only_existing_short_source_quotes(self):
        sources = [{"source_id": "nlc-44091", "page_count": 153},
                   {"source_id": "nlc-44092", "page_count": 115}]
        md, count = stage.pilot_from_existing_cards(self.catalog, sources)
        self.assertEqual(count, 2)
        self.assertIn("NOT THE WHOLE BOOK", md)
        self.assertIn("口須方大", md)
        self.assertIn("面上三停仔細看", md)

    def test_provenance_refuses_wrong_page_or_unidentified_scan(self):
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["cards"][0]["source"]["pdf_page_zero_based"] = 999
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            stage.pilot_from_existing_cards(self.catalog, [
                {"source_id": "nlc-44091", "page_count": 153},
                {"source_id": "nlc-44092", "page_count": 115},
            ])


if __name__ == "__main__":
    unittest.main()
