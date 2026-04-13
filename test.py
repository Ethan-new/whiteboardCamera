#!/usr/bin/env python3
"""Take one still with the Pi Camera and save it under ./pipics."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import sleep


def main() -> None:
    out_dir = Path("pipics")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = out_dir / f"capture_{stamp}.jpg"

    try:
        from picamera2 import Picamera2
    except ImportError as exc:
        raise SystemExit(
            "picamera2 is required on Raspberry Pi OS. "
            "Install: sudo apt install python3-picamera2"
        ) from exc

    camera = Picamera2()
    camera.configure(camera.create_still_configuration())
    camera.start()
    sleep(1)  # let exposure settle
    camera.capture_file(str(output_path))
    camera.stop()

    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
