import unittest
import numpy as np
from audio import amplify


class AudioTests(unittest.TestCase):
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
