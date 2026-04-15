"""Test script for Waveshare 2inch LCD (240x320, ST7789V, SPI).

Wiring (Raspberry Pi, BCM numbering):
    VCC -> 3.3V       (Pin 1)
    GND -> GND        (Pin 6)
    DIN -> GPIO 10    (Pin 19, MOSI)
    CLK -> GPIO 11    (Pin 23, SCLK)
    CS  -> GPIO 8     (Pin 24, CE0)
    DC  -> GPIO 25    (Pin 22)
    RST -> GPIO 27    (Pin 13)
    BL  -> GPIO 18    (Pin 12)

Requires: spidev, RPi.GPIO (or lgpio on Pi 5), Pillow
    sudo apt install python3-rpi.gpio python3-spidev python3-pil
"""

import time
import spidev
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont

RST_PIN = 27
DC_PIN = 25
BL_PIN = 18

WIDTH = 240
HEIGHT = 320


class LCD2inch:
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(RST_PIN, GPIO.OUT)
        GPIO.setup(DC_PIN, GPIO.OUT)
        GPIO.setup(BL_PIN, GPIO.OUT)
        GPIO.output(BL_PIN, GPIO.HIGH)

        self.spi = spidev.SpiDev(0, 0)
        self.spi.max_speed_hz = 20000000
        self.spi.mode = 0b00

        self.reset()
        self.init_display()

    def reset(self):
        GPIO.output(RST_PIN, GPIO.HIGH)
        time.sleep(0.02)
        GPIO.output(RST_PIN, GPIO.LOW)
        time.sleep(0.02)
        GPIO.output(RST_PIN, GPIO.HIGH)
        time.sleep(0.02)

    def cmd(self, c):
        GPIO.output(DC_PIN, GPIO.LOW)
        self.spi.writebytes([c])

    def data(self, d):
        GPIO.output(DC_PIN, GPIO.HIGH)
        if isinstance(d, int):
            self.spi.writebytes([d])
        else:
            for i in range(0, len(d), 4096):
                self.spi.writebytes2(d[i:i + 4096])

    def init_display(self):
        # Waveshare 2inch LCD reference init sequence
        self.cmd(0x36); self.data(0x00)
        self.cmd(0x3A); self.data(0x05)

        self.cmd(0x21)

        self.cmd(0x2A)
        self.data(0x00); self.data(0x00); self.data(0x01); self.data(0x3F)

        self.cmd(0x2B)
        self.data(0x00); self.data(0x00); self.data(0x00); self.data(0xEF)

        self.cmd(0xB2)
        for v in (0x0C, 0x0C, 0x00, 0x33, 0x33):
            self.data(v)

        self.cmd(0xB7); self.data(0x35)
        self.cmd(0xBB); self.data(0x1F)
        self.cmd(0xC0); self.data(0x2C)
        self.cmd(0xC2); self.data(0x01)
        self.cmd(0xC3); self.data(0x12)
        self.cmd(0xC4); self.data(0x20)
        self.cmd(0xC6); self.data(0x0F)
        self.cmd(0xD0); self.data(0xA4); self.data(0xA1)

        self.cmd(0xE0)
        for v in (0xD0, 0x08, 0x11, 0x08, 0x0C, 0x15, 0x39,
                  0x33, 0x50, 0x36, 0x13, 0x14, 0x29, 0x2D):
            self.data(v)

        self.cmd(0xE1)
        for v in (0xD0, 0x08, 0x10, 0x08, 0x06, 0x06, 0x39,
                  0x44, 0x51, 0x0B, 0x16, 0x14, 0x2F, 0x31):
            self.data(v)

        self.cmd(0x21)
        self.cmd(0x11)
        time.sleep(0.12)
        self.cmd(0x29)

    def set_window(self, x0, y0, x1, y1):
        self.cmd(0x2A)
        self.data(x0 >> 8); self.data(x0 & 0xFF)
        self.data(x1 >> 8); self.data(x1 & 0xFF)
        self.cmd(0x2B)
        self.data(y0 >> 8); self.data(y0 & 0xFF)
        self.data(y1 >> 8); self.data(y1 & 0xFF)
        self.cmd(0x2C)

    def show(self, image):
        if image.size != (WIDTH, HEIGHT):
            image = image.resize((WIDTH, HEIGHT))
        img = image.convert("RGB")
        # Pack to RGB565 big-endian using numpy-free approach via bytes()
        pixels = img.tobytes()  # RGB, 3 bytes per pixel
        out = bytearray(WIDTH * HEIGHT * 2)
        j = 0
        for i in range(0, len(pixels), 3):
            r = pixels[i]
            g = pixels[i + 1]
            b = pixels[i + 2]
            rgb = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            out[j] = rgb >> 8
            out[j + 1] = rgb & 0xFF
            j += 2

        self.set_window(0, 0, WIDTH - 1, HEIGHT - 1)
        GPIO.output(DC_PIN, GPIO.HIGH)
        chunk = 4096
        for i in range(0, len(out), chunk):
            self.spi.writebytes2(out[i:i + chunk])

    def clear(self, color=(0, 0, 0)):
        self.show(Image.new("RGB", (WIDTH, HEIGHT), color))

    def cleanup(self):
        self.spi.close()
        GPIO.output(BL_PIN, GPIO.LOW)
        GPIO.cleanup()


def backlight_test():
    """Blink BL pin so you can confirm wiring before SPI init."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(BL_PIN, GPIO.OUT)
    print("Blinking backlight 3x — watch the screen glow...")
    for _ in range(3):
        GPIO.output(BL_PIN, GPIO.HIGH)
        time.sleep(0.4)
        GPIO.output(BL_PIN, GPIO.LOW)
        time.sleep(0.4)
    GPIO.output(BL_PIN, GPIO.HIGH)


def main():
    backlight_test()
    input("Did the backlight blink? Press Enter to continue with display test... ")

    lcd = LCD2inch()
    try:
        print("Filling RED...")
        lcd.clear((255, 0, 0)); time.sleep(1)
        print("Filling GREEN...")
        lcd.clear((0, 255, 0)); time.sleep(1)
        print("Filling BLUE...")
        lcd.clear((0, 0, 255)); time.sleep(1)

        print("Drawing shapes pattern...")
        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle((10, 10, WIDTH - 10, HEIGHT - 10),
                       outline=(255, 255, 255), width=2)
        draw.line((0, 0, WIDTH, HEIGHT), fill=(255, 255, 0), width=2)
        draw.line((WIDTH, 0, 0, HEIGHT), fill=(0, 255, 255), width=2)
        draw.ellipse((60, 110, 180, 210), outline=(255, 0, 255), width=2)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except OSError:
            font = ImageFont.load_default()
        draw.text((60, 260), "LCD OK", fill=(0, 255, 0), font=font)
        lcd.show(img)
        time.sleep(3)
    finally:
        lcd.cleanup()


if __name__ == "__main__":
    main()
