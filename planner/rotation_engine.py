"""Steps 7-9: the plan engine (rule-based, NO machine learning).

What it does, in plain words
  Step 7  list every possible one-year plan = one summer crop then one winter crop (24 plans).
  Step 8  give every plan four marks out of 100: water, soil, money-saving, plus a heat label.
  Step 9  for a farmer's current plan and goal, return three plans:
            A = the farmer's own plan,
            B = the best plan for the goal,
            C = the best plan for the goal that ALSO passes a minimum soil mark.

Every mark comes from a written rule below. Nothing is learned from data, so nothing can be "made up".
Evidence numbers (heat, rain, greenness, soil moisture) are NASA data (crop_season_evidence_monufia.csv).
Crop facts (nitrogen, plant family, season dates, pests) come from the crop library (outside sources).
The money mark is a cost-saving proxy, NOT profit (decision "hybrid", 13 Nov).

Usage:
  python3 -I rotation_engine.py maize wheat save_water        # show A, B, C for one farmer
  python3 -I rotation_engine.py --export rotation_scores_monufia.csv   # the 24 plans with all marks
Needs in the same folder: crop_library_monufia.csv, crop_season_evidence_monufia.csv (and pandas).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent

GOALS = ("save_money", "save_water", "improve_soil")
GOAL_COLUMN = {"save_money": "money_score", "save_water": "water_score", "improve_soil": "soil_score"}

# ------------------------------------------------------------------ rules (edit here, nowhere else)
# Water need is shown as three tiers, never in mm (user decision (e), 13 Nov 16:32). Summer: sesame low;
# maize and soybean middle (sources disagree on their order, so a tie); cotton high. Winter: faba bean,
# potato, wheat low; berseem, onion middle; sugar beet high. Basis: NASA POWER ET0 x FAO crop curve,
# cross-checked with GAEZ (6 crops) and Egyptian field studies (soybean, sesame).
WATER_TIER = {
    "sesame": "LOW", "maize": "MIDDLE", "soybean": "MIDDLE", "cotton": "HIGH",
    "faba_bean": "LOW", "potato": "LOW", "wheat": "LOW", "berseem": "MIDDLE", "onion": "MIDDLE",
    "sugar_beet": "HIGH",
}
TIER_POINTS = {"LOW": 3, "MIDDLE": 2, "HIGH": 1}       # water mark = (points of both crops - 2) / 4 * 100

# Soil mark (0-100) = nitrogen part (max 50) + plant-family part (30) + ground-cover part (20)
SOIL_N_BASE = 25
SOIL_N_POINTS = {"legume": 25, "legume_weak": 10, "heavy": -15, "moderate": -5, "light": 0}
SOIL_N_MAX = 50
SOIL_FAMILY_POINTS = 30       # the two crops are in DIFFERENT plant families (same family = 0)
SOIL_COVER_POINTS = 20        # share of the year the field has a crop (days covered / 365) x 20
SOIL_MIN = 70                 # option C must reach at least this soil mark (9 of the 24 plans do; 60 let in 18)

# Heat level = days at 35 C or more inside the two seasons (NASA POWER, 2011-2024 average). The 24 plans fall in
# three clear clusters (about 97-103, 117-124 and 135-140 days), so the breaks sit in the gaps between them.
HEAT_BREAKS = (110, 130)

# Money-saving proxy (0-100) = water part (half the water mark) + fertiliser part (max 50). Not profit.
FERT_POINTS = {"legume": 25, "legume_weak": 25, "light": 20, "moderate": 12, "heavy": 0}
FERT_MAX = 50
LEGUME_CREDIT = 10            # a nitrogen-fixing winter legume (berseem, faba bean) before a non-legume summer crop

MINOR_CROPS = ("soybean", "sesame")
NO_CROSS_CHECK = ("berseem", "faba_bean", "sugar_beet", "soybean", "sesame")   # no GAEZ value for these
NO_COST_DATA = ("faba_bean", "onion")

CROP_LABEL = {"faba_bean": "faba bean", "sugar_beet": "sugar beet"}

GLOBAL_GAPS = [
    "Water need is a tier (low / middle / high) for comparing crops. It is not an irrigation amount: the NASA "
    "grid cell reads summer air demand about 40% above a published north-Delta station.",
    "The money mark is a cost-saving proxy (water tier and fertiliser need), not profit. Prices are shown "
    "beside it and are never added to it.",
    "Weather is for one grid cell of about 55 x 60 km and greenness for six 250 m points, so this describes "
    "the zone, not one field.",
    "SMAP L4 soil moisture (SPL4SMGP, 9 km) does not see Nile irrigation, so it is context, not a score input.",
    "Season dates are model dates from the crop library, not your field dates.",
]


def label(crop: str) -> str:
    return CROP_LABEL.get(crop, crop)


def _n_class(text: str) -> str:
    t = text.lower()
    if "legume" in t:
        return "legume_weak" if "seed takes most" in t else "legume"
    for k in ("heavy", "moderate", "light"):
        if k in t:
            return k
    raise ValueError(f"cannot read nitrogen class from: {text}")


def _days_covered(sow_doy: int, end_doy: int) -> set[int]:
    if end_doy >= sow_doy:
        return set(range(sow_doy, end_doy + 1))
    return set(range(sow_doy, 366)) | set(range(1, end_doy + 1))     # winter crop wraps over New Year


class Engine:
    def __init__(self, library_csv=None, evidence_csv=None):
        lib = pd.read_csv(library_csv or HERE / "crop_library_monufia.csv")
        ev = pd.read_csv(evidence_csv or HERE / "crop_season_evidence_monufia.csv")
        lib = lib[lib["allowed_in_monufia"].str.lower().str.startswith("yes")].set_index("crop")
        self.lib = lib
        self.ev = ev.set_index("crop")
        self.summer = [c for c in lib.index if lib.loc[c, "slot"] == "summer"]
        self.winter = [c for c in lib.index if lib.loc[c, "slot"] == "winter"]
        assert set(WATER_TIER) == set(lib.index), "water tiers and library crops differ"
        self.ncls = {c: _n_class(lib.loc[c, "n_effect"]) for c in lib.index}
        self.family = {c: str(lib.loc[c, "family"]).split()[0] for c in lib.index}
        self.pairs = self._build_pairs()

    # ---------------------------------------------------------------- Step 7: the 24 plans
    def _build_pairs(self) -> pd.DataFrame:
        rows = [self._score_pair(s, w) for s in self.summer for w in self.winter]
        df = pd.DataFrame(rows)
        df["heat_tier"] = df["heat_days_35"].apply(
            lambda v: "LOW" if v <= HEAT_BREAKS[0] else ("MIDDLE" if v <= HEAT_BREAKS[1] else "HIGH"))
        return df

    # ---------------------------------------------------------------- Step 8: the marks
    def _score_pair(self, s: str, w: str) -> dict:
        L = self.lib
        # water mark from the two tiers
        pts = TIER_POINTS[WATER_TIER[s]] + TIER_POINTS[WATER_TIER[w]]
        water = (pts - 2) / 4 * 100
        # soil mark
        n_part = max(0, min(SOIL_N_MAX, SOIL_N_BASE + SOIL_N_POINTS[self.ncls[s]] + SOIL_N_POINTS[self.ncls[w]]))
        same_family = self.family[s] == self.family[w]
        fam_part = 0 if same_family else SOIL_FAMILY_POINTS
        covered = _days_covered(int(L.loc[s, "sow_doy"]), int(L.loc[s, "end_doy"])) | \
            _days_covered(int(L.loc[w, "sow_doy"]), int(L.loc[w, "end_doy"]))
        cover_part = len(covered) / 365 * SOIL_COVER_POINTS
        soil = n_part + fam_part + cover_part
        # money-saving proxy
        credit = LEGUME_CREDIT if (self.ncls[w] == "legume" and not self.ncls[s].startswith("legume")) else 0
        fert = max(0, min(FERT_MAX, FERT_POINTS[self.ncls[s]] + FERT_POINTS[self.ncls[w]] + credit))
        money = water * 0.5 + fert
        # timing (days between crops; negative = the next crop would have to be sown before the last one ends)
        gap_s2w = int(L.loc[w, "sow_doy"]) - int(L.loc[s, "end_doy"])
        gap_w2s = int(L.loc[s, "sow_doy"]) - int(L.loc[w, "end_doy"])
        heat35 = float(self.ev.loc[s, "hot_days_35"] + self.ev.loc[w, "hot_days_35"])
        heat40 = float(self.ev.loc[s, "hot_days_40"] + self.ev.loc[w, "hot_days_40"])
        return {
            "summer": s, "winter": w,
            "water_tier_summer": WATER_TIER[s], "water_tier_winter": WATER_TIER[w],
            "water_score": round(water, 1),
            "soil_nitrogen_part": round(n_part, 1), "soil_family_part": fam_part,
            "soil_cover_part": round(cover_part, 1), "soil_score": round(soil, 1),
            "money_water_part": round(water * 0.5, 1), "money_fertiliser_part": round(fert, 1),
            "money_score": round(money, 1),
            "same_family": same_family,
            "gap_summer_end_to_winter_sow_days": gap_s2w, "gap_winter_end_to_summer_sow_days": gap_w2s,
            "timing_clash": gap_s2w < 0 or gap_w2s < 0,
            "heat_days_35": round(heat35, 1), "heat_days_40": round(heat40, 1),
        }

    def export_table(self) -> pd.DataFrame:
        return self.pairs.sort_values(["summer", "winter"]).reset_index(drop=True)

    # ---------------------------------------------------------------- Step 9: A, B, C
    def recommend(self, summer: str, winter: str, goal: str, main_crops_only: bool = False) -> dict:
        """Return A (your plan), B (best for the goal) and C (good for the goal AND soil mark >= SOIL_MIN).

        B and C are never plans whose crops clash in time (cotton before any winter crop in the library).
        main_crops_only=True also leaves soybean and sesame (small crops in Egypt) out of B and C.
        """
        if goal not in GOALS:
            raise ValueError(f"goal must be one of {GOALS}")
        if summer not in self.summer:
            raise ValueError(f"summer crop must be one of {self.summer}")
        if winter not in self.winter:
            raise ValueError(f"winter crop must be one of {self.winter}")
        col = GOAL_COLUMN[goal]
        df = self.pairs.copy()
        df["goal_score"] = df[col]
        df = df.sort_values(["goal_score", "soil_score", "water_score", "money_score", "summer", "winter"],
                            ascending=[False, False, False, False, True, True]).reset_index(drop=True)
        is_a = (df["summer"] == summer) & (df["winter"] == winter)
        a = df[is_a].iloc[0]
        pool = df[~is_a & ~df["timing_clash"]]
        if main_crops_only:
            pool = pool[~pool["summer"].isin(MINOR_CROPS) & ~pool["winter"].isin(MINOR_CROPS)]
        b = pool.iloc[0]
        rest = pool[~((pool["summer"] == b["summer"]) & (pool["winter"] == b["winter"]))]
        c_pool = rest[rest["soil_score"] >= SOIL_MIN]
        c_fallback = c_pool.empty
        if c_fallback:       # no other plan reaches the soil mark: take the best soil mark left and say so
            c_pool = rest.sort_values(["soil_score", "goal_score"], ascending=False)
        c = c_pool.iloc[0]
        a_is_best = bool(a["goal_score"] >= b["goal_score"])
        c_opt = self._option("C", c, a, goal, a_is_best)
        if c_fallback:
            c_opt["warnings"].append({"code": "SOIL_MINIMUM_NOT_MET", "text": (
                f"No other plan reaches the soil minimum of {SOIL_MIN} with these settings; this is the best soil mark left.")})
        return {
            "goal": goal, "a_is_best_or_tied": a_is_best, "soil_minimum": SOIL_MIN, "main_crops_only": main_crops_only,
            "A": self._option("A", a, a, goal, a_is_best),
            "B": self._option("B", b, a, goal, a_is_best),
            "C": c_opt,
        }

    # ---------------------------------------------------------------- facts for every option
    def _warnings(self, row) -> list[dict]:
        s, w, L = row["summer"], row["winter"], self.lib
        out = []
        if row["timing_clash"]:
            if row["gap_winter_end_to_summer_sow_days"] < 0:
                late = -row["gap_winter_end_to_summer_sow_days"]
                out.append({"code": "TIMING_CLASH", "text": (
                    f"{label(s).capitalize()} is sown about {L.loc[s, 'model_sow']}, so the winter crop before it must be "
                    f"harvested by then. {label(w).capitalize()} normally ends about {late} days later "
                    f"({L.loc[w, 'model_end']}), so you would need to harvest early or sow {label(s)} later. "
                    f"No source was found for a later sowing date, so this tool does not state one.")})
            if row["gap_summer_end_to_winter_sow_days"] < 0:
                out.append({"code": "TIMING_CLASH", "text": f"{label(w).capitalize()} would have to be sown before {label(s)} is harvested."})
        if row["same_family"]:
            fam = self.family[s]
            out.append({"code": "SAME_FAMILY", "text": (
                f"{label(s).capitalize()} and {label(w)} are in the same plant family ({fam}), which can carry "
                f"diseases and pests from one crop to the next.")})
        for c in (s, w):
            if c in MINOR_CROPS:
                out.append({"code": "MINOR_CROP", "text": (
                    f"{label(c).capitalize()} is a small crop in Egypt and no Monufia area was found: "
                    f"check seed and buyer before relying on it.")})
        return out

    def _gaps(self, row) -> list[str]:
        gaps = list(GLOBAL_GAPS)
        for c in (row["summer"], row["winter"]):
            if c in NO_CROSS_CHECK:
                gaps.append(f"The water tier for {label(c)} comes from NASA data only: there is no FAO (GAEZ) value to cross-check it.")
            if c in NO_COST_DATA:
                gaps.append(f"No cost figures were found for {label(c)}.")
        return gaps

    def _why(self, row, goal: str) -> list[str]:
        s, w = row["summer"], row["winter"]
        f = []
        f.append(f"Water: {label(s)} needs {row['water_tier_summer']} water and {label(w)} needs {row['water_tier_winter']} water "
                 f"(water mark {row['water_score']:.0f} of 100).")
        n_bits = []
        for c in (s, w):
            k = self.ncls[c]
            n_bits.append({"legume": f"{label(c)} fixes nitrogen", "legume_weak": f"{label(c)} fixes nitrogen but its seed takes most of it",
                           "heavy": f"{label(c)} takes a lot of nitrogen", "moderate": f"{label(c)} takes a moderate amount of nitrogen",
                           "light": f"{label(c)} takes little nitrogen"}[k])
        f.append("Soil: " + "; ".join(n_bits) + ". "
                 + ("Both crops are in the same plant family. " if row["same_family"] else "The two crops are in different plant families. ")
                 + f"The field has a crop for about {row['soil_cover_part'] / SOIL_COVER_POINTS * 100:.0f}% of the year "
                   f"(soil mark {row['soil_score']:.0f} of 100).")
        f.append(f"Money-saving proxy (not profit): water part {row['money_water_part']:.0f} + fertiliser part "
                 f"{row['money_fertiliser_part']:.0f} = {row['money_score']:.0f} of 100.")
        f.append(f"Heat: about {row['heat_days_35']:.0f} days a year at 35 C or more during the two seasons "
                 f"(heat level {row['heat_tier']}).")
        f.append(f"Timing: {row['gap_summer_end_to_winter_sow_days']} days between the summer harvest and winter sowing, "
                 f"{row['gap_winter_end_to_summer_sow_days']} days between the winter harvest and the next summer sowing.")
        return f

    def _evidence(self, crop: str) -> dict:
        e = self.ev.loc[crop]
        return {
            "season": f"{e['model_sow']} for {int(e['model_days'])} days (to {e['model_end']})",
            "hot_days_35_per_season": float(e["hot_days_35"]), "hot_days_40_per_season": float(e["hot_days_40"]),
            "average_daily_high_c": float(e["tmax_mean_c"]), "rain_mm_per_season": float(e["rain_mm"]),
            "greenness_ndvi": float(e["greenness"]),
            "soil_moisture_rootzone_smap": None if pd.isna(e["sm_rootzone"]) else float(e["sm_rootzone"]),
            "seasons_used": int(e["n_seasons"]),
            "source": "NASA POWER (weather), NASA MODIS MOD13Q1 (greenness), NASA SMAP L4 SPL4SMGP, 9 km (soil moisture); model season windows 2011-2024",
        }

    def _crop_facts(self, crop: str) -> dict:
        r = self.lib.loc[crop]
        return {"water_tier": WATER_TIER[crop], "family": r["family"], "nitrogen": r["n_effect"],
                "soil_effect": r["soil_effect"], "pests": r["pest_notes"], "rotation_hint": r["rotation_hint"],
                "price_card": r["price_card"], "sources": r["sources"]}

    def _option(self, tag: str, row, a_row, goal: str, a_is_best: bool = False) -> dict:
        b_role = (f"Best other plan for your goal ({goal.replace('_', ' ')}); your current plan is already as good on it"
                  if a_is_best else f"Best plan for your goal ({goal.replace('_', ' ')})")
        role = {"A": "Your current plan", "B": b_role, "C": "Good for your goal and kind to the soil"}[tag]
        return {
            "label": tag, "role": role, "summer": row["summer"], "winter": row["winter"],
            "scores": {"goal": float(row["goal_score"]), "water": float(row["water_score"]),
                       "soil": float(row["soil_score"]), "money_saving_proxy": float(row["money_score"]),
                       "heat_level": row["heat_tier"], "passes_soil_minimum": bool(row["soil_score"] >= SOIL_MIN)},
            "change_vs_A": None if tag == "A" else {
                "water": round(float(row["water_score"] - a_row["water_score"]), 1),
                "soil": round(float(row["soil_score"] - a_row["soil_score"]), 1),
                "money_saving_proxy": round(float(row["money_score"] - a_row["money_score"]), 1)},
            "why_facts": self._why(row, goal),
            "warnings": self._warnings(row),
            "information_gaps": self._gaps(row),
            "evidence_nasa": {"summer": self._evidence(row["summer"]), "winter": self._evidence(row["winter"])},
            "crop_facts": {row["summer"]: self._crop_facts(row["summer"]), row["winter"]: self._crop_facts(row["winter"])},
            "risks_for_local_review": [f"{label(c)}: {self.lib.loc[c, 'pest_notes']}" for c in (row["summer"], row["winter"])],
        }


def _print_option(o: dict) -> None:
    sc = o["scores"]
    print(f"  {o['label']}  {label(o['summer'])} then {label(o['winter'])}  [{o['role']}]")
    print(f"     goal {sc['goal']:.0f} | water {sc['water']:.0f} | soil {sc['soil']:.0f} | money proxy {sc['money_saving_proxy']:.0f} | heat {sc['heat_level']}")
    for wn in o["warnings"]:
        print(f"     ! {wn['code']}: {wn['text']}")


if __name__ == "__main__":
    eng = Engine()
    if len(sys.argv) >= 3 and sys.argv[1] == "--export":
        eng.export_table().to_csv(sys.argv[2], index=False)
        print("wrote", sys.argv[2], len(eng.pairs), "plans")
    elif len(sys.argv) in (4, 5):
        res = eng.recommend(sys.argv[1], sys.argv[2], sys.argv[3], main_crops_only=(len(sys.argv) == 5 and sys.argv[4] == "--main-only"))
        print(f"goal: {res['goal']} | A is best or tied: {res['a_is_best_or_tied']} | main crops only: {res['main_crops_only']}")
        for k in "ABC":
            _print_option(res[k])
    else:
        print(__doc__)
