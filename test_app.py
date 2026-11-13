"""Tests for the Monufia rotation planner site.

Run:   python3 -m unittest test_app -v          (about 1 minute)
Quick: FIELD_SHIFT_QUICK=1 python3 -m unittest test_app   (every 6th farmer situation only)
"""
import calendar
import itertools
import os
import re
import sys
import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "planner"))
import explainer as ex  # noqa: E402
import plan_text  # noqa: E402
import price_cards as pc  # noqa: E402
from rotation_engine import GOALS, MINOR_CROPS, Engine  # noqa: E402

ENG = Engine()
SUMMER = list(dict.fromkeys(ENG.pairs["summer"]))
WINTER = list(dict.fromkeys(ENG.pairs["winter"]))
QUICK = bool(os.environ.get("FIELD_SHIFT_QUICK"))


def run_app(lang="en", page=None):
    """Run the whole app. page='evidence' / 'about' runs that page's function instead of the default one."""
    source = (ROOT / "app.py").read_text(encoding="utf-8").replace(
        "ROOT = Path(__file__).parent", f"ROOT = Path({str(ROOT.resolve())!r})")
    if page:
        assert source.count("page.run()") == 1
        source = source.replace("page.run()", f"{page}()")
    at = AppTest.from_string(source, default_timeout=60)
    at.session_state["lang"] = lang
    return at.run()


def K(name, lang="en"):
    """Widget keys carry the language (see app.py)."""
    return f"w_{name}_{lang}"


def all_text(at):
    parts = [m.value for m in at.markdown] + [w.value for w in at.warning] + [i.value for i in at.info]
    parts += [c.value for c in at.caption] + [s.value for s in at.subheader]
    return "\n".join(parts)


class DataChecks(unittest.TestCase):
    def test_explainer_checks_all_144_situations(self):
        n, problems = ex.check_all(ENG)
        self.assertEqual(problems, [])
        self.assertGreaterEqual(n, 144)

    def test_price_lines_match_library_and_arabic(self):
        self.assertEqual(pc.check(), [])
        self.assertEqual(set(pc.LINES), set(ex.CROP_EN))

    def test_text_file_has_everything(self):
        for lang in ("en", "ar"):
            res = ENG.recommend("cotton", "wheat", "save_money", main_crops_only=True)
            out = ex.explain(ENG, res, lang)
            text = plan_text.build(out, res, "cotton", "wheat", lang)
            for tag in "ABC":
                self.assertIn(out[tag]["title"], text)
                self.assertIn(f'{ex._r(res[tag]["scores"]["goal"])}/100', text)
            self.assertIn(out["disclaimer"], text)
            for c in ("cotton", "wheat"):
                for line in pc.lines(c, lang):
                    self.assertIn(line, text)


