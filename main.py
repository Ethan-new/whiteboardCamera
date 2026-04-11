#!/usr/bin/env python3
"""
Minimal Raspberry Pi camera + OCR starter script.

Dependencies:
- picamera2
- pytesseract
- Pillow

Note: pytesseract also requires the Tesseract OCR system binary to be installed.
"""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep

import pytesseract
from PIL import Image, ImageChops, ImageFilter, ImageOps


def get_default_test_image() -> Path:
    test_dir = Path("testimgs")
    if not test_dir.exists():
        raise FileNotFoundError("Default test image directory not found: testimgs")

    image_files = sorted(
        [
            path
            for path in test_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
    )
    if not image_files:
        raise FileNotFoundError("No .jpg/.jpeg/.png images found in testimgs")

    return image_files[0]


def capture_image(output_path: Path) -> None:
    try:
        from picamera2 import Picamera2
    except ImportError as exc:
        raise RuntimeError(
            "picamera2 is only available on Linux (Raspberry Pi OS). "
            "Run capture on a Pi, or pass an existing image to OCR."
        ) from exc

    camera = Picamera2()
    camera.configure(camera.create_still_configuration())
    camera.start()
    sleep(1)  # let exposure settle
    camera.capture_file(str(output_path))
    camera.stop()


def parse_board_crop(crop: str) -> tuple[float, float, float, float]:
    try:
        left, top, right, bottom = (float(part.strip()) for part in crop.split(","))
    except ValueError as exc:
        raise ValueError(
            "Invalid --board-crop format. Use: left,top,right,bottom (fractions)."
        ) from exc

    fractions = (left, top, right, bottom)
    if any(value <= 0 or value >= 1 for value in fractions):
        raise ValueError("Board crop fractions must be between 0 and 1.")
    if not (left < right and top < bottom):
        raise ValueError("Board crop must satisfy left < right and top < bottom.")

    return fractions


def crop_board(image: Image.Image, crop_fractions: tuple[float, float, float, float]) -> Image.Image:
    width, height = image.size
    left, top, right, bottom = crop_fractions
    crop_box = (
        int(width * left),
        int(height * top),
        int(width * right),
        int(height * bottom),
    )
    return image.crop(crop_box)


def ocr_score(image_path: Path, config: str) -> tuple[float, str]:
    data = pytesseract.image_to_data(
        str(image_path),
        config=config,
        output_type=pytesseract.Output.DICT,
    )
    words = []
    for word, conf_str in zip(data["text"], data["conf"]):
        conf = float(conf_str)
        if not word.strip() or conf < 30 or len(word.strip()) < 2:
            continue
        words.append((word.strip(), conf))
    text = " ".join(w for w, _ in words)
    # Weight each word by its confidence and length — rewards finding
    # real multi-character words at high confidence over noise.
    score = sum(conf * len(w) for w, conf in words)
    return score, text


def run_ocr(
    image_path: Path,
    save_preprocessed: Path | None = None,
    compare_ocr: bool = False,
    board_crop: tuple[float, float, float, float] = (0.17, 0.14, 0.82, 0.82),
) -> str:
    ocr_configs = (
        "--oem 3 --psm 4",
        "--oem 3 --psm 6",
        "--oem 3 --psm 11",
    )

    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        with Image.open(image_path) as img:
            board = crop_board(img, board_crop)
            color_path = temp_dir_path / "board_color.png"
            board.save(color_path)

            # Min-channel grayscale: take the darkest RGB channel per pixel.
            # Standard grayscale weights green ~59%, making green marker text
            # nearly invisible on a white board. Min-channel ensures any
            # colored ink (green, red, blue) appears dark against white.
            r, g, b = board.split()
            gray = ImageChops.darker(ImageChops.darker(r, g), b)

            high_contrast = ImageOps.autocontrast(gray, cutoff=2)

            upscaled = high_contrast.resize(
                (high_contrast.width * 2, high_contrast.height * 2),
                Image.Resampling.LANCZOS,
            )
            upscaled = upscaled.filter(ImageFilter.SHARPEN)
            denoised = upscaled.filter(ImageFilter.MedianFilter(size=3))

            # Adaptive threshold: pixels darker than their local neighborhood
            # become black text; everything else becomes white background.
            gray_path = temp_dir_path / "board_gray.png"
            denoised.save(gray_path)

            local_mean = denoised.filter(ImageFilter.GaussianBlur(radius=20))
            diff = ImageChops.subtract(local_mean, denoised, scale=1, offset=0)
            binary = diff.point(lambda p: 0 if p > 18 else 255)
            preprocess_path = temp_dir_path / "board_binary.png"
            binary.save(preprocess_path)

        candidates: list[tuple[float, str, Path, str]] = []
        for candidate_image in (color_path, gray_path, preprocess_path):
            for config in ocr_configs:
                score, text = ocr_score(candidate_image, config)
                if text.strip():
                    candidates.append((score, text, candidate_image, config))

        if not candidates:
            return "(no text detected)"

        best_score, best_text, best_image_path, best_config = max(candidates, key=lambda item: item[0])

        if compare_ocr:
            raw_score, raw_text = ocr_score(image_path, "--oem 3 --psm 6")
            print(f"Raw OCR chars: {len(raw_text.strip())} (score: {raw_score:.2f})")
            print(f"Best board OCR chars: {len(best_text.strip())} (score: {best_score:.2f})")
            print(f"Best OCR source: {best_image_path.name} with config '{best_config}'")

        if save_preprocessed is not None:
            save_preprocessed.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(best_image_path) as best_image:
                best_image.save(save_preprocessed)
            if compare_ocr:
                print(f"Saved best OCR source image to: {save_preprocessed}")

        return best_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture an image and run OCR.")
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Capture a new image with Pi camera before running OCR.",
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="Path to an existing image file for OCR (defaults to first image in testimgs).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("capture.jpg"),
        help="Captured image output path when using --capture.",
    )
    parser.add_argument(
        "--save-preprocessed",
        type=Path,
        help="Save the preprocessed image to disk so you can inspect it.",
    )
    parser.add_argument(
        "--compare-ocr",
        action="store_true",
        help="Print character counts for raw OCR vs preprocessed OCR.",
    )
    parser.add_argument(
        "--board-crop",
        type=str,
        default="0.17,0.14,0.82,0.82",
        help="Whiteboard crop fractions as left,top,right,bottom.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.capture:
        image_path = args.output
        capture_image(image_path)
    else:
        image_path = args.image or get_default_test_image()
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

    text = run_ocr(
        image_path,
        save_preprocessed=args.save_preprocessed,
        compare_ocr=args.compare_ocr,
        board_crop=parse_board_crop(args.board_crop),
    )
    print("OCR result:")
    print(text.strip())


if __name__ == "__main__":
    main()
