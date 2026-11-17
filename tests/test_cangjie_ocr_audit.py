"""M16.2 audit must fail on skipped, duplicated or silently approved OCR pages."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts import cangjie_ocr_audit as audit
from scripts.cangjie_corpus_stage import SCANS


class OcrAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_reports(self):
        reports = []
        for source in SCANS:
            sid, n = source["id"], source["expected_pages"]
            pages = [{
                "page_id": f"{sid}:p{i:03d}", "source_id": sid,
                "pdf_page_zero_based": i, "source_pdf_sha256": sid + "-hash",
                "requires_manual_page_review": True,
                "eligible_for_cangjie_verified_corpus": False,
                "state": "ocr_candidate", "han_char_count": 20,
                "mean_word_confidence": 75.0,
            } for i in range(n)]
            report = {
                "source_id": sid, "source_pdf_sha256": sid + "-hash",
                "total_pdf_pages": n, "processed_pages": n, "pages": pages,
            }
            path = self.root / (sid + ".json")
            path.write_text(json.dumps(report), encoding="utf-8")
            reports.append(path)
        return reports

    def test_complete_but_unreviewed(self):
        x = audit.aggregate(self.make_reports())
        self.assertEqual(x["ocr_attempted_pages"], 268)
        self.assertEqual(x["candidate_text_pages"], 268)
        self.assertEqual(x["human_reviewed_pages"], 0)
        self.assertFalse(x["full_book_agent_extraction_performed"])

    def test_missing_page_rejected(self):
        paths = self.make_reports()
        record = json.loads(paths[0].read_text())
        record["pages"].pop()
        record["processed_pages"] -= 1
        paths[0].write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "Missing OCR attempts"):
            audit.aggregate(paths)

    def test_unreviewed_is_never_promoted(self):
        paths = self.make_reports()
        record = json.loads(paths[0].read_text())
        record["pages"][0]["eligible_for_cangjie_verified_corpus"] = True
        paths[0].write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "promoted"):
            audit.aggregate(paths)

    def test_duplicate_page_rejected(self):
        paths = self.make_reports()
        record = json.loads(paths[0].read_text())
        record["pages"].append(record["pages"][0])
        record["processed_pages"] += 1
        paths[0].write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audit.aggregate(paths)


if __name__ == "__main__":
    unittest.main()
