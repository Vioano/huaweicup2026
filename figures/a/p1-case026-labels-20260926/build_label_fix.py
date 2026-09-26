"""Keep the fixed case_026 figure pixel-identical outside its two corrected letters.

The image-generation proposal supplies replacement glyphs. Only the X/Y glyph
pixels in the two heading positions are transferred to the fixed source PNG.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = (
    "6ee1684675e92b65ddea96a5bb2b6dacefefafef:"
    "paper/manuscript-v1/figures/fig-p1-cuts-zh.png"
)
SOURCE_SHA256 = "ce7f192887ec4860ff4767b7322907c36605465f34c81975d67e5ed52a8f9c3f"
PROPOSAL_SHA256 = "f8816b1cdde927573bf07d6f146d8d3ab0485fd8fe0c3edd32039759a2c397b7"
WIDTH, HEIGHT = 1536, 1024
LETTER_AREAS = ((836, 875, 54, 91), (1171, 1210, 54, 91))


def fixed_bytes() -> bytes:
    source = subprocess.check_output(["git", "-C", str(ROOT), "show", SOURCE])
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("fixed source PNG hash differs from the requested diagram")
    return source


def rgb(png: bytes) -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
        input=png, capture_output=True, check=True,
    )
    if len(result.stdout) != WIDTH * HEIGHT * 3:
        raise ValueError("source image is not 1536×1024 RGB")
    return result.stdout


def corrected_pixels(original: bytes, proposal: bytes) -> tuple[bytes, int]:
    result = bytearray(original)
    changed = set()
    for left, right, top, bottom in LETTER_AREAS:
        dark = set()
        for y in range(top, bottom):
            for x in range(left, right):
                at = (y * WIDTH + x) * 3
                if min(original[at:at + 3]) < 205 or min(proposal[at:at + 3]) < 205:
                    dark.add((x, y))
        # Include antialiased glyph edges, but never the surrounding labels.
        for x, y in dark:
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    xx, yy = x + dx, y + dy
                    if left <= xx < right and top <= yy < bottom:
                        changed.add((xx, yy))
    for x, y in changed:
        at = (y * WIDTH + x) * 3
        result[at:at + 3] = proposal[at:at + 3]
    if not 200 <= len(changed) <= 2500:
        raise ValueError(f"unexpected edited pixel area: {len(changed)}")
    return bytes(result), len(changed)


def main() -> None:
    source = fixed_bytes()
    proposal = (HERE / "imagegen-letter-proposal.png").read_bytes()
    if hashlib.sha256(proposal).hexdigest() != PROPOSAL_SHA256:
        raise ValueError("image-generation proposal hash changed")
    before, after_proposal = rgb(source), rgb(proposal)
    result, selected = corrected_pixels(before, after_proposal)
    output = HERE / "fig-p1-cuts-xy-corrected.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{WIDTH}x{HEIGHT}", "-i", "pipe:0", "-frames:v", "1", "-c:v", "png", str(output)],
        input=result, capture_output=True, check=True,
    )
    if rgb(output.read_bytes()) != result:
        raise ValueError("PNG encoding changed pixels")
    print(f"wrote {output} | proposal area {selected} px | outside two letters unchanged")
    print(f"SHA-256 {hashlib.sha256(output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
