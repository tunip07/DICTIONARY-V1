import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import utils


class UtilsTests(unittest.TestCase):
    def test_today_key_formats_iso_date(self):
        self.assertEqual(utils.today_key(date(2026, 3, 22)), "2026-03-22")

    def test_json_state_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            payload = {"recent_searches": ["hello"], "daily_challenge": {"streak": 2}}

            utils.save_json_state(path, payload)

            self.assertEqual(utils.load_json_state(path), payload)

    def test_app_storage_dir_uses_appdata_when_frozen(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(utils.sys, "frozen", True, create=True):
                with patch.dict("os.environ", {"APPDATA": tmpdir}):
                    storage_dir = utils.app_storage_dir()

            self.assertEqual(storage_dir, Path(tmpdir) / utils.APP_NAME)
            self.assertTrue(storage_dir.exists())


if __name__ == "__main__":
    unittest.main()
