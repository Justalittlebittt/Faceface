"""M16.3 source-anchor diagnostic tests; these do not attest OCR correctness."""
import unittest

from scripts.cangjie_ocr_benchmark import only_han, reference_anchors, anchor_probe


class ReferenceBenchmarkTests(unittest.TestCase):
    def test_retain_chinese_phrases_but_strip_separators(self):
        self.assertEqual(only_han("口 須 方 大。"), "口須方大")
        catalog={"cards":[{
            "source_phrase":"額為衡山；鼻為嵩山",
            "source":{"source_url":"https://commons.wikimedia.org/wiki/44091",
                      "pdf_page_zero_based":27}
        }],"framework_notes":[]}
        anchors=reference_anchors(catalog,"nlc-44091")
        self.assertEqual(anchors[27],["額為衡山","鼻為嵩山"])
        self.assertEqual(reference_anchors(catalog,"nlc-44092"),{})

    def test_scores_are_proxies_not_certification(self):
        r=anchor_probe("本頁記載口須方大，亦有鼻之用詞",["口須方大","鼻梁端直"])
        self.assertEqual(r["reference_phrase_count"],2)
        self.assertEqual(r["exact_phrase_count"],1)
        self.assertLess(r["mean_longest_contiguous_ratio"],1.0)
        self.assertGreater(r["mean_longest_contiguous_ratio"],0.5)

    def test_empty_reference_set_is_not_fake_zero_accuracy(self):
        r=anchor_probe("面相五官",[])
        self.assertEqual(r["reference_phrase_count"],0)
        self.assertIsNone(r["mean_longest_contiguous_ratio"])


if __name__ == "__main__":
    unittest.main()
