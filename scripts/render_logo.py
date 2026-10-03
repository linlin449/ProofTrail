"""Render the code-native ProofTrail mark as a submission-ready PNG (no AI raster edit)."""

from pathlib import Path

from PIL import Image, ImageDraw

scale = 16
image = Image.new("RGB", (1024, 1024), "#eaf0f7")
draw = ImageDraw.Draw(image)


def box(values):
    return tuple(value * scale for value in values)


draw.rounded_rectangle(box((2, 2, 62, 62)), radius=15 * scale, fill="#193447")
draw.line(box((19, 46, 19, 18, 33, 18)), fill="#edf4fb", width=6 * scale, joint="curve")
draw.arc(box((22, 18, 44, 40)), start=270, end=90, fill="#edf4fb", width=6 * scale)
draw.line(box((33, 40, 26, 40)), fill="#edf4fb", width=6 * scale)
draw.line(box((34, 46, 41, 52, 53, 36)), fill="#8bd3c3", width=5 * scale, joint="curve")
for x, y in ((34, 46), (41, 52), (53, 36)):
    draw.ellipse(box((x - 2.5, y - 2.5, x + 2.5, y + 2.5)), fill="#8bd3c3")
output = Path("assets/logo-1024.png")
output.parent.mkdir(exist_ok=True)
image.save(output, optimize=True)
assert output.stat().st_size < 2 * 1024 * 1024
print(f"Saved {output}: 1024×1024 RGB, {output.stat().st_size} bytes")
