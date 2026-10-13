import unittest
import numpy as np
from audio import amplify, VoiceProcessor


class AudioTests(unittest.TestCase):
    def test_disabled_effects_preserve_existing_boost(self):
        signal = np.linspace(-0.5, 0.5, 480, dtype=np.float32)[:, None]
        np.testing.assert_allclose(VoiceProcessor().process(signal, 12), amplify(signal, 12))

    def test_low_cut_attenuates_rumble_and_preserves_speech_frequencies(self):
        rms = []
        for frequency in (20, 1000):
            time = np.arange(4800) / 48000
            signal = (0.1 * np.sin(2 * np.pi * frequency * time)).astype(np.float32)[:, None]
            result = VoiceProcessor().process(signal, 0, low_cut=True)
            rms.append(float(np.sqrt(np.mean(result[2400:] ** 2))))
        self.assertLess(rms[0], rms[1] * 0.3)
        self.assertGreater(rms[1], 0.065)

    def test_gate_suppresses_quiet_noise_and_opens_for_voice(self):
        processor = VoiceProcessor()
        quiet = np.full((480, 1), 0.0001, dtype=np.float32)
        for _ in range(100):
            result = processor.process(quiet, 0, noise_gate=True, gate_db=-55)
        self.assertLess(float(np.max(result)), 0.00001)
        loud = np.full((480, 1), 0.02, dtype=np.float32)
        for _ in range(10):
            result = processor.process(loud, 0, noise_gate=True, gate_db=-55)
        np.testing.assert_allclose(result, loud, rtol=1e-5)

    def test_compressor_reduces_loud_voice_and_all_effects_remain_bounded(self):
        processor = VoiceProcessor()
        signal = np.full((480, 1), 0.4, dtype=np.float32)
        for _ in range(100):
            result = processor.process(signal, 0, compressor=True)
        self.assertLess(float(np.max(result)), 0.2)
        result = processor.process(signal, 36, low_cut=True, noise_gate=True, compressor=True)
        self.assertTrue(np.all(np.isfinite(result)))
        self.assertTrue(np.all(np.abs(result) <= 1))

    def test_quiet_signal_gets_requested_gain(self):
        signal = np.array([[-0.01], [0], [0.01]], dtype=np.float32)
        np.testing.assert_allclose(amplify(signal, 20), signal * 10, rtol=1e-6)

    def test_extreme_input_is_bounded_and_preserves_polarity(self):
        result = amplify(np.array([[-1], [0], [1]], dtype=np.float32), 36)
        self.assertTrue(np.all(np.isfinite(result)))
        self.assertTrue(np.all(np.abs(result) <= 1))
        self.assertLess(result[0, 0], 0)
        self.assertEqual(result[1, 0], 0)
        self.assertGreater(result[2, 0], 0)

    def test_soft_knee_is_continuous_and_monotonic(self):
        signal = np.linspace(0.84, 0.86, 1000, dtype=np.float32)
        result = amplify(signal, 0)
        self.assertTrue(np.all(np.diff(result) >= 0))
        self.assertLess(float(np.max(np.diff(result))), 0.00003)


if __name__ == '__main__':
    unittest.main()
