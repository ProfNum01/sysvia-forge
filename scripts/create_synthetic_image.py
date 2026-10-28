"""Original procedural test image, clearly labeled synthetic; never a mock model response."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1] / "data" / "synthetic-preparation.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1200, 760), "#e5e9ef")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 36)
        small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
    except OSError:
        font = ImageFont.load_default(size=36)
        small = ImageFont.load_default(size=20)
    draw.text((34, 24), "ORIGINAL SYNTHETIC TEST FIXTURE", font=font, fill="#172335")
    draw.text((34, 80), "Procedural shapes and labels. Not a warehouse photograph.", font=small, fill="#344054")
    draw.rectangle((0, 590, 1200, 760), fill="#bec7d4")
    draw.rounded_rectangle((185, 198, 450, 590), radius=22, fill="#d83238", outline="#9d2028", width=5)
    draw.rectangle((260, 163, 374, 205), fill="#9b1c24")
    draw.rounded_rectangle((208, 335, 430, 425), radius=5, fill="white")
    draw.text((218, 360), "PS-RED-01", font=font, fill="#111111")
    draw.text((232, 462), "UTILITY", font=small, fill="white")
    draw.rectangle((695, 295, 1010, 590), fill="#215fcc", outline="#163e93", width=5)
    draw.polygon([(695,295),(760,245),(1075,245),(1010,295)], fill="#5e8feb")
    draw.polygon([(1010,295),(1075,245),(1075,540),(1010,590)], fill="#153e92")
    draw.rectangle((727, 365, 987, 445), fill="white")
    draw.text((737, 387), "PS-BLUE-02", font=font, fill="#111111")
    draw.text((34, 690), "Rights: original locally generated synthetic fixture · no external imagery", font=small, fill="#172335")
    image.save(destination, "PNG")
    print("Created data/synthetic-preparation.png (original synthetic test image; no inspection results).")
