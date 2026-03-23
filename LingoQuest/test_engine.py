import unittest

from engine import SearchEngine


class SearchEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = SearchEngine(
            {
                "apple": {"meaning": "qua tao"},
                "apply": {"meaning": "ap dung"},
                "banana": {"meaning": "chuoi"},
                "ubiquitous": {"meaning": "pho bien"},
            }
        )

    def test_exact_lookup_is_case_insensitive(self):
        self.assertIsNotNone(self.engine.exact_lookup("  APPLE "))

    def test_autocomplete_uses_prefix_index(self):
        self.assertEqual(self.engine.autocomplete("app"), ["apple", "apply"])

    def test_suggestions_stays_bounded_to_requested_limit(self):
        self.assertEqual(self.engine.suggestions("app", limit=1), ["apple"])

    def test_search_prefers_meaning_before_fuzzy(self):
        self.assertEqual(self.engine.search("chuoi"), ["banana"])

    def test_meaning_search_supports_multi_token_prefix_queries(self):
        self.assertEqual(self.engine.search("qua ta"), ["apple"])

    def test_fuzzy_is_only_used_as_fallback(self):
        results = self.engine.search("aplpe")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0], "apple")


if __name__ == "__main__":
    unittest.main()
