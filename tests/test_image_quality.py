import io
import unittest
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from backend.app.services.image_quality import analyze_image_quality


def sample(image):
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class ImageQualityTests(unittest.TestCase):
    def test_existing_scene_and_controlled_variations(self):
        source = Path("evaluation/datasets/synthetic-packing/01_missing_product_before.png")
        with Image.open(source) as opened:
            image = opened.convert("RGB")
        self.assertEqual(analyze_image_quality(sample(image))["quality_status"], "ACCEPTABLE")
        self.assertEqual(analyze_image_quality(sample(ImageEnhance.Brightness(image).enhance(.8)))["quality_status"], "ACCEPTABLE")
        self.assertIn("LOW_LIGHT", analyze_image_quality(sample(ImageEnhance.Brightness(image).enhance(.1)))["issues"])
        self.assertIn("EXCESSIVE_BLUR", analyze_image_quality(sample(image.filter(ImageFilter.GaussianBlur(12))))["issues"])
        obstructed = image.copy()
        ImageDraw.Draw(obstructed).rectangle((600, 300, 1000, 650), fill=(90, 90, 90))
        self.assertNotIn("LOW_RESOLUTION", analyze_image_quality(sample(obstructed))["issues"])

    def test_clear_photo_is_not_rejected(self):
        image = Image.new("RGB", (512, 512), "white")
        for x in range(100, 400):
            for y in range(100, 400):
                image.putpixel((x, y), (15, 70, 160) if (x // 12 + y // 12) % 2 else (210, 30, 40))
        result = analyze_image_quality(sample(image), min_side=256)
        self.assertEqual(result["quality_status"], "ACCEPTABLE")

    def test_low_resolution_is_decisive(self):
        result = analyze_image_quality(sample(Image.new("RGB", (64, 64), "gray")), min_side=256)
        self.assertEqual(result["quality_status"], "RETAKE_RECOMMENDED")
        self.assertIn("LOW_RESOLUTION", result["issues"])

    def test_dark_and_bright_frames(self):
        dark = analyze_image_quality(sample(Image.new("RGB", (512, 512), (5, 5, 5))))
        bright = analyze_image_quality(sample(Image.new("RGB", (512, 512), "white")))
        self.assertIn("LOW_LIGHT", dark["issues"])
        self.assertIn("OVEREXPOSED", bright["issues"])

    def test_invalid_bytes_fail_safely(self):
        self.assertEqual(analyze_image_quality(b"invalid")["quality_status"], "TECHNICAL_FAILURE")

    def test_blurred_pattern_requires_review(self):
        image = Image.new("RGB", (512, 512))
        pixels = image.load()
        for x in range(512):
            for y in range(512):
                pixels[x, y] = (20, 20, 20) if (x // 12 + y // 12) % 2 else (220, 220, 220)
        result = analyze_image_quality(sample(image.filter(ImageFilter.GaussianBlur(12))))
        self.assertIn("EXCESSIVE_BLUR", result["issues"])
        self.assertEqual(result["quality_status"], "NEEDS_HUMAN_REVIEW")

    def test_potential_glare_is_warning_only(self):
        image = Image.new("RGB", (512, 512), (220, 220, 220))
        for x in range(100, 230):
            for y in range(100, 230):
                image.putpixel((x, y), (255, 255, 255))
        result = analyze_image_quality(sample(image))
        self.assertIn("POTENTIAL_GLARE", result["issues"])
        self.assertNotEqual(result["quality_status"], "RETAKE_RECOMMENDED")
