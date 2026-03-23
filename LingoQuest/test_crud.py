from datetime import date
import unittest

from crud import (
    delete_word_entries,
    favorite_word_entries,
    import_parsed_entries,
    merge_entry,
    pick_word_of_day,
    toggle_favorite_flag,
    update_entry_field,
)


class CrudTests(unittest.TestCase):
    def test_merge_entry_preserves_existing_flags(self):
        merged = merge_entry(
            {"meaning": "cu", "is_favorite": True},
            {"meaning": "moi", "phonetic": "/moi/"},
            pragmatics="ctx",
        )
        self.assertEqual(merged["meaning"], "moi")
        self.assertTrue(merged["is_favorite"])
        self.assertEqual(merged["pragmatics"], "ctx")

    def test_toggle_favorite_flag_flips_value(self):
        words = {"apple": {"is_favorite": False}}
        self.assertTrue(toggle_favorite_flag(words, "apple"))
        self.assertFalse(toggle_favorite_flag(words, "apple"))

    def test_bulk_helpers_update_words(self):
        words = {
            "apple": {"is_favorite": False},
            "banana": {"is_favorite": False},
        }
        self.assertEqual(favorite_word_entries(words, {"apple", "banana"}), 2)
        self.assertEqual(delete_word_entries(words, {"banana"}), 1)
        self.assertNotIn("banana", words)

    def test_update_entry_field_updates_text_field(self):
        words = {"apple": {"meaning": "qua cu"}}
        self.assertTrue(update_entry_field(words, "apple", "meaning", "qua tao"))
        self.assertEqual(words["apple"]["meaning"], "qua tao")

    def test_import_parsed_entries_uses_resolver_when_meaning_missing(self):
        words = {}

        def resolver(word):
            return {"meaning": f"nghia cua {word}", "phonetic": "/test/"}

        added_count, failed_lines = import_parsed_entries(words, [("apple", None), ("banana", "qua chuoi")], resolver=resolver)

        self.assertEqual(added_count, 2)
        self.assertEqual(failed_lines, [])
        self.assertEqual(words["apple"]["phonetic"], "/test/")

    def test_pick_word_of_day_is_deterministic(self):
        words = {"apple": {}, "banana": {}, "cat": {}}
        picked = pick_word_of_day(words, date(2026, 3, 22))
        self.assertEqual(picked[0], "cat")


if __name__ == "__main__":
    unittest.main()
