"""Audio processing shared by the GUI and tests."""
import numpy as np


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
