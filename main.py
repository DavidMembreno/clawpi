#!/usr/bin/env python3
"""
main.py — ClawPi
Voice-controlled VEX V5 Clawbot via Raspberry Pi 4B
"""

import os
import json
import tempfile
import subprocess
import sys
import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from scipy.signal import resample_poly

SPEAKING = False

# ── Serial config ─────────────────────────────────────────────────────────────
SERIAL_ENABLED = False
SERIAL_PORT    = "/dev/ttyUSB0"
BAUD_RATE      = 115200

if SERIAL_ENABLED:
    import serial
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

# ── Piper TTS config ──────────────────────────────────────────────────────────
PIPER_BIN   = os.path.expanduser("~/clawpi/piper/piper")
PIPER_MODEL = os.path.expanduser("~/clawpi/piper/en_GB-alan-medium.onnx")
JBL_SINK    = "bluez_sink.F8_5C_7D_F3_84_55.a2dp_sink"

# ── Audio config ──────────────────────────────────────────────────────────────
NATIVE_RATE  = 44100
SAMPLE_RATE  = 16000
INPUT_DEVICE = 1
VOSK_CHUNK   = 11025

# ── Vosk model ────────────────────────────────────────────────────────────────
VOSK_MODEL_PATH = os.path.expanduser("~/clawpi/vosk-model")

# ── Fixed grammar ─────────────────────────────────────────────────────────────
GRAMMAR = json.dumps([
    "command",
    "move forward", "move backward", "move back",
    "move left", "move right",
    "arm up", "arm down", "raise arm", "lower arm",
    "grab", "release", "let go",
    "stop", "stay", "halt", "sleep",
    "shutdown", "shut down", "power off",
    "[unk]"
])

WAKE_WORDS   = ["command"]
STOP_PHRASES = ["stop", "stay", "halt", "sleep"]
EXIT_PHRASES = ["shutdown", "shut down", "power off"]

COMMANDS = {
    "move forward":  ("MOVE_FORWARD",  "Moving forward."),
    "move backward": ("MOVE_BACKWARD", "Moving backward."),
    "move back":     ("MOVE_BACKWARD", "Moving backward."),
    "move left":     ("MOVE_LEFT",     "Moving left."),
    "move right":    ("MOVE_RIGHT",    "Moving right."),
    "arm up":        ("ARM_UP",        "Arm up."),
    "arm down":      ("ARM_DOWN",      "Arm down."),
    "raise arm":     ("ARM_UP",        "Arm up."),
    "lower arm":     ("ARM_DOWN",      "Arm down."),
    "grab":          ("GRAB",          "Grabbing."),
    "release":       ("RELEASE",       "Releasing."),
    "let go":        ("RELEASE",       "Releasing."),
}

AMBIGUOUS_GROUPS = [
    {"arm up", "arm down"},
    {"move forward", "move backward"},
    {"grab", "release"},
]

# ─────────────────────────────────────────────────────────────────────────────

def speak(text: str):
    global SPEAKING
    print(f"[TTS] {text}")
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        subprocess.run(
            [PIPER_BIN, "--model", PIPER_MODEL, "--output_file", tmp_path],
            input=text.encode(),
            stderr=subprocess.DEVNULL
        )
        SPEAKING = True
        subprocess.run(["paplay", "--device", JBL_SINK, tmp_path], stderr=subprocess.DEVNULL)
        SPEAKING = False
        os.unlink(tmp_path)
    except FileNotFoundError as e:
        print(f"[TTS ERROR] {e}")


def send_command(cmd: str):
    if SERIAL_ENABLED:
        ser.write(f"{cmd}\n".encode())
        print(f"[SERIAL] Sent: {cmd}")
    else:
        print(f"[SERIAL STUB] Would send: {cmd}")


def process_chunk(data) -> bytes:
    audio_np     = np.frombuffer(bytes(data), dtype=np.int16)
    audio_stereo = audio_np.reshape(-1, 2)
    audio_mono   = audio_stereo.mean(axis=1).astype(np.float32)
    audio_rs     = resample_poly(audio_mono, SAMPLE_RATE, NATIVE_RATE).astype(np.int16)
    return audio_rs.tobytes()


