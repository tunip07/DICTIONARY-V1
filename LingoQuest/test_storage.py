import tempfile
import unittest
from pathlib import Path

from storage import export_dictionary, import_legacy_txt, load_dictionary, repair_text, save_dictionary


class StorageTests(unittest.TestCase):
    def test_load_dictionary_upgrades_legacy_string_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "dictionary.json"
            path.write_text('{"Apple": "qua tao"}', encoding="utf-8")

            words = load_dictionary(path)

            self.assertIn("apple", words)
            self.assertEqual(words["apple"]["meaning"], "qua tao")
            self.assertFalse(words["apple"]["is_favorite"])

    def test_save_dictionary_normalizes_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "dictionary.json"

            saved = save_dictionary(path, {" Apple ": {"meaning": "qua tao"}})

            self.assertIn("apple", saved)
            self.assertEqual(load_dictionary(path)["apple"]["meaning"], "qua tao")
            self.assertIn(load_dictionary(path)["apple"]["level"], {"A1", "A2", "B1", "B2", "C1", "C2"})
            self.assertEqual(load_dictionary(path)["apple"]["direction"], "en-vi")
            self.assertIn(load_dictionary(path)["apple"]["level"], load_dictionary(path)["apple"]["tags"])

    def test_import_legacy_txt_supports_equals_and_tab_formats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "legacy.txt"
            source.write_text(
                "apple=qua tao\nbanana\t(n) trai chuoi\n",
                encoding="utf-8",
            )

            entries = import_legacy_txt(source)

            self.assertEqual(entries["apple"]["meaning"], "qua tao")
            self.assertEqual(entries["banana"]["pos"], "n")

    def test_repair_text_fixes_common_utf8_mojibake(self):
        self.assertEqual(repair_text("Chá»¯ nÃ y"), "Chữ này")
        self.assertEqual(repair_text("Äang phÃ¢n tÃ­ch"), "Đang phân tích")

    def test_export_dictionary_writes_csv_with_level_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "dictionary.csv"

            export_dictionary(path, {"apple": {"meaning": "qua tao", "level": "A1"}})

            exported = path.read_text(encoding="utf-8")
            self.assertIn("word,meaning,phonetic,pos,example,eng_meaning,pragmatics,level,is_favorite", exported)
            self.assertIn("apple,qua tao", exported)
            self.assertIn(",A1,", exported)


if __name__ == "__main__":
    unittest.main()
