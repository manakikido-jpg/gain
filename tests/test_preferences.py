import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
import preferences
from test_pipeline import make_app


class PreferenceTests(unittest.TestCase):
    def test_roundtrip_and_clamped_gain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            data = {'gain_db': 25, 'input': 'USB (MME)', 'output': 'CABLE Input (MME)', 'auto_start': True}
            preferences.save_preferences(data, path)
            self.assertEqual(preferences.load_preferences(path), data)
            data['gain_db'] = 100
            preferences.save_preferences(data, path)
            self.assertEqual(preferences.load_preferences(path)['gain_db'], 36)

    def test_corrupt_settings_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text('{broken')
            self.assertEqual(preferences.load_preferences(path), {})
            path.write_text('[]')
            self.assertEqual(preferences.load_preferences(path), {})

    def test_device_number_changes_and_ambiguous_names(self):
        self.assertEqual(preferences.find_device(['9: USB (MME)'], 'USB (MME)'), '9: USB (MME)')
        self.assertEqual(preferences.find_device(['9: USB (MME)', '10: USB (MME)'], 'USB (MME)'), '')
        self.assertEqual(preferences.find_device(['9: USB (WASAPI)'], 'USB (MME)'), '')

    def test_login_command_quotes_paths_and_uses_windowed_python(self):
        with tempfile.TemporaryDirectory(prefix='mic boost ') as directory:
            executable = Path(directory) / 'python.exe'
            windowed = Path(directory) / 'pythonw.exe'
            windowed.touch()
            with patch('preferences.sys.executable', str(executable)):
                command = preferences.login_command()
            self.assertTrue(command.startswith('"' + str(windowed)))
            self.assertIn('main.py', command)
            self.assertTrue(command.endswith('--login'))

    def test_effect_settings_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            preferences.save_preferences({'audio': {'gate_db': -999, 'noise_gate': 'yes'}}, path)
            audio = preferences.load_preferences(path)['audio']
            self.assertEqual(audio['gate_db'], -70)
            self.assertFalse(audio['noise_gate'])

    @patch('preferences.sys.platform', 'win32')
    @patch('preferences.login_command', return_value='"C:\\my app\\pythonw.exe" "C:\\my app\\main.py" --login')
    def test_registry_enable_disable(self, command):
        registry = MagicMock()
        with patch.dict('sys.modules', {'winreg': registry}):
            preferences.register_login(True)
            registry.SetValueEx.assert_called_once()
            self.assertEqual(registry.SetValueEx.call_args.args[-1], command.return_value)
            preferences.register_login(False)
            registry.DeleteValue.assert_called_once()

    def test_missing_saved_device_does_not_autostart(self):
        app = make_app()
        app.source.get.return_value = ''
        app.toggle = MagicMock()
        app.begin_automatically()
        app.toggle.assert_not_called()
        self.assertIn('見つかりません', app.failure)

    def test_speaker_never_autostarts(self):
        app = make_app()
        app.destination.get.return_value = 'Speakers'
        app.toggle = MagicMock()
        app.begin_automatically()
        app.toggle.assert_not_called()

    def test_saved_cable_autostarts(self):
        app = make_app()
        app.toggle = MagicMock()
        app.begin_automatically()
        app.toggle.assert_called_once()

    @patch('main.preferences.register_login', side_effect=OSError('access denied'))
    @patch('main.messagebox.showerror')
    def test_registration_failure_reverts_checkbox(self, error, register):
        app = make_app()
        app.auto_start = MagicMock()
        app.auto_start.get.return_value = True
        app.change_autostart()
        app.auto_start.set.assert_called_once_with(False)
        app.persist_settings.assert_not_called()


if __name__ == '__main__':
    unittest.main()
