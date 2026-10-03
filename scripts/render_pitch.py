"""Code-native pitch artwork + local synthetic narration. Review draft, never a fake screen recording."""

import hashlib
import json
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/pitch"
OUTPUT.mkdir(parents=True, exist_ok=True)
SCENES = json.loads((ROOT / "assets/pitch-scenes.json").read_text("utf-8"))
FONTS = Path("C:/Windows/Fonts")
INK, MUTED, PAPER = "#193447", "#617789", "#EAF0F7"
VIOLET, MINT, RED = "#7162DE", "#1A8277", "#B2534E"


def font(size, bold=False, mono=False):
    filename = "consola.ttf" if mono else "msyhbd.ttc" if bold else "msyh.ttc"
    return ImageFont.truetype(str(FONTS / filename), size)


def wrapped(draw, text, xy, size, width, fill=INK, bold=False, spacing=12):
    face = font(size, bold)
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        # Word wrapping for English subtitles; character wrapping for Chinese artwork.
        words = paragraph.split(" ") if paragraph.isascii() else list(paragraph)
        joiner = " " if paragraph.isascii() else ""
        for word in words:
            candidate = line + (joiner if line else "") + word
            if line and draw.textlength(candidate, font=face) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    for index, line in enumerate(lines):
        draw.text((xy[0], xy[1] + index * (size + spacing)), line, font=face, fill=fill)
    return len(lines) * (size + spacing)


def box(draw, rect, fill="#FFFFFF", outline=None, radius=22):
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=2)


