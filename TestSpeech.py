#!/usr/bin/env python3
"""
TestSpeech.py — ClawPi
Tests Piper TTS output through the JBL Go 3 via Bluetooth.
"""
import subprocess
import os
import tempfile

PIPER_PATH = os.path.expanduser("~/clawpi/piper/piper")
MODEL_PATH = os.path.expanduser("~/clawpi/piper/en_GB-alan-medium.onnx")
JBL_SINK   = "bluez_sink.F8_5C_7D_F3_84_55.a2dp_sink"

def speak(text: str):
    print(f"[TTS] Speaking: \"{text}\"")
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        subprocess.run(
            [PIPER_PATH, "--model", MODEL_PATH, "--output_file", tmp_path],
            input=text.encode(),
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            ["paplay", "--device", JBL_SINK, tmp_path],
            stderr=subprocess.PIPE
        )
        os.unlink(tmp_path)
        print("[TTS] Done.")
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    print("=== ClawPi TTS Test ===\n")
    lines = [
        "ClawPi online.",
        "Raise is ready for commands.",
    ]
    for line in lines:
        speak(line)
    print("\n=== Test complete. ===")
