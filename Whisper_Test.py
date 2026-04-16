#!/usr/bin/env python3
"""
Whisper_Test.py — ClawPi
Records via Scarlett Solo at native 44100Hz, resamples to 16000Hz for Whisper.
"""

import whisper
import sounddevice as sd
import numpy as np
from scipy.signal import resample_poly

NATIVE_RATE  = 44100
TARGET_RATE  = 16000
DURATION     = 4
INPUT_DEVICE = 1  # Scarlett Solo USB

print("Loading Whisper base...")
model = whisper.load_model("base")
print("Ready.\n")

print(f"Recording {DURATION} seconds — say 'Raise move forward' clearly...\n")

audio = sd.rec(
    int(DURATION * NATIVE_RATE),
    samplerate=NATIVE_RATE,
    channels=2,
    dtype="float32",
    device=INPUT_DEVICE
)
sd.wait()

# Mix stereo down to mono
audio_mono = audio.mean(axis=1)

# Resample from 44100 to 16000 for Whisper
audio_resampled = resample_poly(audio_mono, TARGET_RATE, NATIVE_RATE)

peak = np.max(np.abs(audio_resampled))
print(f"Peak level: {peak:.4f}")

result = model.transcribe(audio_resampled.astype(np.float32), fp16=False, language="en")
print(f"\nWhisper heard: \"{result['text'].strip()}\"")
