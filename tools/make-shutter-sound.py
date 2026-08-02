#!/usr/bin/env python3
"""Synthesise the capture sound: packaging/shutter.wav.

A camera shutter is two mechanical clicks in quick succession — the mirror
going up, then the blades closing. Each is a burst of noise shaped by a
lowpass filter and an exponential decay, with a damped sine underneath for the
body of the mechanism. That is a broadband transient, which is exactly what
MIDI cannot express: MIDI carries note messages, and would need a synthesiser
and a soundfont at playback time to make any sound at all.

Deterministic: the noise uses a fixed seed, so re-running this reproduces the
same file byte for byte.

    python3 tools/make-shutter-sound.py
"""

import math
import os
import random
import struct
import sys
import wave

RATE = 44100
PEAK = 0.82  # leave headroom so playback never clips
SEED = 20260802

OUTPUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, "packaging", "shutter.wav"
)


class Click:
    """One mechanical click.

    brightness  0..1, how much high frequency survives the lowpass
    decay       seconds; the noise envelope's time constant
    body_hz     the resonance you feel more than hear
    """

    def __init__(self, at, gain, brightness, decay, body_hz, body_gain):
        self.at = at
        self.gain = gain
        self.brightness = brightness
        self.decay = decay
        self.body_hz = body_hz
        self.body_gain = body_gain

    def render(self, buffer, rng):
        start = int(self.at * RATE)
        length = int(self.decay * 6 * RATE)
        lowpass = 0.0
        for i in range(length):
            index = start + i
            if index >= len(buffer):
                break
            t = i / RATE
            # One-pole lowpass over white noise: the "shhk" of the mechanism.
            lowpass += (rng.uniform(-1.0, 1.0) - lowpass) * self.brightness
            noise = lowpass * math.exp(-t / self.decay)
            # A damped sine gives the click a body instead of a bare tick.
            body = (
                math.sin(2 * math.pi * self.body_hz * t)
                * math.exp(-t / (self.decay * 1.8))
                * self.body_gain
            )
            buffer[index] += (noise + body) * self.gain


# Mirror up, then the blades: the second is tighter and brighter.
CLICKS = (
    Click(at=0.000, gain=1.00, brightness=0.55, decay=0.016, body_hz=185, body_gain=0.55),
    Click(at=0.080, gain=0.78, brightness=0.78, decay=0.011, body_hz=320, body_gain=0.30),
)

# Long enough for the second click to die away, and no longer.
DURATION = 0.155


def build():
    buffer = [0.0] * int(DURATION * RATE)
    rng = random.Random(SEED)
    for click in CLICKS:
        click.render(buffer, rng)
    normalise(buffer)
    fade_out(buffer, milliseconds=6)
    return buffer


def normalise(buffer):
    loudest = max(abs(sample) for sample in buffer) or 1.0
    scale = PEAK / loudest
    for i, sample in enumerate(buffer):
        buffer[i] = sample * scale


def fade_out(buffer, milliseconds):
    """Ramp the tail to silence so the file does not end on a step."""
    length = min(int(milliseconds / 1000 * RATE), len(buffer))
    for i in range(length):
        buffer[len(buffer) - length + i] *= 1.0 - (i / length)


def write(path, buffer):
    frames = b"".join(
        struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767)) for sample in buffer
    )
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(frames)


def main():
    buffer = build()
    path = os.path.normpath(OUTPUT)
    write(path, buffer)
    print(
        "wrote %s  (%.0f ms, %d Hz mono, %d bytes)"
        % (path, DURATION * 1000, RATE, os.path.getsize(path))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
