#!/usr/bin/env python3
"""Capture a photo once per hour and send it to Claude for analysis."""

import base64
import os
import sys
from datetime import datetime
from pathlib import Path
from time import sleep

from anthropic import Anthropic
from dotenv import load_dotenv

from main import capture_image

CAPTURE_INTERVAL_SECONDS = 60 * 60
CAPTURE_DIR = Path("pipics")
MODEL = "claude-opus-4-5"
PROMPT = (
    "This is a photo of a whiteboard. Transcribe any text or diagrams you see "
    "and briefly summarize the content."
)


def upload_to_claude(client: Anthropic, image_path: Path) -> str:
    image_bytes = image_path.read_bytes()
    encoded = base64.standard_b64encode(image_bytes).decode("utf-8")
    suffix = image_path.suffix.lower().lstrip(".")
    media_type = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix}"

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded,
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def run_once(client: Anthropic) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = CAPTURE_DIR / f"capture_{timestamp}.jpg"

    print(f"[{timestamp}] Capturing image to {image_path}")
    capture_image(image_path)

    print(f"[{timestamp}] Uploading to Claude ({MODEL})")
    response = upload_to_claude(client, image_path)
    print(f"[{timestamp}] Claude response:\n{response}\n")


def main() -> None:
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set. Add it to .env")

    client = Anthropic(api_key=api_key)

    while True:
        try:
            run_once(client)
        except Exception as exc:
            print(f"Error during capture/upload: {exc}", file=sys.stderr)
        sleep(CAPTURE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
