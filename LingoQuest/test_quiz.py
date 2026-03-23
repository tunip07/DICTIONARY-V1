from datetime import date
import unittest

from quiz import build_daily_challenge, build_flashcard_round, build_matching_round


class QuizBuildersTests(unittest.TestCase):
    def setUp(self):
        self.words = {
            "apple": {"meaning": "quả táo", "phonetic": "/ap/", "example": "an apple a day", "level": "A1"},
            "banana": {"meaning": "quả chuối", "phonetic": "/ba/", "example": "yellow banana", "level": "A1"},
            "cat": {"meaning": "con mèo", "phonetic": "/kat/", "example": "the cat sleeps", "level": "A1"},
            "dragon": {"meaning": "rồng", "phonetic": "/dra/", "example": "mythical dragon", "level": "B1"},
        }

    def test_build_flashcard_round_uses_existing_entry_fields(self):
        round_data = build_flashcard_round(self.words)

        self.assertIsNotNone(round_data)
        word = round_data["word"]
        self.assertIn(word, self.words)
        self.assertEqual(round_data["meaning"], self.words[word]["meaning"])
        self.assertEqual(round_data["level"], self.words[word]["level"])

    def test_build_matching_round_returns_consistent_pairs(self):
        round_data = build_matching_round(self.words, pair_count=4)

        self.assertIsNotNone(round_data)
        pair_ids = {pair["id"] for pair in round_data["pairs"]}
        self.assertEqual(pair_ids, {pair["id"] for pair in round_data["left"]})
        self.assertEqual(pair_ids, {pair["id"] for pair in round_data["right"]})
        self.assertEqual(len(pair_ids), 4)

    def test_build_daily_challenge_is_deterministic_for_one_day(self):
        first = build_daily_challenge(self.words, day=date(2026, 3, 22), size=3)
        second = build_daily_challenge(self.words, day=date(2026, 3, 22), size=3)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)

    def test_build_daily_challenge_requires_at_least_four_words(self):
        limited_words = {
            "apple": {"meaning": "quả táo"},
            "banana": {"meaning": "quả chuối"},
            "cat": {"meaning": "con mèo"},
        }

        self.assertEqual(build_daily_challenge(limited_words, day=date(2026, 3, 22), size=3), [])


if __name__ == "__main__":
    unittest.main()