def artwork(scene, number):
    image = Image.new("RGB", (1920, 1080), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((92, 56), "ProofTrail", font=font(36, True), fill=INK)
    draw.text(
        (1180, 64), "SYNTHETIC NARRATION / REVIEW DRAFT", font=font(23, mono=True), fill=MUTED
    )
    draw.line((92, 123, 1828, 123), fill="#CCD8E5", width=2)
    draw.text((92, 182), scene["tag"], font=font(25, mono=True), fill=VIOLET)
    wrapped(draw, scene["title"], (92, 262), 82, 895, bold=True, spacing=20)
    wrapped(draw, scene["body"], (96, 528), 35, 860, fill=MUTED, spacing=17)
    left, top, right, bottom = 1060, 218, 1828, 775
    box(draw, (left, top, right, bottom))
    visual = scene["visual"]
    if visual == "receipt":
        draw.text((1110, 263), "PORTABLE / RECEIPT", font=font(26, mono=True), fill=MUTED)
        for i, (label, value) in enumerate(
            [
                ("ISSUER", "Signed claim"),
                ("CONTENT", "Original bytes"),
                ("ANCHOR", "Merkle inclusion"),
                ("LIFECYCLE", "Revocation state"),
            ]
        ):
            y = 348 + i * 83
            draw.text((1110, y), label, font=font(23, mono=True), fill=MUTED)
            draw.text((1350, y - 5), value, font=font(29, True), fill=INK)
            draw.line((1110, y + 54, 1778, y + 54), fill=PAPER, width=2)
    elif visual == "flow":
        for i, (label, detail, color) in enumerate(
            [
                ("APP A", "Research Studio", VIOLET),
                ("JSON", "Signed receipt", INK),
                ("APP B", "Knowledge Publisher", MINT),
            ]
        ):
            y = 270 + i * 152
            box(draw, (1110, y, 1778, y + 110), fill="#F3F6FA")
            draw.text((1140, y + 22), label, font=font(29, mono=True), fill=color)
            draw.text((1290, y + 21), detail, font=font(29), fill=INK)
            if i < 2:
                draw.line((1444, y + 114, 1444, y + 148), fill=color, width=4)
    elif visual == "states":
        for i, (label, detail, color) in enumerate(
            [
                ("INTACT", "Private preview allowed", MINT),
                ("CHANGED", "Content mismatch", RED),
                ("REVOKED", "Preview refused", RED),
            ]
        ):
            y = 282 + i * 147
            draw.ellipse((1112, y, 1140, y + 28), fill=color)
            draw.text((1170, y - 6), label, font=font(29, mono=True), fill=color)
            draw.text((1170, y + 46), detail, font=font(29), fill=INK)
    elif visual == "batch":
        draw.text((1110, 265), "32 RECEIPTS", font=font(44, True), fill=INK)
        for i in range(32):
            x, y = 1110 + (i % 8) * 78, 353 + (i // 8) * 56
            box(draw, (x, y, x + 57, y + 34), fill="#DCD6F6", radius=6)
        draw.text((1110, 603), "1 REGISTRATION", font=font(38, True), fill=VIOLET)
        draw.text((1110, 674), "~2,758 GAS / RECEIPT", font=font(28, mono=True), fill=MINT)
    elif visual == "sdk":
        draw.text((1110, 265), "PYTHON / SDK", font=font(30, mono=True), fill=VIOLET)
        code = [
            "receipt = create_receipt(...)",
            "bundle = build_batch(...)[0]",
            "registry.anchor(...)",
            "",
            "# Independent consumer",
            "result = verify_receipt(...)",
            "if result.status == 'valid':",
            "    preview(content)",
        ]
        for i, line in enumerate(code):
            draw.text(
                (1110, 346 + i * 43),
                line,
                font=font(25, mono=True),
                fill=MUTED if line.startswith("#") else INK,
            )
    else:
        draw.text((1110, 268), "READY FOR LOCAL REVIEW", font=font(27, mono=True), fill=MINT)
        wrapped(draw, "SDK / 两款应用\n70 项测试 / 中文文档", (1110, 335), 36, 650, bold=True)
        draw.line((1110, 477, 1778, 477), fill=PAPER, width=3)
        draw.text((1110, 513), "NEXT / NOT YET COMPLETE", font=font(27, mono=True), fill=VIOLET)
        wrapped(draw, "公开产品 / GitHub\n最终技术视频 / 用户检查", (1110, 580), 34, 650)
    box(draw, (70, 823, 1850, 1013), fill=INK)
    used = wrapped(draw, scene["english"], (104, 846), 33, 1705, fill="#F6FAFF", spacing=9)
    if used > 158:
        raise ValueError("Subtitle exceeds safe frame region")
    draw.text(
        (96, 1031),
        "MONAD TESTNET · Exact-match source verified · Provenance is not factual truth",
        font=font(21),
        fill=MUTED,
    )
    draw.text((1780, 1031), f"{number}/6", font=font(23, mono=True), fill=MUTED)
    image.save(OUTPUT / f"scene-{number:02}.png")


def timecode(seconds):
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


durations = []
for index, scene in enumerate(SCENES, 1):
    artwork(scene, index)
    with wave.open(str(OUTPUT / f"scene-{index:02}.wav")) as audio:
        durations.append(audio.getnframes() / audio.getframerate() + 0.7)
total = sum(durations)
if total > 119:
    raise SystemExit(
        f"Pitch {total:.2f}s exceeds the safe 119s limit; shorten narration and regenerate."
    )
subtitles, position = [], 0.0
for index, (scene, duration) in enumerate(zip(SCENES, durations, strict=True), 1):
    subtitles.append(
        f"{index}\n{timecode(position)} --> {timecode(position + duration)}\n{scene['english']}\n"
    )
    position += duration
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-framerate",
            "24",
            "-i",
            str(OUTPUT / f"scene-{index:02}.png"),
            "-i",
            str(OUTPUT / f"scene-{index:02}.wav"),
            "-af",
            "apad=pad_dur=0.7",
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-tune",
            "stillimage",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "1",
            "-movflags",
            "+faststart",
            str(OUTPUT / f"scene-{index:02}.mp4"),
        ],
        check=True,
    )
(OUTPUT / "english.srt").write_text("\n".join(subtitles), "utf-8")
playlist = OUTPUT / "concat.txt"
playlist.write_text(
    "\n".join(f"file 'scene-{i:02}.mp4'" for i in range(1, len(SCENES) + 1)), "utf-8"
)
video = OUTPUT / "ProofTrail-pitch-review.mp4"
subprocess.run(
    [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(playlist),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(video),
    ],
    check=True,
)
probe = json.loads(
    subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video)]
    )
)
record = {
    "kind": "synthetic narration review draft; code-native artwork, not a live screen recording",
    "durationSeconds": float(probe["format"]["duration"]),
    "sceneDurations": durations,
    "voice": "Microsoft Huihui Desktop (generic Chinese synthetic voice)",
    "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
    "bytes": video.stat().st_size,
    "videoCodec": next(s["codec_name"] for s in probe["streams"] if s["codec_type"] == "video"),
    "audioCodec": next(s["codec_name"] for s in probe["streams"] if s["codec_type"] == "audio"),
    "submitted": False,
}
if record["durationSeconds"] >= 120:
    raise SystemExit("Encoded duration reaches the 120s submission limit; shorten the draft.")
(OUTPUT / "review-record.json").write_text(
    json.dumps(record, indent=2, ensure_ascii=False) + "\n", "utf-8"
)
print(json.dumps(record, indent=2, ensure_ascii=False))
