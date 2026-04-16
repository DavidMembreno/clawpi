import whisper
import sounddevice as sd
import numpy as np
import requests
import subprocess
import sys
from scipy.signal import resample_poly

PI_URL = "http://192.168.1.203:5000/command"
NATIVE_RATE = 44100
TARGET_RATE = 16000
DURATION = 4
INPUT_DEVICE = 1
ENERGY_THRESHOLD = 0.02

COMMANDS = {
    "move forward": "MOVE_FORWARD",
    "move backward": "MOVE_BACKWARD",
    "move back": "MOVE_BACKWARD",
    "move left": "MOVE_LEFT",
    "move right": "MOVE_RIGHT",
    "arm up": "ARM_UP",
    "arm down": "ARM_DOWN",
    "raise arm": "ARM_UP",
    "lower arm": "ARM_DOWN",
    "grab": "GRAB",
    "release": "RELEASE",
    "let go": "RELEASE",
    "stop": "STOP",
    "spin four": "SPIN_FOUR",
    "spin times four": "SPIN_FOUR",
    "spin": "SPIN_ONCE",
}

VOLUME_COMMANDS = {
    "volume low":    "25",
    "volume medium": "50",
    "volume high":   "95",
}

WAKE_WORDS = ["command", "comment", "commence"]
EXIT_WORDS = ["shutdown", "power off", "shut down"]

PI_SSH = "pi-fruit@192.168.1.203"
JBL_SINK = "bluez_sink.F8_5C_7D_F3_84_55.a2dp_sink"

def set_volume(percent: str):
    print(f"[VOLUME] Setting to {percent}%")
    subprocess.run(
        ["ssh", PI_SSH, f"pactl set-sink-volume {JBL_SINK} {percent}%"],
        stderr=subprocess.DEVNULL
    )

print("Loading Whisper base model...")
model = whisper.load_model("base")
print("Ready.\n")

STATE = "IDLE"

while True:
    print(f"[{STATE}] Listening...")
    audio = sd.rec(int(DURATION * NATIVE_RATE), samplerate=NATIVE_RATE, channels=2, dtype="float32", device=INPUT_DEVICE)
    sd.wait()
    audio_mono = audio.mean(axis=1)
    peak = np.max(np.abs(audio_mono))

    if peak < ENERGY_THRESHOLD:
        continue

    audio_resampled = resample_poly(audio_mono, TARGET_RATE, NATIVE_RATE).astype(np.float32)
    result = model.transcribe(audio_resampled, fp16=False, language="en")
    text = result["text"].strip().lower()
    print(f"[WHISPER] Heard: {text}")

    if any(e in text for e in EXIT_WORDS):
        print("[EXIT] Shutting down.")
        sys.exit(0)

    if STATE == "IDLE":
        if any(w in text for w in WAKE_WORDS):
            STATE = "ACTIVE"
            print("[ACTIVE] Listening for commands.\n")

    elif STATE == "ACTIVE":
        if "stop" in text or "stay" in text:
            requests.post(PI_URL, json={"command": "STOP"})
            STATE = "IDLE"
            print("[IDLE] Going to sleep.\n")
            continue

        volume_matched = False
        for phrase, percent in VOLUME_COMMANDS.items():
            if phrase in text:
                set_volume(percent)
                volume_matched = True
                break

        if volume_matched:
            continue

        for phrase, cmd in COMMANDS.items():
            if phrase in text:
                print(f"[SEND] {cmd}")
                try:
                    r = requests.post(PI_URL, json={"command": cmd}, timeout=15)
                    print(f"[PI] {r.json()}")
                except Exception as e:
                    print(f"[ERROR] Could not reach Pi: {e}")
                break