class Pages(unittest.TestCase):
    def test_all_pages_both_languages(self):
        for lang in ("en", "ar"):
            for page in (None, "evidence", "about"):
                at = run_app(lang, page)
                self.assertFalse(at.exception, (lang, page, [e.value for e in at.exception]))

    def test_plans_page_shows_three_plans_and_all_details(self):
        for lang in ("en", "ar"):
            at = run_app(lang)
            text = all_text(at)
            res = ENG.recommend("maize", "wheat", "save_water", main_crops_only=True)
            out = ex.explain(ENG, res, lang)
            for tag in "ABC":
                self.assertIn(f"role-{tag}", text)
                self.assertIn(out[tag]["title"], text)
            self.assertEqual(len(at.expander), 12)  # 4 per plan: evidence, prices, gaps, risks
            self.assertEqual(len(at.get("download_button")), 1)
            self.assertIn(out["disclaimer"], text)

    def test_language_switch_keeps_the_farmers_choices(self):
        at = run_app("en")
        at.selectbox(key=K("summer")).select("cotton").run()
        at.selectbox(key=K("winter")).select("potato").run()
        at.radio(key=K("goal")).set_value("improve_soil").run()
        at.checkbox(key=K("main_only")).set_value(False).run()
        at.radio(key="lang").set_value("ar").run()
        self.assertFalse(at.exception)
        self.assertEqual(at.selectbox(key=K("summer", "ar")).value, "cotton")
        self.assertEqual(at.selectbox(key=K("winter", "ar")).value, "potato")
        self.assertEqual(at.radio(key=K("goal", "ar")).value, "improve_soil")
        self.assertFalse(at.checkbox(key=K("main_only", "ar")).value)
        at.radio(key="lang").set_value("en").run()  # and back again
        self.assertEqual(at.selectbox(key=K("summer")).value, "cotton")

    def test_choices_come_back_after_leaving_the_page(self):
        """Streamlit forgets widgets when you open another page; the saved profile must bring the choices back.
        Here the profile is set but the widget keys are absent, which is exactly the state on coming back."""
        source = (ROOT / "app.py").read_text(encoding="utf-8").replace(
            "ROOT = Path(__file__).parent", f"ROOT = Path({str(ROOT.resolve())!r})")
        at = AppTest.from_string(source, default_timeout=60)
        at.session_state["profile"] = dict(summer="sesame", winter="onion", goal="save_money", main_only=False)
        at.run()
        self.assertFalse(at.exception)
        self.assertEqual(at.selectbox(key=K("summer")).value, "sesame")
        self.assertEqual(at.selectbox(key=K("winter")).value, "onion")
        self.assertEqual(at.radio(key=K("goal")).value, "save_money")
        self.assertFalse(at.checkbox(key=K("main_only")).value)
        # and the profile follows every change the farmer makes
        at.selectbox(key=K("summer")).select("maize").run()
        self.assertEqual(at.session_state["profile"]["summer"], "maize")

    def test_main_crops_tickbox_default_on_and_hides_minor_crops(self):
        at = run_app("en")
        self.assertTrue(at.checkbox(key=K("main_only")).value)  # default ON
        for s, w in itertools.product(SUMMER, WINTER):
            res = ENG.recommend(s, w, "save_water", main_crops_only=True)
            for tag in "BC":
                self.assertNotIn(res[tag]["summer"], MINOR_CROPS)

    def test_evidence_page_numbers_match_the_data(self):
        df = pd.read_csv(ROOT / "planner" / "monufia_month_profile.csv")
        at = run_app("en", "evidence")
        text = all_text(at)
        self.assertEqual(len(at.subheader), 4)
        self.assertEqual(len(at.metric), 3)
        change = df["t_mean_change_c"].mean()
        self.assertEqual(at.metric[0].value, f"\u2066+{change:.1f} °C\u2069")
        self.assertEqual(at.metric[1].value, f"{df['rain_mm'].sum():.0f} mm")
        self.assertEqual(at.metric[2].value, f"{df['hot_days_35'].sum():.0f}")
        # the months with "more than half the days at 35 °C" must be one unbroken stretch (the sentence says "from X to Y")
        dim = {m: calendar.monthrange(2023, m)[1] for m in range(1, 13)}
        most = [int(m) for m, h in zip(df["month"], df["hot_days_35"]) if h > dim[int(m)] / 2]
        self.assertEqual(most, list(range(min(most), max(most) + 1)))
        self.assertIn(f"From {calendar.month_name[min(most)]} to {calendar.month_name[max(most)]}", text)
        # no millimetre irrigation amounts anywhere: water is shown as a relative number only
        self.assertNotIn("irrigation amount of", text.lower())

    def test_second_tab_is_called_statistical_information_in_both_languages(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        # the menu entry (the navigation bar is drawn by the browser, so it is checked in the source)
        self.assertIn('title=t("Statistical information", "معلومات إحصائية")', source)
        self.assertNotIn('title=t("NASA evidence"', source)
        # the heading label on the page itself, in both languages
        self.assertIn('class="eyebrow">STATISTICAL INFORMATION<', all_text(run_app("en", "evidence")))
        self.assertIn('class="eyebrow">معلومات إحصائية<', all_text(run_app("ar", "evidence")))
        for lang in ("en", "ar"):
            self.assertNotIn("NASA EVIDENCE", all_text(run_app(lang, "evidence")))

    def test_about_page_numbers_match_the_engine(self):
        text = all_text(run_app("en", "about"))
        self.assertIn(f"{len(ENG.pairs)} yearly plans", text)
        self.assertIn(f"{len(SUMMER)} summer crops × {len(WINTER)} winter crops", text)
        soil_min = ENG.recommend("maize", "wheat", "save_water")["soil_minimum"]
        self.assertIn(f"at {soil_min} or more", text)


class EverySituation(unittest.TestCase):
    """All 24 current rotations x 3 goals x tick-box on/off, in both languages: the page must draw without an
    error and show exactly what the engine and the explainer produced."""

    def test_every_farmer_situation_both_languages(self):
        situations = list(itertools.product(SUMMER, WINTER, GOALS, (True, False)))
        self.assertEqual(len(situations), 144)
        if QUICK:
            situations = situations[::6]
        for lang in ("en", "ar"):
            at = run_app(lang)
            for s, w, g, main in situations:
                at.selectbox(key=K("summer", lang)).select(s)
                at.selectbox(key=K("winter", lang)).select(w)
                at.radio(key=K("goal", lang)).set_value(g)
                at.checkbox(key=K("main_only", lang)).set_value(main)
                at.run()
                tag_ = (lang, s, w, g, main)
                self.assertFalse(at.exception, (tag_, [e.value for e in at.exception]))
                res = ENG.recommend(s, w, g, main_crops_only=main)
                out = ex.explain(ENG, res, lang)
                text = all_text(at)
                for tag in "ABC":
                    self.assertIn(out[tag]["title"], text, tag_)
                    self.assertIn(f'{ex._r(res[tag]["scores"]["goal"])}<small>/100', text, tag_)
                    for line in out[tag]["benefits"] + out[tag]["trade_offs"] + out[tag]["warnings"]:
                        self.assertIn(line, text, tag_)
                for c in (s, w):
                    self.assertIn(pc.lines(c, lang)[0], text, tag_)
                if lang == "ar":  # Arabic page: no English crop name should leak into the plan titles
                    for tag in "ABC":
                        self.assertIsNone(re.search(r"[A-Za-z]{3,}", re.sub(r"A|B|C", "", out[tag]["title"])), tag_)


if __name__ == "__main__":
    unittest.main()
