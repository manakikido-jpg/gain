"""Actual Tk widgets; audio device discovery is simulated, not hardware-tested."""
import tkinter as tk
import sys
import unittest
from unittest.mock import patch

from main import MicrophoneBoost


class GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            if sys.platform == 'win32':
                raise
            self.skipTest(f'Display unavailable: {error}')
        self.root.withdraw()
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.root.destroy()

    def create_app(self, devices):
        with patch('main.sd.query_devices', return_value=devices), patch(
            'main.sd.query_hostapis', return_value=[{'name': 'Windows WASAPI'}]
        ):
            app = MicrophoneBoost(self.root)
        self.root.update()
        return app

    def test_native_audio_library_enumeration_and_real_window_startup(self):
        # Uses the installed PortAudio library; does not claim microphone I/O.
        app = MicrophoneBoost(self.root)
        self.root.update()
        self.assertEqual(app.button.cget('text'), '開始')
        self.assertTrue(self.root.winfo_exists())
        app.stop()
        self.root.update()

    def test_widgets_and_device_selection(self):
        app = self.create_app([
            {'name': 'USB microphone', 'hostapi': 0, 'max_input_channels': 1, 'max_output_channels': 0},
            {'name': 'CABLE Input', 'hostapi': 0, 'max_input_channels': 0, 'max_output_channels': 2},
        ])
        self.assertIn('USB microphone', app.source.get())
        self.assertIn('CABLE Input', app.destination.get())
        app.set_gain('24')
        self.assertEqual(app.gain_db, 24)
        self.assertIn('24', app.gain_label.cget('text'))
        app.level = 0.5
        app.refresh()
        self.assertEqual(float(app.meter['value']), 50)

    @patch('main.messagebox.showerror')
    def test_no_audio_devices_can_open_ui_and_show_useful_error(self, error):
        app = self.create_app([])
        app.button.invoke()
        error.assert_called_once()
        self.assertEqual(app.button.cget('text'), '開始')

    @patch('main.sd.check_input_settings')
    @patch('main.sd.check_output_settings')
    @patch('main.sd.InputStream')
    @patch('main.sd.OutputStream')
    def test_buttons_disable_device_selection_and_enable_on_stop(self, *mocks):
        app = self.create_app([
            {'name': 'USB microphone', 'hostapi': 0, 'max_input_channels': 1, 'max_output_channels': 0},
            {'name': 'CABLE Input', 'hostapi': 0, 'max_input_channels': 0, 'max_output_channels': 2},
        ])
        app.button.invoke()
        self.assertEqual(app.button.cget('text'), '停止')
        self.assertEqual(str(app.source.cget('state')), 'disabled')
        app.button.invoke()
        self.assertEqual(app.button.cget('text'), '開始')
        self.assertEqual(str(app.source.cget('state')), 'readonly')


if __name__ == '__main__':
    unittest.main()
