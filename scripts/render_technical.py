"""Actual evidence slideshow for technical review, explicitly not continuous wallet footage."""

import hashlib
import json
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/technical"
OUT.mkdir(parents=True, exist_ok=True)
SCENES = json.loads((ROOT / "assets/technical-scenes.json").read_text("utf-8"))
DEPLOYMENT = json.loads((ROOT / "artifacts/monad-deployment.json").read_text("utf-8"))
ACCEPTANCE = json.loads((ROOT / "artifacts/monad-acceptance.json").read_text("utf-8"))
SOURCE = json.loads((ROOT / "artifacts/verification/sourcify-record.json").read_text("utf-8"))
CLI = json.loads((ROOT / "artifacts/monad-demo/independent-cli-checks.json").read_text("utf-8"))
assert ACCEPTANCE["status"] == "passed"
assert SOURCE["job"]["contract"]["match"] == "exact_match"
INK, MUTED, PAPER, MINT = "#193447", "#617789", "#EAF0F7", "#1A8277"


def font(size, mono=False, bold=False):
    return ImageFont.truetype(
        str(
            Path("C:/Windows/Fonts")
            / ("consola.ttf" if mono else "msyhbd.ttc" if bold else "msyh.ttc")
        ),
        size,
    )


def text(draw, value, xy, size=29, width=1730, color=INK, mono=False):
    face = font(size, mono)
    position = xy[1]
    for paragraph in value.split("\n"):
        line = ""
        words = paragraph.split(" ") if paragraph.isascii() and not mono else list(paragraph)
        joiner = " " if paragraph.isascii() and not mono else ""
        for word in words:
            candidate = line + (joiner if line else "") + word
            if line and draw.textlength(candidate, font=face) > width:
                draw.text((xy[0], position), line, font=face, fill=color)
                position += size + 12
                line = word
            else:
                line = candidate
        draw.text((xy[0], position), line, font=face, fill=color)
        position += size + 12
    return position


