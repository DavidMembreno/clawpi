#!/usr/bin/env python3
from flask import Flask, request, jsonify
import subprocess
import tempfile
import os

SERIAL_ENABLED = False
SERIAL_PORT    = "/dev/ttyUSB0"
BAUD_RATE      = 115200

if SERIAL_ENABLED:
    import serial
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

PIPER_BIN   = os.path.expanduser("~/clawpi/piper/piper")
PIPER_MODEL = os.path.expanduser("~/clawpi/piper/en_GB-alan-medium.onnx")
JBL_SINK    = "bluez_sink.F8_5C_7D_F3_84_55.a2dp_sink"

app = Flask(__name__)

VALID_COMMANDS = {
    "MOVE_FORWARD":  "Moving forward.",
    "MOVE_BACKWARD": "Moving backward.",
    "MOVE_LEFT":     "Moving left.",
    "MOVE_RIGHT":    "Moving right.",
    "ARM_UP":        "Arm up.",
    "ARM_DOWN":      "Arm down.",
    "GRAB":          "Grabbing.",
    "RELEASE":       "Releasing.",
    "STOP":          "Stopping.",
    "SPIN_ONCE":     "Spinning once.",
    "SPIN_FOUR":     "Spinning four times.",
}

def speak(text: str):
    print(f"[TTS] {text}")
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        subprocess.run(
            [PIPER_BIN, "--model", PIPER_MODEL, "--output_file", tmp_path],
            input=text.encode(),
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            ["paplay", "--device", JBL_SINK, tmp_path],
            stderr=subprocess.DEVNULL
        )
        os.unlink(tmp_path)
    except FileNotFoundError as e:
        print(f"[TTS ERROR] {e}")

@app.route("/command", methods=["POST"])
def receive_command():
    data = request.get_json()
    cmd  = data.get("command", "").strip().upper()

    if cmd not in VALID_COMMANDS:
        return jsonify({"status": "error", "message": f"Unknown command: {cmd}"}), 400

    if SERIAL_ENABLED:
        ser.write(f"{cmd}\n".encode())
        print(f"[SERIAL] Sent: {cmd}")
    else:
        print(f"[SERIAL STUB] Would send: {cmd}")

    speak(VALID_COMMANDS[cmd])
    return jsonify({"status": "ok", "command": cmd})

if __name__ == "__main__":
    speak("Claw Pi online. Say command to begin.")
    print("ClawPi server running on port 5000")
    app.run(host="0.0.0.0", port=5000)
