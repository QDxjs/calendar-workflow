"""Directory preferences remain portable, atomic and backward compatible."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import preferences


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.settings = self.root / "preferences" / "settings.json"
        settings = patch("preferences.preferences_path", return_value=self.settings)
        settings.start()
        self.addCleanup(settings.stop)

    def test_missing_custom_and_reset_follow_current_default(self):
        first, moved = self.root / "app-one", self.root / "app-two"
        custom = self.root / "my-calendars"
        self.assertEqual(preferences.load_output_directory(first), first)
        preferences.save_output_directory(custom)
        self.assertEqual(preferences.load_output_directory(moved), custom)
        preferences.save_output_directory(None)
        self.assertEqual(preferences.load_output_directory(moved), moved)

    def test_old_settings_and_other_fields_survive_save_and_reset(self):
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps({"output_directory": str(self.root), "future_option": [1, 2]}))
        self.assertEqual(preferences.load_output_directory(self.root / "default"), self.root)
        preferences.save_output_directory(self.root / "new")
        preferences.save_output_directory(None)
        self.assertEqual(json.loads(self.settings.read_text()), {"future_option": [1, 2]})

    def test_corrupt_settings_warn_and_can_be_replaced(self):
        self.settings.parent.mkdir()
        for content in ("{broken", "[]"):
            self.settings.write_text(content)
            self.assertTrue(preferences.preferences_warning())
            self.assertEqual(preferences.load_output_directory(self.root), self.root)
        preferences.save_output_directory(self.root)
        self.assertEqual(preferences.preferences_warning(), "")

    def test_failed_replace_preserves_old_settings_and_cleans_temporary_file(self):
        preferences.save_output_directory(self.root)
        original = self.settings.read_bytes()
        with patch("preferences.os.replace", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                preferences.save_output_directory(self.root / "new")
        self.assertEqual(self.settings.read_bytes(), original)
        self.assertEqual(list(self.settings.parent.iterdir()), [self.settings])

    def test_unavailable_absolute_directory_is_not_silently_replaced(self):
        unavailable = self.root / "missing-drive"
        preferences.save_output_directory(unavailable)
        self.assertEqual(preferences.load_output_directory(self.root), unavailable)
        self.assertFalse(unavailable.exists())

    def test_relative_and_invalid_stored_paths_are_rejected(self):
        with self.assertRaises(ValueError):
            preferences.save_output_directory(Path("relative"))
        self.settings.parent.mkdir()
        for invalid in ("relative", "", "\0", 42):
            self.settings.write_text(json.dumps({"output_directory": invalid}))
            self.assertEqual(preferences.load_output_directory(self.root), self.root)
            self.assertTrue(preferences.preferences_warning())

    def test_creator_preferences_default_empty_unchecked_and_persist_atomically(self):
        self.assertEqual(preferences.load_creator_preferences(), (False, ""))
        preferences.save_creator_preferences(True, "小林 · 2027")
        self.assertEqual(preferences.load_creator_preferences(), (True, "小林 · 2027"))
        preferences.save_creator_preferences(False, "小林 · 2027")
        self.assertEqual(preferences.load_creator_preferences(), (False, "小林 · 2027"))
        preferences.save_output_directory(self.root / "out")
        self.assertEqual(preferences.load_creator_preferences(), (False, "小林 · 2027"))
