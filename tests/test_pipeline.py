"""Callback and lifecycle tests; device calls are explicitly simulated."""
from collections import deque
import threading
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from audio import VoiceProcessor
from main import MicrophoneBoost


def make_app():
    app = MicrophoneBoost.__new__(MicrophoneBoost)
    app.auto_timer = None
    app.persist_settings = MagicMock()
    app.processor = VoiceProcessor()
    app.audio_options = {}
    app.lock = threading.Lock()
    app.chunks = deque()
    app.offset = 0
    app.level = 0
    app.gain_db = 20
    app.audio_warning = False
    app.output_started = False
    app.failure = ""
    app.streams = []
    app.inputs = {"USB microphone": 0}
    app.outputs = {"CABLE Input": 1}
    app.devices = [{"max_input_channels": 1}, {"max_output_channels": 2}]
    for name in ("source", "destination", "button", "status", "root"):
        setattr(app, name, MagicMock())
    app.meter = {}
    app.source.get.return_value = "USB microphone"
    app.destination.get.return_value = "CABLE Input"
    return app


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def test_audio_keeps_order_across_different_callback_sizes_and_stereo(self):
        signal = np.linspace(-0.03, 0.03, 1000, dtype=np.float32)[:, None]
        self.app.capture(signal[:480], 480, None, False)
        self.app.capture(signal[480:], 520, None, False)
        output = []
        for frames in (123, 600, 277):
            block = np.empty((frames, 2), dtype=np.float32)
            self.app.playback(block, frames, None, False)
            output.append(block)
        actual = np.concatenate(output)
        np.testing.assert_allclose(actual[:, 0], signal[:, 0] * 10, rtol=1e-6)
        np.testing.assert_array_equal(actual[:, 0], actual[:, 1])
        self.assertFalse(self.app.audio_warning)
        self.assertFalse(self.app.chunks)

    def test_input_buffer_can_be_reused_without_corrupting_pending_audio(self):
        data = np.full((480, 1), 0.01, dtype=np.float32)
        self.app.capture(data, 480, None, False)
        data.fill(0)
        output = np.empty((480, 1), dtype=np.float32)
        self.app.playback(output, 480, None, False)
        np.testing.assert_allclose(output, 0.1, rtol=1e-6)

    def test_underrun_silences_unfilled_frames_and_reports_warning(self):
        self.app.capture(np.full((20, 1), 0.01, dtype=np.float32), 20, None, False)
        output = np.ones((40, 2), dtype=np.float32)
        self.app.playback(output, 40, None, False)
        np.testing.assert_allclose(output[:20], 0.1, rtol=1e-6)
        np.testing.assert_array_equal(output[20:], 0)
        self.assertTrue(self.app.audio_warning)

    def test_startup_silence_is_not_reported_as_underrun(self):
        output = np.ones((480, 2), dtype=np.float32)
        self.app.playback(output, 480, None, False)
        np.testing.assert_array_equal(output, 0)
        self.assertFalse(self.app.audio_warning)

    def test_backlog_is_bounded_and_discards_oldest_audio(self):
        for number in range(12):
            data = np.full((480, 1), number / 1000, dtype=np.float32)
            self.app.capture(data, 480, None, False)
        self.assertEqual(len(self.app.chunks), 8)
        self.assertTrue(self.app.audio_warning)
        output = np.empty((480, 1), dtype=np.float32)
        self.app.playback(output, 480, None, False)
        np.testing.assert_allclose(output, 0.04, rtol=1e-6)

    def test_device_status_is_reported(self):
        self.app.capture(np.zeros((480, 1), dtype=np.float32), 480, None, True)
        self.assertTrue(self.app.audio_warning)

    @patch('main.sd.check_input_settings')
    @patch('main.sd.check_output_settings')
    @patch('main.sd.OutputStream')
    @patch('main.sd.InputStream')
    def test_start_stop_and_restart(self, input_stream, output_stream, *checks):
        self.app.toggle()
        self.assertEqual(len(self.app.streams), 2)
        input_stream.return_value.start.assert_called_once()
        output_stream.return_value.start.assert_called_once()
        self.app.toggle()
        self.assertEqual(self.app.streams, [])
        input_stream.return_value.close.assert_called_once()
        output_stream.return_value.close.assert_called_once()
        self.app.toggle()
        self.assertEqual(len(self.app.streams), 2)

    @patch('main.messagebox.showerror')
    @patch('main.sd.check_input_settings')
    @patch('main.sd.check_output_settings')
    @patch('main.sd.OutputStream', side_effect=RuntimeError('cannot open output'))
    @patch('main.sd.InputStream')
    def test_output_open_failure_releases_already_open_input(self, input_stream, *mocks):
        self.app.toggle()
        input_stream.return_value.close.assert_called_once()
        self.assertEqual(self.app.streams, [])
        mocks[-1].assert_called_once()

    @patch('main.messagebox.showerror')
    @patch('main.sd.check_input_settings')
    @patch('main.sd.check_output_settings')
    @patch('main.sd.OutputStream')
    @patch('main.sd.InputStream')
    def test_start_failure_closes_both_devices(self, input_stream, output_stream, *mocks):
        output_stream.return_value.start.side_effect = RuntimeError('start failed')
        self.app.toggle()
        input_stream.return_value.close.assert_called_once()
        output_stream.return_value.close.assert_called_once()
        self.assertEqual(self.app.streams, [])

    def test_stop_error_does_not_leak_other_streams_or_pending_audio(self):
        first, second = MagicMock(), MagicMock()
        second.stop.side_effect = RuntimeError('device disconnected')
        self.app.streams = [first, second]
        self.app.chunks.append(np.ones((10, 1), dtype=np.float32))
        self.app.stop()
        first.close.assert_called_once()
        second.close.assert_called_once()
        self.assertEqual(self.app.streams, [])
        self.assertFalse(self.app.chunks)
        self.assertIn('device disconnected', self.app.failure)

    def test_disconnected_stream_is_not_displayed_as_running(self):
        stream = MagicMock()
        stream.active = False
        self.app.streams = [stream]
        self.app.refresh()
        self.assertEqual(self.app.streams, [])
        self.assertIn('停止しました', self.app.status.config.call_args.kwargs['text'])

    def test_close_cancels_ui_timer_and_closes_stream(self):
        stream = MagicMock()
        self.app.streams = [stream]
        self.app.refresh_timer = 'scheduled-refresh'
        self.app.close()
        self.app.root.after_cancel.assert_called_once_with('scheduled-refresh')
        stream.close.assert_called_once()
        self.app.root.destroy.assert_called_once()

    @patch('main.messagebox.showerror')
    @patch('main.sd.InputStream')
    def test_missing_device_does_not_open_stream(self, input_stream, error):
        self.app.source.get.return_value = ''
        self.app.toggle()
        input_stream.assert_not_called()
        error.assert_called_once()

    @patch('main.messagebox.askyesno', return_value=False)
    @patch('main.sd.InputStream')
    def test_declined_speaker_warning_does_not_start_audio(self, input_stream, question):
        self.app.outputs = {'Speakers': 1}
        self.app.destination.get.return_value = 'Speakers'
        self.app.toggle()
        input_stream.assert_not_called()
        question.assert_called_once()


if __name__ == '__main__':
    unittest.main()
