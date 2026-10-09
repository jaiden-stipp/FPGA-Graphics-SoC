#!/usr/bin/env python3
"""Send keyboard state to the SoC's existing UDP transport (Windows, no packages)."""
import argparse
import binascii
import ctypes
import os
import secrets
import socket
import struct
import time


def packet(frame_id, sequence, buttons):
    if not 0 <= buttons < 32:
        raise ValueError("Only five control bits are defined")
    command = b"GF" + bytes((2, 4, 4, 255, 0x4b, sequence & 255, buttons))
    command += struct.pack(">H", binascii.crc_hqx(command, 0xffff))
    return struct.pack(">2sBBIHH", b"GP", 2, 3, frame_id & 0xffffffff, 0, len(command)) + command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", default="192.168.7.2")
    parser.add_argument("--port", type=int, default=4000)
    parser.add_argument("--buttons", type=lambda s: int(s, 0), help="Send a fixed mask for network checks")
    parser.add_argument("--seconds", type=float, help="Stop automatically after this duration")
    parser.add_argument("--layout", choices=["mario", "quake", "scene"], default="mario",
                        help="Mario: move/jump; Quake: turn/walk/jump; scene: orbit/zoom")
    args = parser.parse_args()
    if args.buttons is None and os.name != "nt":
        parser.error("Live keyboard polling needs Windows; fixed --buttons works on other systems")
    if args.buttons is not None and not 0 <= args.buttons < 32:
        parser.error("--buttons must be between 0 and 31")
    if args.seconds is not None and args.seconds <= 0:
        parser.error("--seconds must be positive")
    if args.buttons is None:
        keys = ctypes.WinDLL("user32", use_last_error=True).GetAsyncKeyState
        keys.argtypes = (ctypes.c_int,)
        keys.restype = ctypes.c_short
        pressed = lambda key: bool(keys(key) & 0x8000)
    target = (args.ip, args.port)
    frame, sequence = secrets.randbits(32), 0
    replies, accepted = 0, 0
    print(f"Sending controls to {args.ip}:{args.port} at 60 Hz.")
    print("WASD/arrows: move; Space: jump; R: respawn." if args.layout == "mario" else
          "A/D or Left/Right: turn; W/S or Up/Down: walk; Space: jump; R: respawn." if args.layout == "quake" else
          "A/Left: orbit left; D/Right: orbit right; W/Up: zoom in; S/Down: zoom out; R: reset view.")
    print("Windows keys are global while this sender runs. Esc or Ctrl+C stops it.")
    start, next_tick = time.monotonic(), time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("", 0))
        sock.setblocking(False)
        try:
            while args.seconds is None or time.monotonic() - start < args.seconds:
                if args.buttons is None:
                    if pressed(0x1b):
                        break
                    mask = ((pressed(0x41) or pressed(0x25)) |
                            ((pressed(0x44) or pressed(0x27)) << 1) |
                            ((pressed(0x57) or pressed(0x26)) << 2) |
                            ((pressed(0x53) or pressed(0x28)) << 3) |
                            (pressed(0x20 if args.layout in ("mario","quake") else 0x52) << 4))
                    if args.layout in ("mario","quake") and pressed(0x52):
                        mask = 15  # Existing directional chord, no FPGA protocol change.
                else:
                    mask = args.buttons
                sock.sendto(packet(frame, sequence, mask), target)
                frame = (frame + 1) & 0xffffffff
                sequence = (sequence + 1) & 255
                # Drain packet acknowledgements; sending never waits on a reply.
                while True:
                    try:
                        data, peer = sock.recvfrom(2048)
                        if peer[0] == args.ip and peer[1] == args.port and len(data) == 20 and data[:4] == b"GS\x02\x01":
                            replies += 1
                            accepted += bool(struct.unpack_from(">I", data, 12)[0] & 1)
                    except (BlockingIOError, ConnectionResetError):
                        break
                next_tick += 1/60
                time.sleep(max(0, next_tick - time.monotonic()))
                if time.monotonic() - next_tick > 0.1:
                    next_tick = time.monotonic()
        except KeyboardInterrupt:
            pass
        finally:
            for _ in range(3):
                sock.sendto(packet(frame, sequence, 0), target)
                frame = (frame + 1) & 0xffffffff
                sequence = (sequence + 1) & 255
                time.sleep(1/60)
    print(f"Stopped; {replies} packet replies, {accepted} accepted. FPGA releases keys after 300 ms without input.")


if __name__ == "__main__":
    main()
