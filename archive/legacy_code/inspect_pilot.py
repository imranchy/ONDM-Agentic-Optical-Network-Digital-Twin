
from pathlib import Path
import random

import matplotlib.pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "optical_topology_v2_pilot" / "images"
OUTPUT = ROOT / "results" / "figures"
OUTPUT.mkdir(parents=True, exist_ok=True)

image_files = sorted(IMAGES.glob("*.png"))

if not image_files:
    raise RuntimeError(f"No images found in {IMAGES}")

rng = random.Random(2027)
selected = rng.sample(image_files, min(12, len(image_files)))

fig, axes = plt.subplots(3, 4, figsize=(16, 12))

for ax in axes.flat:
    ax.axis("off")

for ax, image_path in zip(axes.flat, selected):
    with Image.open(image_path) as img:
        ax.imshow(img.convert("RGB"))
    ax.set_title(image_path.stem, fontsize=11)
    ax.axis("off")

fig.suptitle(
    "ONDM 2027 — Optical Topology Generation Pilot",
    fontsize=17,
    fontweight="bold",
)

plt.tight_layout()

output_file = OUTPUT / "v2_pilot_contact_sheet.png"

plt.savefig(
    output_file,
    dpi=200,
    bbox_inches="tight",
)

plt.show()

print(f"Saved contact sheet: {output_file}")
