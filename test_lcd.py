"""Test script for Waveshare 2inch LCD (240x320, ST7789V, SPI).

Wiring (Raspberry Pi, BCM numbering):
    VCC -> 3.3V
    GND -> GND
    DIN -> GPIO 10 (MOSI)
    CLK -> GPIO 11 (SCLK)
    CS  -> GPIO 8  (CE0)
    DC  -> GPIO 25
    RST -> GPIO 27
    BL  -> GPIO 18

Requires: spidev, RPi.GPIO, Pillow
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

        self.spi = spidev.SpiDev(0, 0)
        self.spi.max_speed_hz = 40000000
        self.spi.mode = 0b00

        GPIO.output(BL_PIN, GPIO.HIGH)

        self.reset()
        self.init_display()

    def reset(self):
        GPIO.output(RST_PIN, GPIO.HIGH)
        time.sleep(0.01)
        GPIO.output(RST_PIN, GPIO.LOW)
        time.sleep(0.01)
        GPIO.output(RST_PIN, GPIO.HIGH)
        time.sleep(0.01)

    def cmd(self, c):
        GPIO.output(DC_PIN, GPIO.LOW)
        self.spi.writebytes([c])

    def data(self, d):
        GPIO.output(DC_PIN, GPIO.HIGH)
        if isinstance(d, int):
            self.spi.writebytes([d])
        else:
            for i in range(0, len(d), 4096):
                self.spi.writebytes(list(d[i:i + 4096]))

    def init_display(self):
        self.cmd(0x36); self.data(0x00)
        self.cmd(0x3A); self.data(0x05)

        self.cmd(0xB2)
        for v in (0x0C, 0x0C, 0x00, 0x33, 0x33):
            self.data(v)

        self.cmd(0xB7); self.data(0x35)
        self.cmd(0xBB); self.data(0x19)
        self.cmd(0xC0); self.data(0x2C)
        self.cmd(0xC2); self.data(0x01)
        self.cmd(0xC3); self.data(0x12)
        self.cmd(0xC4); self.data(0x20)
        self.cmd(0xC6); self.data(0x0F)
        self.cmd(0xD0); self.data(0xA4); self.data(0xA1)

        self.cmd(0xE0)
        for v in (0xD0, 0x04, 0x0D, 0x11, 0x13, 0x2B, 0x3F,
                  0x54, 0x4C, 0x18, 0x0D, 0x0B, 0x1F, 0x23):
            self.data(v)

        self.cmd(0xE1)
        for v in (0xD0, 0x04, 0x0C, 0x11, 0x13, 0x2C, 0x3F,
                  0x44, 0x51, 0x2F, 0x1F, 0x1F, 0x20, 0x23):
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
        pixels = img.load()
        buf = bytearray(WIDTH * HEIGHT * 2)
        idx = 0
        for y in range(HEIGHT):
            for x in range(WIDTH):
                r, g, b = pixels[x, y]
                rgb = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                buf[idx] = rgb >> 8
                buf[idx + 1] = rgb & 0xFF
                idx += 2
        self.set_window(0, 0, WIDTH - 1, HEIGHT - 1)
        GPIO.output(DC_PIN, GPIO.HIGH)
        for i in range(0, len(buf), 4096):
            self.spi.writebytes(list(buf[i:i + 4096]))

    def clear(self, color=(0, 0, 0)):
        self.show(Image.new("RGB", (WIDTH, HEIGHT), color))

    def cleanup(self):
        self.spi.close()
        GPIO.output(BL_PIN, GPIO.LOW)
        GPIO.cleanup()


def main():
    lcd = LCD2inch()
    try:
        for color, name in [((255, 0, 0), "RED"),
                            ((0, 255, 0), "GREEN"),
                            ((0, 0, 255), "BLUE")]:
            img = Image.new("RGB", (WIDTH, HEIGHT), color)
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            except OSError:
                font = ImageFont.load_default()
            draw.text((40, 140), name, fill=(255, 255, 255), font=font)
            lcd.show(img)
            time.sleep(1)

        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle((10, 10, WIDTH - 10, HEIGHT - 10), outline=(255, 255, 255), width=2)
        draw.line((0, 0, WIDTH, HEIGHT), fill=(255, 255, 0), width=2)
        draw.line((WIDTH, 0, 0, HEIGHT), fill=(0, 255, 255), width=2)
        draw.ellipse((60, 110, 180, 210), outline=(255, 0, 255), width=2)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except OSError:
            font = ImageFont.load_default()
        draw.text((30, 260), "LCD OK", fill=(0, 255, 0), font=font)
        lcd.show(img)
        time.sleep(3)
    finally:
        lcd.cleanup()


if __name__ == "__main__":
    main()
