"""Check shipped theme token contrast using the WCAG relative-luminance formula."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def luminance(hex_value):
    values = [int(hex_value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def main():
    css = (ROOT / "frontend/src/style.css").read_text()
    themes = re.findall(r":root(?:\[data-theme=\"dark\"\])?\s*\{([^}]+)\}", css)
    checks = []
    for name, block in zip(("light", "dark"), themes):
        tokens = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block))
        pairs = [
            (fg, bg, 4.5)
            for fg in ("ink", "muted", "accent", "bad")
            for bg in ("ground", "surface", "subtle")
        ]
        pairs += [("accent", "accent-soft", 4.5), ("bad", "bad-soft", 4.5), ("ground", "accent", 4.5)]
        pairs += [(fg, bg, 3) for fg in ("control", "focus") for bg in ("ground", "surface", "subtle")]
        for fg, bg, threshold in pairs:
            left, right = sorted((luminance(tokens[fg]), luminance(tokens[bg])))
            ratio = (right + 0.05) / (left + 0.05)
            checks.append(
                {
                    "theme": name,
                    "foreground": fg,
                    "background": bg,
                    "ratio": round(ratio, 2),
                    "minimum": threshold,
                    "pass": ratio >= threshold,
                }
            )
    assert len(checks) == 42, "Both shipped themes must be checked"
    path = ROOT / "reports/contrast.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(checks, indent=2), encoding="utf-8")
    failures = [c for c in checks if not c["pass"]]
    print(
        json.dumps(
            {
                "checked": len(checks),
                "minimum_text_ratio": min(c["ratio"] for c in checks if c["minimum"] == 4.5),
                "failures": failures,
            },
            indent=2,
        )
    )
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
