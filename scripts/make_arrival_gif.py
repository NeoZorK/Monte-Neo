"""Render docs/assets/demo-arrival.gif: a strategy that lives on data it could not have seen, and an honest one.

Unlike demo-verify.gif the terminal lines are not typed in: they come from live runs of ``verify_quotes`` on the
synthetic quotes of ``monte-neo verify --demo-quotes``, so the numbers on the picture are the numbers of the code.
Certificate ids include the engine version, so they change with every release: re-run this script after one.

Run: uv run --extra plot python scripts/make_arrival_gif.py
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from monte_neo.verify.quotes import synthetic_quotes
from monte_neo.verify.quotes_verdict import verify_quotes
from monte_neo.verify.verdict import model_from_costs

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "demo-arrival.gif"
W, H = 960, 560
BG, PANEL, BORDER = (13, 17, 23), (22, 27, 34), (48, 54, 61)
FG, DIM = (201, 209, 217), (125, 133, 144)
RED, GRN, YEL, BLU = (248, 81, 73), (63, 185, 80), (210, 153, 34), (121, 192, 255)

Part = tuple[str, tuple[int, int, int], bool]
CLEAR = "clear"


def _font_dir() -> str:
    import matplotlib

    return os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf") + os.sep


def p(text: str, color: tuple[int, int, int] = FG, bold: bool = False) -> Part:
    return (text, color, bold)


STATUS_COLOR = {"pass": GRN, "warn": YEL, "fail": RED, "skip": DIM}
VERDICT_COLOR = {"PASS": GRN, "PASS_WITH_WARNINGS": YEL, "REJECT": RED, "NEEDS_MORE_EVIDENCE": YEL}


def short(summary: str) -> str:
    """The sentence the CLI prints, without its trailing clauses, so a line fits the window whole."""
    kept = [part for part in summary.split("; ") if "older than" not in part]
    return "; ".join(kept).replace(" on the exchange clock (a plain backtest)", " (plain backtest)")


def result_lines(report: dict) -> list[list[Part]]:
    """The verdict and one line per check, as the CLI prints them."""
    lines = [[p(report["verdict"], VERDICT_COLOR[report["verdict"]], True), p(f"  certificate {report['certificate_id']}", DIM)]]
    for c in report["checks"]:
        lines.append([p(f"  {c['id']:<22}"), p(f"{c['status']:<5}", STATUS_COLOR[c["status"]], True), p(f" {short(c['summary'])}")])
    return lines


def bars(report: dict) -> list[list[Part]]:
    """The two returns as bars: what the backtest saw against what was knowable."""
    a = report["latency"]["arrival"]
    scale = max(abs(a["return_exchange_clock"]), abs(a["return_arrival_clock"]), 1e-9)
    rows = []
    for label, value in (("exchange time (plain backtest)", a["return_exchange_clock"]), ("arrival time (what you could see)", a["return_arrival_clock"])):
        n = max(1, int(round(34 * abs(value) / scale)))
        rows.append([p(f"  {label:<36}"), p("█" * n, GRN if value > 0 else RED), p(f" {value:+.2%}", GRN if value > 0 else RED, True)])
    return rows


def build_scenes() -> list[list[list[Part]] | str]:
    model = model_from_costs(commission_bps=0.2, slippage_bps=0.0)

    def fast(df):  # reacts to each 10 ms bar the moment it closes
        return np.sign(df["close"].diff().fillna(0.0).to_numpy())

    def slow(df):  # a three-bar trend on 1 s bars
        return np.sign(df["close"].diff(3).fillna(0.0).to_numpy())

    bad = verify_quotes(synthetic_quotes(30_000, rho=0.5), signal_fn=fast, bar_ms=10.0, model=model, samples=20)
    good = verify_quotes(
        synthetic_quotes(40_000, rho=0.0, drift=1.5e-5, regime_steps=3000), signal_fn=slow, bar_ms=1000.0, model=model, samples=20
    )
    arrival = bad["latency"]["arrival"]
    return [
        [[p("# A fast strategy. An ordinary backtest says it earns money.", DIM)]],
        [[p("$ ", GRN), p("monte-neo verify --quotes quotes.csv --strategy fast_strategy.py --bar-ms 10")]],
        result_lines(bad),
        [[p("")], *bars(bad)],
        [
            [p("")],
            [p("# The strategy acted on prices that had not reached the machine yet:", BLU)],
            [p(f"# the data is {bad['metrics']['latency_p50_ms']:.0f} ms late (median), the bars are 10 ms.", BLU)],
            [p(f"# Profit {arrival['return_exchange_clock']:+.0%} on exchange time, {arrival['return_arrival_clock']:+.0%} on arrival time.", YEL, True)],
        ],
        CLEAR,
        [[p("# Same data source, a slow honest strategy.", DIM)]],
        [[p("$ ", GRN), p("monte-neo verify --quotes quotes.csv --strategy trend_strategy.py --bar-ms 1000")]],
        result_lines(good),
        [[p("")], *bars(good)],
        [
            [p("")],
            [p("# It does not need a quote before it arrives: the profit survives,", BLU)],
            [p("# in every latency draw. Monte-Neo separates the two.", BLU)],
        ],
    ]


def render(lines: list[list[Part]], fonts: tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]) -> Image.Image:
    regular, bold = fonts
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([12, 12, W - 12, H - 12], radius=12, fill=PANEL, outline=BORDER, width=2)
    for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse([30 + i * 22, 28, 42 + i * 22, 40], fill=c)
    d.text((W // 2 - 120, 25), "monte-neo verify --quotes", font=regular, fill=DIM)
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
    folder = _font_dir()
    fonts = (ImageFont.truetype(folder + "DejaVuSansMono.ttf", 15), ImageFont.truetype(folder + "DejaVuSansMono-Bold.ttf", 15))
    frames: list[Image.Image] = []
    durations: list[int] = []
    shown: list[list[Part]] = []
    for scene in build_scenes():
        if scene == CLEAR:
            durations[-1] = 2600
            shown = []
            continue
        for line in scene:  # type: ignore[union-attr]
            shown.append(line)
            frames.append(render(shown, fonts))
            durations.append(260)
        durations[-1] = 1500 if len(scene) > 4 else 900  # type: ignore[arg-type]
    durations[-1] = 4500
    # One palette for every frame: a per-frame palette merges the yellow of a warning into the red of a failure.
    sample = Image.new("RGB", (W, H * len(frames)))
    for i, frame in enumerate(frames):
        sample.paste(frame, (0, i * H))
    shared = sample.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette = [f.quantize(palette=shared, dither=Image.Dither.NONE) for f in frames]
    palette[0].save(OUT, save_all=True, append_images=palette[1:], duration=durations, loop=0, optimize=True)
    print(f"wrote {OUT} ({len(frames)} frames, {OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
