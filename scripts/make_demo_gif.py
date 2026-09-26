"""Render docs/assets/demo-verify.gif: a leaky agent strategy, the fix, the honest verdict.

The terminal lines are copied from real `monte-neo verify` runs on
`synthetic_ohlcv(3000, seed=1)`. Re-run those commands and update the lines if the
verifier output changes. Certificate ids include the engine version, so they
change with every release.

Run: uv run python scripts/make_demo_gif.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "demo-verify.gif"
W, H = 960, 600
FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
BG, PANEL, BORDER = (13, 17, 23), (22, 27, 34), (48, 54, 61)
FG, DIM = (201, 209, 217), (125, 133, 144)
RED, GRN, YEL, BLU = (248, 81, 73), (63, 185, 80), (210, 153, 34), (121, 192, 255)

Part = tuple[str, tuple[int, int, int], bool]


def p(text: str, color: tuple[int, int, int] = FG, bold: bool = False) -> Part:
    return (text, color, bold)


def check(name: str, status: str, summary: str) -> list[Part]:
    return [p(f"  {name:<25}"), p(status, GRN if status == "pass" else RED, True), p(f"  {summary}")]


SCENES: list[list[list[Part]]] = [
    [[p('# The agent reports: "Found a profitable strategy!"', DIM)]],
    [[p("$ ", GRN), p("monte-neo verify --ohlcv prices.csv --strategy agent_strategy.py --n-trials 40")]],
    [
        [p("REJECT", RED, True), p("  certificate a6901d8b6622804e", DIM)],
        check("lookahead_truncation", "fail", "truncation probe: LEAK DETECTED"),
        check("lookahead_perturbation", "fail", "future-perturbation probe: LEAK DETECTED"),
        check("lookahead_static_lint", "fail", "static lint: negative_shift"),
        check("implausible_accuracy", "fail", "next-bar hit rate 1.000"),
        [p("→ compute features only from rows <= t (no shift(-k), centered windows, bfill)", YEL)],
    ],
    [
        [p("")],
        [p("# The agent fixes line 6:", DIM)],
        [p('-    return np.sign(df["close"].shift(-1) - df["close"])', RED)],
        [p('+    return np.sign(df["close"].diff())', GRN)],
    ],
    [[p("")], [p("$ ", GRN), p("monte-neo verify --ohlcv prices.csv --strategy fixed_strategy.py --n-trials 2")]],
    [
        [p("REJECT", RED, True), p("  certificate 8ed2812b618d7ac0", DIM)],
        check("lookahead_truncation", "pass", "truncation probe: no leak detected"),
        check("lookahead_perturbation", "pass", "future-perturbation probe: no leak detected"),
        check("net_profitability", "fail", "net total return -95.19% after costs"),
        [p("→ The strategy loses money after costs: reduce turnover or find a stronger edge.", YEL)],
    ],
    [[p("")], [p("# No look-ahead left, and no edge after costs: the honest answer on a random walk.", BLU)]],
]
# Scenes after which the animation pauses longer (ms).
PAUSES = {2: 1600, 5: 1600}


def render(lines: list[list[Part]]) -> Image.Image:
    regular = ImageFont.truetype(FONT_DIR + "DejaVuSansMono.ttf", 16)
    bold = ImageFont.truetype(FONT_DIR + "DejaVuSansMono-Bold.ttf", 16)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([12, 12, W - 12, H - 12], radius=12, fill=PANEL, outline=BORDER, width=2)
    for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse([30 + i * 22, 28, 42 + i * 22, 40], fill=c)
    d.text((W // 2 - 60, 25), "monte-neo verify", font=regular, fill=DIM)
    y = 62
    for line in lines:
        x = 32.0
        for text, color, is_bold in line:
            font = bold if is_bold else regular
            d.text((x, y), text, font=font, fill=color)
            x += d.textlength(text, font=font)
        y += 24
    return img


def main() -> None:
    frames: list[Image.Image] = []
    durations: list[int] = []
    shown: list[list[Part]] = []
    for index, scene in enumerate(SCENES):
        for line in scene:
            shown.append(line)
            frames.append(render(shown))
            durations.append(250)
        durations[-1] = PAUSES.get(index, 900)
    durations[-1] = 4000
    palette = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=32) for f in frames]
    palette[0].save(OUT, save_all=True, append_images=palette[1:], duration=durations, loop=0, optimize=True)
    print(f"wrote {OUT} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
