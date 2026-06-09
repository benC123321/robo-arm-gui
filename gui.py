#!/usr/bin/env python3
import argparse
import tkinter as tk
from tkinter import ttk

import grpc
import motor_control_pb2
import motor_control_pb2_grpc

UINT8_MAX  = 255
UINT16_MAX = 65535
WEB_PORT   = 6001

_WEB_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Robo Arm Control</title>
  <style>
    body { font-family: sans-serif; max-width: 420px; margin: 48px auto; padding: 0 16px; }
    h1   { font-size: 1.3rem; margin-bottom: 24px; }
    .row { display: flex; align-items: center; margin-bottom: 12px; }
    .row label { width: 200px; flex-shrink: 0; }
    .row input  { flex: 1; padding: 4px 6px; }
    .sep  { border: none; border-top: 1px solid #ccc; margin: 16px 0; }
    button { width: 100%; padding: 8px; margin-top: 8px; font-size: 1rem; cursor: pointer; }
    .status { margin-top: 14px; font-size: 0.9rem; color: {{ color }}; }
  </style>
</head>
<body>
  <h1>Robo Arm Control</h1>
  <form method="post">
    <div class="row">
      <label>IP Address</label>
      <input name="ip" value="{{ ip }}" required>
    </div>
    <div class="row">
      <label>Port</label>
      <input name="port" type="number" value="{{ port }}" min="1" max="65535" required>
    </div>
    <hr class="sep">
    <div class="row">
      <label>Motor ID (0 – 255)</label>
      <input name="motor_id" type="number" value="{{ motor_id }}" min="0" max="255" required>
    </div>
    <div class="row">
      <label>Position (0 – 65535)</label>
      <input name="position" type="number" value="{{ position }}" min="0" max="65535" required>
    </div>
    <div class="row">
      <label>Move Time ms (0 – 65535)</label>
      <input name="move_time" type="number" value="{{ move_time }}" min="0" max="65535" required>
    </div>
    <button type="submit">Send</button>
  </form>
  {% if status %}
  <p class="status">{{ status }}</p>
  {% endif %}
</body>
</html>"""


def _validate_uint(value: str, max_val: int) -> tuple[bool, int | None]:
    if not value.strip():
        return False, None
    try:
        n = int(value)
    except ValueError:
        return False, None
    return (True, n) if 0 <= n <= max_val else (False, None)


def _send_grpc(ip: str, port: int, motor_id: int, position: int, move_time: int) -> tuple[bool, str]:
    try:
        with grpc.insecure_channel(f"{ip}:{port}") as channel:
            stub = motor_control_pb2_grpc.MotorControlServiceStub(channel)
            response = stub.SendCommand(
                motor_control_pb2.MotorCommandRequest(
                    motor_id=motor_id,
                    position=position,
                    move_time=move_time,
                )
            )
        return response.success, response.message
    except grpc.RpcError as e:
        return False, f"gRPC {e.code().name}: {e.details()}"


# --- Web mode ---

def run_web():
    from flask import Flask, request, render_template_string

    app = Flask(__name__)

    defaults = dict(ip="localhost", port=50051, motor_id="", position="", move_time="")

    @app.route("/", methods=["GET", "POST"])
    def index():
        status, color = "", "#555"
        values = dict(defaults)

        if request.method == "POST":
            values = {k: request.form.get(k, "") for k in defaults}

            ok_id,  motor_id  = _validate_uint(values["motor_id"],  UINT8_MAX)
            ok_pos, position  = _validate_uint(values["position"],  UINT16_MAX)
            ok_mt,  move_time = _validate_uint(values["move_time"], UINT16_MAX)

            errors = []
            if not ok_id:
                errors.append("Motor ID must be 0–255")
            if not ok_pos:
                errors.append("Position must be 0–65535")
            if not ok_mt:
                errors.append("Move Time must be 0–65535")

            if errors:
                status, color = " | ".join(errors), "#c00"
            else:
                try:
                    grpc_port = int(values["port"])
                except ValueError:
                    status, color = "Port must be an integer", "#c00"
                else:
                    success, msg = _send_grpc(values["ip"], grpc_port, motor_id, position, move_time)
                    status = f"OK — {msg}" if success else f"Error: {msg}"
                    color  = "#080" if success else "#c00"

        return render_template_string(_WEB_TEMPLATE, status=status, color=color, **values)

    print(f"Web UI running at http://0.0.0.0:{WEB_PORT}")
    app.run(host="0.0.0.0", port=WEB_PORT)


# --- Desktop mode ---

class RoboArmGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Robo Arm Control")
        self.resizable(False, False)
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        frame = ttk.Frame(self, padding=16)
        frame.grid(row=0, column=0)

        ttk.Label(frame, text="IP Address").grid(row=0, column=0, sticky="e", **pad)
        self._ip = ttk.Entry(frame, width=20)
        self._ip.insert(0, "localhost")
        self._ip.grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(frame, text="Port").grid(row=0, column=2, sticky="e", **pad)
        self._port = ttk.Entry(frame, width=8)
        self._port.insert(0, "50051")
        self._port.grid(row=0, column=3, sticky="w", **pad)

        ttk.Separator(frame, orient="horizontal").grid(
            row=1, column=0, columnspan=4, sticky="ew", pady=8
        )

        ttk.Label(frame, text="Motor ID  (0 – 255)").grid(row=2, column=0, sticky="e", **pad)
        self._motor_id = ttk.Entry(frame, width=10)
        self._motor_id.grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(frame, text="Position  (0 – 65535)").grid(row=3, column=0, sticky="e", **pad)
        self._position = ttk.Entry(frame, width=10)
        self._position.grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(frame, text="Move Time ms  (0 – 65535)").grid(row=4, column=0, sticky="e", **pad)
        self._move_time = ttk.Entry(frame, width=10)
        self._move_time.grid(row=4, column=1, sticky="w", **pad)

        ttk.Button(frame, text="Send", command=self._on_send).grid(
            row=5, column=0, columnspan=4, pady=(12, 4)
        )

        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self._status_var, foreground="gray").grid(
            row=6, column=0, columnspan=4, **pad
        )

    def _on_send(self):
        ok_id,  motor_id  = _validate_uint(self._motor_id.get(),  UINT8_MAX)
        ok_pos, position  = _validate_uint(self._position.get(),  UINT16_MAX)
        ok_mt,  move_time = _validate_uint(self._move_time.get(), UINT16_MAX)

        errors = []
        if not ok_id:
            errors.append("Motor ID must be 0–255")
        if not ok_pos:
            errors.append("Position must be 0–65535")
        if not ok_mt:
            errors.append("Move Time must be 0–65535")
        if errors:
            self._status_var.set(" | ".join(errors))
            return

        try:
            port = int(self._port.get().strip())
        except ValueError:
            self._status_var.set("Port must be an integer")
            return

        success, msg = _send_grpc(self._ip.get().strip(), port, motor_id, position, move_time)
        self._status_var.set(f"OK — {msg}" if success else f"Error: {msg}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Robo Arm Control GUI")
    parser.add_argument("--web", action="store_true", help="Serve as a webpage on port 6001")
    args = parser.parse_args()

    if args.web:
        run_web()
    else:
        RoboArmGui().mainloop()