inputs = [
    "assets/technical-scenes.json",
    "artifacts/monad-deployment.json",
    "artifacts/monad-acceptance.json",
    "artifacts/verification/sourcify-record.json",
    "artifacts/monad-demo/independent-cli-checks.json",
]
durations = []
for index, scene in enumerate(SCENES, 1):
    image = Image.new("RGB", (1920, 1080), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((70, 36), "ProofTrail / MONAD TESTNET", font=font(26, mono=True), fill=MINT)
    draw.text((1240, 36), "ACTUAL EVIDENCE / REVIEW DRAFT", font=font(24, mono=True), fill=MUTED)
    draw.text((70, 90), scene["title"], font=font(46, bold=True), fill=INK)
    draw.rounded_rectangle((55, 173, 1865, 832), radius=20, fill="white")
    visual = scene["visual"]
    if visual == "deployment":
        text(draw, "实际交易成功 / 非本地链模拟", (90, 214), 40, color=MINT)
        text(draw, "CONTRACT  " + DEPLOYMENT["address"], (90, 298), 30, mono=True)
        text(draw, "DEPLOY TX " + DEPLOYMENT["transactionHash"], (90, 365), 26, mono=True)
        text(
            draw,
            f"BLOCK {DEPLOYMENT['blockNumber']:,} / GAS {DEPLOYMENT['gasUsed']:,}",
            (90, 432),
            31,
            mono=True,
        )
        text(
            draw,
            "SOURCIFY: creationMatch = exact_match\nruntimeMatch = exact_match",
            (90, 510),
            32,
            mono=True,
            color=MINT,
        )
        text(draw, "证据：monad-deployment.json / verification/sourcify-record.json", (90, 650), 29)
        text(draw, "源码验证不等于第三方安全审计。", (90, 726), 29, color=MUTED)
    elif visual == "batches":
        text(draw, "实际 4 笔登记 / 每笔一个 Merkle 根", (90, 209), 38, color=MINT)
        text(
            draw,
            "RECEIPTS     TX       TOTAL GAS      GAS / RECEIPT      RPC WAIT ms",
            (90, 286),
            28,
            mono=True,
        )
        for i, item in enumerate(ACCEPTANCE["measurements"]):
            tx = item["transaction"]
            text(
                draw,
                f"{item['size']:>8}      1         {tx['gasUsed']:>8,}      {item['gasPerReceipt']:>13,.2f}      {tx['elapsedMs']:>11,.2f}",
                (90, 355 + i * 65),
                29,
                mono=True,
            )
        text(draw, "原文 + JSON 凭证 → artifacts/monad-demo/", (90, 670), 31)
        text(
            draw, "单次样本；不含签名/树构建；RPC 耗时不是共识最终性。", (90, 743), 28, color=MUTED
        )
    elif visual in {"valid", "tampered", "revoked"}:
        filename = f"artifacts/screenshots/monad-consumer-{visual}.png"
        inputs.append(filename)
        screenshot = Image.open(ROOT / filename).convert("RGB")
        # Enlarge the recorded check panel, retaining a full-page context thumbnail.
        thumbnail = screenshot.copy()
        thumbnail.thumbnail((470, 570))
        image.paste(thumbnail, (82, 237))
        focus = screenshot.crop((638, 500, 1218, 1255))
        focus.thumbnail((770, 618))
        image.paste(focus, (635, 191))
        text(
            draw,
            "实际页面截图\n右侧检查区放大\n\n独立服务\n127.0.0.1:8786\n读取真实链 10143",
            (1225, 236),
            31,
            width=560,
        )
        expected = {
            "valid": "全部通过 / 私有预览",
            "tampered": "内容完整性失败",
            "revoked": "发行者撤销检查失败",
        }[visual]
        text(
            draw,
            expected,
            (1225, 616),
            35,
            width=560,
            color=MINT if visual == "valid" else "#B2534E",
        )
    else:
        text(draw, "脱离发行 API 的独立 CLI", (90, 213), 37, color=MINT)
        for i, name in enumerate(("valid", "revoked")):
            item = CLI[name]
            text(
                draw,
                f"{name:8}  status={item['verification']['status']:8}  exit={item['exitCode']}",
                (90, 300 + i * 58),
                31,
                mono=True,
            )
        text(
            draw,
            "双容器：UID 10001 / 只读文件系统 / 无签名私钥\n独立消费与撤销通过，服务端签发返回 403",
            (90, 465),
            31,
        )
        text(
            draw,
            "待完成：公开托管、公开 GitHub、浏览器钱包实测、最终审阅\n尚无外部采用；来源声明不证明事实、版权或现实身份。",
            (90, 636),
            30,
            color=MUTED,
        )
    draw.rounded_rectangle((55, 852, 1865, 1012), radius=14, fill=INK)
    bottom = text(draw, scene["english"], (86, 873), 28, width=1745, color="white")
    if bottom > 1000:
        raise SystemExit("English captions exceed the safe frame region.")
    draw.text(
        (70, 1031),
        "ACTUAL UI SCREENSHOTS + RECORDED TRANSACTIONS / SYNTHETIC VOICE / NOT SUBMITTED",
        font=font(20, mono=True),
        fill=MUTED,
    )
    image.save(OUT / f"scene-{index:02}.png")
    with wave.open(str(OUT / f"scene-{index:02}.wav")) as audio:
        durations.append(audio.getnframes() / audio.getframerate() + 0.7)

if sum(durations) > 179:
    raise SystemExit("Technical review exceeds safe 179s; shorten and regenerate narration.")
for i, duration in enumerate(durations, 1):
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
            str(OUT / f"scene-{i:02}.png"),
            "-i",
            str(OUT / f"scene-{i:02}.wav"),
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
            str(OUT / f"scene-{i:02}.mp4"),
        ],
        check=True,
    )
playlist = OUT / "concat.txt"
playlist.write_text(
    "\n".join(f"file 'scene-{i:02}.mp4'" for i in range(1, len(SCENES) + 1)), "utf-8"
)
video = OUT / "ProofTrail-technical-review.mp4"
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
duration = float(probe["format"]["duration"])
if duration >= 180:
    raise SystemExit("Encoded technical video reaches 180 seconds.")
record = {
    "kind": "Actual UI screenshots and recorded transaction evidence; synthetic narration; not continuous wallet footage",
    "durationSeconds": duration,
    "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
    "bytes": video.stat().st_size,
    "sourceHashes": {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in inputs
    },
    "walletBrowserFlowVerified": False,
    "submitted": False,
}
(OUT / "review-record.json").write_text(json.dumps(record, indent=2) + "\n", "utf-8")
print(json.dumps({k: v for k, v in record.items() if k != "sourceHashes"}, indent=2))
