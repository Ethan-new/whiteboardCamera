"""Capture a photo with the Pi camera and display it on the Waveshare 2inch LCD.

Wiring: see debug/test_lcd.py
Requires: picamera2, spidev, RPi.GPIO, Pillow
"""

import time
from pathlib import Path

from PIL import Image

from test_lcd import LCD2inch, WIDTH, HEIGHT


def capture(output_path: Path) -> Path:
    from picamera2 import Picamera2

    camera = Picamera2()
    camera.configure(camera.create_still_configuration())
    camera.start()
    time.sleep(1)  # let auto-exposure settle
    camera.capture_file(str(output_path))
    camera.stop()
    camera.close()
    return output_path


def fit_to_screen(image: Image.Image) -> Image.Image:
    """Rotate (if landscape) and letterbox into 240x320."""
    img = image.convert("RGB")
    if img.width > img.height:
        img = img.rotate(90, expand=True)

    scale = min(WIDTH / img.width, HEIGHT / img.height)
    new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    resized = img.resize(new_size, Image.LANCZOS)

    canvas = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    offset = ((WIDTH - new_size[0]) // 2, (HEIGHT - new_size[1]) // 2)
    canvas.paste(resized, offset)
    return canvas


def main():
    out_dir = Path(__file__).parent
    photo_path = out_dir / "lcd_camera_test.jpg"

    print(f"Capturing photo to {photo_path}...")
    capture(photo_path)

    print("Initializing LCD...")
    lcd = LCD2inch()
    try:
        print("Displaying photo...")
        img = Image.open(photo_path)
        lcd.show(fit_to_screen(img))
        time.sleep(5)
    finally:
        lcd.cleanup()


if __name__ == "__main__":
    main()
