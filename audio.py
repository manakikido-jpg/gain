"""Audio processing shared by the GUI and tests."""
import numpy as np


class VoiceProcessor:
    """Stateful speech filters; defaults preserve the original microphone sound."""
    def __init__(self, rate=48000):
        self.rate = rate
        self.previous_input = 0.0
        self.previous_output = 0.0
        self.gate_gain = 1.0
        self.compressor_gain = 1.0

    def process(self, samples, gain_db, low_cut=False, noise_gate=False,
                gate_db=-55, compressor=False):
        signal = np.asarray(samples, dtype=np.float32).copy()
        if not signal.size:
            return signal
        if low_cut:
            alpha = np.exp(-2 * np.pi * 80 / self.rate)
            flat = signal[:, 0]
            for index in range(len(flat)):
                current = float(flat[index])
                self.previous_output = alpha * (self.previous_output + current - self.previous_input)
                self.previous_input = current
                flat[index] = self.previous_output
        else:
            self.previous_input = self.previous_output = 0.0
        rms = float(np.sqrt(np.mean(signal.astype(np.float64) ** 2)))
        if noise_gate:
            target = 1.0 if rms >= 10 ** (gate_db / 20) else 10 ** (-24 / 20)
            curve = self.smooth(self.gate_gain, target, len(signal), 0.005 if target > self.gate_gain else 0.12)
            self.gate_gain = float(curve[-1])
            signal *= curve[:, None]
        else:
            self.gate_gain = 1.0
        signal *= 10 ** (gain_db / 20)
        if compressor:
            level = float(np.sqrt(np.mean(signal.astype(np.float64) ** 2)))
            db = 20 * np.log10(max(level, 1e-12))
            # 3:1 compression above -18 dBFS; no automatic makeup boost.
            reduction = max(0.0, db + 18) * (1 - 1 / 3)
            target = 10 ** (-reduction / 20)
            curve = self.smooth(self.compressor_gain, target, len(signal),
                                0.01 if target < self.compressor_gain else 0.15)
            self.compressor_gain = float(curve[-1])
            signal *= curve[:, None]
        else:
            self.compressor_gain = 1.0
        return amplify(signal, 0)

    def smooth(self, previous, target, frames, seconds):
        return target + (previous - target) * np.exp(-np.arange(1, frames + 1) / (self.rate * seconds))


def amplify(samples, gain_db):
    boosted = np.asarray(samples, dtype=np.float32) * (10 ** (gain_db / 20))
    magnitude = np.abs(boosted)
    # A continuous soft knee bounds the signal without wrapping or hard clipping.
    limited = np.where(
        magnitude <= 0.85,
        magnitude,
        0.85 + 0.15 * np.tanh((magnitude - 0.85) / 0.15),
    )
    return (np.sign(boosted) * limited).astype(np.float32)
