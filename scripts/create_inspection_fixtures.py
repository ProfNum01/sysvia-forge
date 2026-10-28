"""Generate original synthetic scenario images, never model responses or real photos."""
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.services.catalog import REFERENCE_CATALOG


def render_scene(destination: Path, variant: str):
    units = {"missing": ["product-red", "product-blue"],
             "correct": ["product-red", "product-red", "product-blue"],
             "extra": ["product-red", "product-red", "product-blue", "product-green"],
             "ambiguous": ["product-red", "product-blue"],
             "unidentified": ["product-red", "product-blue", None]}[variant]
    image = Image.new("RGB", (1000, 1000), "#e5e9ef")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
        small = ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        font = ImageFont.load_default(size=24)
        small = ImageFont.load_default(size=16)
    draw.text((30, 24), "ORIGINAL SYNTHETIC INSPECTION FIXTURE", font=font, fill="#172335")
    draw.text((30, 70), "Locally drawn test scene. Not a warehouse photograph.", font=small, fill="#344054")
    draw.rectangle((20, 130, 980, 920), fill="#d0d7e1", outline="#94a3b8", width=3)
    positions = [(120, 230), (620, 230)] if len(units) == 2 else [(120, 180), (620, 180), (120, 540), (620, 540)]
    for index, (pid, (x, y)) in enumerate(zip(units, positions)):
        if pid is None:
            draw.ellipse((x+20,y+25,x+240,y+260), fill="#76658d", outline="#413853", width=4)
            continue
        item = REFERENCE_CATALOG[pid]
        color, shape = item["color"], item["shape"]
        if shape == "canister":
            draw.rounded_rectangle((x,y+35,x+260,y+285), radius=18, fill=color, outline="#9d2028", width=4)
            draw.rectangle((x+75,y+5,x+185,y+40), fill="#9b1c24")
        elif shape == "box":
            draw.rectangle((x,y+80,x+260,y+285), fill=color, outline="#163e93", width=4)
            draw.polygon([(x,y+80),(x+45,y+40),(x+305,y+40),(x+260,y+80)], fill="#5e8feb")
            draw.polygon([(x+260,y+80),(x+305,y+40),(x+305,y+245),(x+260,y+285)], fill="#153e92")
        else:
            draw.polygon([(x+10,y+25),(x+250,y+25),(x+270,y+285),(x-10,y+285)], fill=color)
        label = item["sku"] if variant != "ambiguous" or index != 0 else "UNREADABLE"
        draw.rectangle((x+8,y+155,x+252,y+220), fill="white")
        bounds = draw.textbbox((0,0), label, font=font)
        draw.text((x+(260-bounds[2])/2,y+175), label, font=font, fill="#111111")
    draw.text((30, 948), "Rights: original procedural geometry and text. No external imagery.", font=small, fill="#172335")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return False
    image.save(destination, "PNG")
    return True


if __name__ == "__main__":
    folder = Path(__file__).resolve().parents[1] / "data" / "fixtures"
    count = sum(render_scene(folder / f"task002-{variant}.png", variant)
                for variant in ("missing", "correct", "extra", "ambiguous", "unidentified"))
    print(f"Created {count} original synthetic scenario images in data/fixtures/. Existing files preserved.")
