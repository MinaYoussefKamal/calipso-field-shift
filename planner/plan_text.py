"""The plans as a plain-text file the farmer can keep, print or send (no Streamlit needed, so it can be tested)."""
from __future__ import annotations

import explainer as ex
import price_cards as pc

HEAD = {"en": "Field Shift · Monufia", "ar": "Field Shift · المنوفية"}


def crop_label(c: str, lang: str) -> str:
    return ex.CROP_AR[c][0] if lang == "ar" else ex.CROP_EN[c].capitalize()


def build(out: dict, res: dict, summer: str, winter: str, lang: str) -> str:
    ui = out["ui"]
    lines = [HEAD[lang], ui["intro_title"], out["intro"], ""]
    for tag in "ABC":
        o, sc = out[tag], res[tag]["scores"]
        lines += [f'=== {ui["plan"]} {tag}: {o["title"]} ({o["role"]}) ===',
                  f'{ui["marks"]["goal"]}: {ex._r(sc["goal"])}/100',
                  f'{ui["marks"]["water"]}: {ex._r(sc["water"])}/100',
                  f'{ui["marks"]["soil"]}: {ex._r(sc["soil"])}/100',
                  f'{ui["marks"]["money"]}: {ex._r(sc["money_saving_proxy"])}/100',
                  f'{ui["marks"]["heat"]}: {ui["tier"][sc["heat_level"]]}', "",
                  o["why"]["goal"], o["why"]["water"], o["why"]["soil"], ""]
        for head, items in ((ui["benefits"], o["benefits"]), (ui["trade_offs"], o["trade_offs"]),
                            (ui["warnings"], o["warnings"]), (ui["evidence"], o["evidence"]),
                            (ui["gaps"], o["information_gaps"]), (ui["risks"], o["risks_for_local_review"])):
            if items:
                lines += [head + ":"] + [f"- {s}" for s in items] + [""]
        lines += [pc.TITLE[lang] + ":"]
        for c in (summer, winter):
            lines += [f"{crop_label(c, lang)}:"] + [f"- {s}" for s in pc.lines(c, lang)]
        lines += [""]
    lines += [out["disclaimer"], pc.SOURCE_NOTE[lang], "CALIPSO"]
    return "\n".join(lines)