def drain_stream(stream, chunks: int = 8):
    for _ in range(chunks):
        stream.read(VOSK_CHUNK)


def parse_command(text: str):
    for phrase in EXIT_PHRASES:
        if phrase in text:
            return ("EXIT", None)
    for phrase in STOP_PHRASES:
        if phrase in text:
            return ("STOP", None)
    for phrase in WAKE_WORDS:
        if phrase in text:
            return ("WAKE", None)

    matched = []
    for phrase, payload in COMMANDS.items():
        if phrase in text:
            matched.append((phrase, payload))

    if len(matched) == 1:
        return ("EXECUTE", matched[0][1])
    if len(matched) > 1:
        matched_phrases = {m[0] for m in matched}
        for group in AMBIGUOUS_GROUPS:
            if matched_phrases & group == matched_phrases:
                options = " or ".join(matched_phrases)
                return ("CLARIFY", f"Did you mean {options}?")
        return ("EXECUTE", matched[0][1])

    return None


def run(recognizer):
    global SPEAKING
    STATE = "IDLE"
    print("[IDLE] Streaming — say 'command' to begin.\n")

    with sd.RawInputStream(
        samplerate=NATIVE_RATE,
        blocksize=VOSK_CHUNK,
        dtype="int16",
        channels=2,
        device=INPUT_DEVICE
    ) as stream:
        while True:
            data, _ = stream.read(VOSK_CHUNK)
            chunk   = process_chunk(data)

            if recognizer.AcceptWaveform(chunk):
                result = json.loads(recognizer.Result())
                text   = result.get("text", "").strip().lower()
            else:
                partial = json.loads(recognizer.PartialResult())
                text    = partial.get("partial", "").strip().lower()

            text = text.replace("[unk]", "").strip()
            if not text:
                continue

            if SPEAKING:
                continue

            print(f"[VOSK:{STATE}] \"{text}\"")
            result = parse_command(text)
            if result is None:
                continue

            action, payload = result

            if STATE == "IDLE":
                if action == "WAKE":
                    STATE = "ACTIVE"
                    recognizer.Reset()
                    drain_stream(stream)
                    speak("Ready. Awaiting commands.")
                    print("[ACTIVE] Active mode — say stop to idle, shutdown to exit.\n")
                elif action == "EXIT":
                    return "exit"

            elif STATE == "ACTIVE":
                if action == "EXIT":
                    return "exit"
                elif action == "STOP":
                    send_command("STOP")
                    STATE = "IDLE"
                    recognizer.Reset()
                    drain_stream(stream)
                    speak("Stopping. Going to sleep.")
                    print("[IDLE] Streaming — say 'command' to begin.\n")
                elif action == "WAKE":
                    recognizer.Reset()
                    drain_stream(stream)
                elif action == "CLARIFY":
                    speak(payload)
                    recognizer.Reset()
                    drain_stream(stream)
                elif action == "EXECUTE":
                    serial_cmd, ack = payload
                    send_command(serial_cmd)
                    recognizer.Reset()
                    drain_stream(stream)
                    speak(ack)


def main():
    print("=" * 40)
    print("  ClawPi Online")
    print(f"  Serial : {'ENABLED' if SERIAL_ENABLED else 'STUB MODE'}")
    print(f"  Engine : Vosk full streaming")
    print(f"  Mic    : Device {INPUT_DEVICE} @ {NATIVE_RATE}Hz -> {SAMPLE_RATE}Hz")
    print(f"  Speaker: JBL Go 3 Bluetooth")
    print("=" * 40 + "\n")

    print("[INIT] Loading Vosk model with fixed grammar...")
    vosk_model = Model(VOSK_MODEL_PATH)
    recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE, GRAMMAR)
    recognizer.SetWords(True)
    print("[INIT] Vosk ready.\n")

    speak("Claw Pi online. Say command to begin.")

    try:
        run(recognizer)
    except KeyboardInterrupt:
        pass

    print("\n[EXIT] Shutting down ClawPi.")
    speak("Shutting down. Goodbye.")
    sys.exit(0)


if __name__ == "__main__":
    main()
