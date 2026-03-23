import unittest

from api import build_translation_fallback_entry, fetch_and_cache_word, parse_dictionaryapi_payload


class ApiTests(unittest.TestCase):
    def test_parse_dictionaryapi_payload_extracts_first_definition(self):
        payload = [
            {
                "word": "apple",
                "phonetic": "/ˈap.əl/",
                "meanings": [
                    {
                        "partOfSpeech": "noun",
                        "definitions": [
                            {
                                "definition": "a round fruit with red or green skin",
                                "example": "She ate an apple.",
                            }
                        ],
                    }
                ],
            }
        ]

        result = parse_dictionaryapi_payload(payload)

        self.assertIsNotNone(result)
        self.assertEqual(result["pos"], "noun")
        self.assertEqual(result["part_of_speech"], "noun")
        self.assertEqual(result["eng_meaning"], "a round fruit with red or green skin")
        self.assertEqual(result["definitions"][0]["definition"], "a round fruit with red or green skin")

    def test_fetch_and_cache_word_applies_suggestion_fallback(self):
        words = {}

        def fake_fetch_entry(word):
            if word == "apple":
                return {"meaning": "qua tao", "phonetic": "/ap/", "pos": "noun", "example": "", "eng_meaning": "apple"}
            return None

        def fake_fetch_suggestions(word, max_results=1):
            self.assertEqual(word, "appel")
            return ["apple"]

        def fake_fetch_collocations(word):
            self.assertEqual(word, "apple")
            return "Hay đi kèm với: pie"

        result = fetch_and_cache_word(
            words,
            "appel",
            fetch_entry=fake_fetch_entry,
            fetch_suggestions=fake_fetch_suggestions,
            fetch_collocations=fake_fetch_collocations,
        )

        self.assertTrue(result["found"])
        self.assertTrue(result["corrected"])
        self.assertIn("apple", words)
        self.assertEqual(words["apple"]["pragmatics"], "Hay đi kèm với: pie")

    def test_fetch_and_cache_word_uses_translation_fallback_when_dictionary_misses(self):
        words = {}

        result = fetch_and_cache_word(
            words,
            "ubiquitous",
            fetch_entry=lambda _word: None,
            fetch_suggestions=lambda _word, max_results=1: [],
            fetch_collocations=lambda _word: "Đang phân tích ngữ cảnh...",
            translate=lambda _word: "phổ biến khắp nơi",
        )

        self.assertTrue(result["found"])
        self.assertEqual(result["source"], "translate_fallback")
        self.assertIn("ubiquitous", words)
        self.assertEqual(words["ubiquitous"]["meaning"], "phổ biến khắp nơi")

    def test_build_translation_fallback_entry_ignores_self_translation(self):
        self.assertIsNone(build_translation_fallback_entry("hello", "hello"))


if __name__ == "__main__":
    unittest.main()
