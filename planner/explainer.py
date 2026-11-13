"""Step 10: the explainer. It turns the plan engine's facts into short plain sentences, in English
and in Egyptian Arabic, and it checks its own sentences against those facts.

How it works, in plain words
  * The plan engine (rotation_engine.py) decides the marks and the three plans A, B and C.
  * This file only DESCRIBES them. It never changes a mark and never adds a fact of its own.
  * The sentences were written by the AI agent (Claude) as sentence recipes. Each recipe is filled in
    with numbers and crop names taken from the engine, so a sentence cannot contain a made-up number.
  * check_option() then proves it: every number, crop name and claim in the text must come from the
    engine's facts, and the English and Arabic versions must say the same things.
  * No live AI is needed on the website. A live AI can be added later; it would have to pass the same checker.

Use:
    from rotation_engine import Engine
    from explainer import explain
    eng = Engine()
    res = eng.recommend("maize", "wheat", "save_water", main_crops_only=True)
    text = explain(eng, res, "ar")      # or "en"
    text["B"]["why"]["goal"]            # one sentence
Run  python3 -I explainer.py  to check all 144 farmer situations in both languages.
"""
from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rotation_engine import (GLOBAL_GAPS, GOALS, MINOR_CROPS, NO_COST_DATA, NO_CROSS_CHECK, Engine)  # noqa: E402

LANGS = ("en", "ar")

# ------------------------------------------------------------------ words
CROP_EN = {"maize": "maize", "cotton": "cotton", "soybean": "soybean", "sesame": "sesame", "wheat": "wheat",
           "berseem": "berseem", "faba_bean": "faba bean", "sugar_beet": "sugar beet", "potato": "potato",
           "onion": "onion"}
# Arabic: (without "the", with "the")
CROP_AR = {"maize": ("ذرة شامية", "الذرة الشامية"), "cotton": ("قطن", "القطن"),
           "soybean": ("فول صويا", "فول الصويا"), "sesame": ("سمسم", "السمسم"), "wheat": ("قمح", "القمح"),
           "berseem": ("برسيم", "البرسيم"), "faba_bean": ("فول بلدي", "الفول البلدي"),
           "sugar_beet": ("بنجر السكر", "بنجر السكر"), "potato": ("بطاطس", "البطاطس"), "onion": ("بصل", "البصل")}
MONTH_AR = {"Jan": "يناير", "Feb": "فبراير", "Mar": "مارس", "Apr": "أبريل", "May": "مايو", "Jun": "يونيو",
            "Jul": "يوليو", "Aug": "أغسطس", "Sep": "سبتمبر", "Oct": "أكتوبر", "Nov": "نوفمبر", "Dec": "ديسمبر"}

GOAL_EN = {"save_money": "saving money", "save_water": "saving water", "improve_soil": "improving the soil"}
GOAL_AR = {"save_money": "توفير المصاريف", "save_water": "توفير المياه", "improve_soil": "تحسين التربة"}
TIER_EN = {"LOW": "little", "MIDDLE": "a medium amount of", "HIGH": "a lot of"}
TIER_AR_ADJ = {"LOW": "قليل", "MIDDLE": "متوسط", "HIGH": "كبير"}
FAMILY_EN = {"Poaceae": "cereals", "Fabaceae": "legumes"}
FAMILY_AR = {"Poaceae": "الحبوب", "Fabaceae": "البقوليات"}

# What each crop's main pest and disease risks are (short, from the crop library; no numbers on purpose)
PEST_EN = {
    "wheat": "rusts spread through the air, so rotation does not control them.",
    "berseem": "no major pest was flagged in our search (that does not mean there are none).",
    "faba_bean": "broomrape, a parasitic weed on the roots, can cut yield heavily; faba necrotic yellow virus has also hit fields.",
    "sugar_beet": "root-knot nematodes (tiny soil worms) are a major pest; sowing from October or later reduced them in trials.",
    "potato": "brown rot; exporters say too much potato on the same land causes it, and one case can stop exports to the EU.",
    "onion": "white rot, a soil disease and the most destructive onion disease; fields can need several rounds of trap crops.",
    "maize": "stem borers; April sowing is the most infested and the larvae survive the winter.",
    "cotton": "pink and spiny bollworms; the pink bollworm survives as resting larvae and the moths come out the next spring.",
    "soybean": "sucking pests (whitefly, spider mites, aphids, leafhoppers) and the cotton leafworm; later sowing lowered spider mites in one trial.",
    "sesame": "capsule borer (the main insect), phyllody (spread by leafhoppers), Fusarium wilt and charcoal rot in the soil, and whitefly.",
}
PEST_AR = {
    "wheat": "الصدأ بينتقل في الهوا، فالدورة الزراعية مش بتتحكم فيه.",
    "berseem": "ملقيناش آفات كبيرة في بحثنا (ده مش معناه إن مفيش).",
    "faba_bean": "الهالوك (عشب متطفل على الجذور) ممكن يقلل المحصول جامد، وفيروس الاصفرار النخري للفول ضرب حقول كمان.",
    "sugar_beet": "نيماتودا تعقد الجذور (ديدان صغيرة في التربة) آفة رئيسية؛ الزراعة من أكتوبر وبعده قللتها في التجارب.",
    "potato": "العفن البني؛ المصدّرين بيقولوا إن كتر البطاطس في نفس الأرض بيسببه، وحالة واحدة ممكن توقف التصدير للاتحاد الأوروبي.",
    "onion": "العفن الأبيض مرض في التربة وهو أخطر أمراض البصل؛ الأرض ممكن تحتاج كذا دورة من المحاصيل المصيدة.",
    "maize": "ثاقبات الساق؛ زراعة أبريل أكتر إصابة، واليرقات بتعدي الشتا.",
    "cotton": "دودة اللوز القرنفلية والشوكية؛ القرنفلية بتعدي الشتا يرقات ساكنة والفراشات بتطلع الربيع اللي بعده.",
    "soybean": "الآفات الماصة (الذبابة البيضاء والعنكبوت الأحمر والمن والجاسيد) ودودة ورق القطن؛ الزراعة المتأخرة قللت العنكبوت في تجربة واحدة.",
    "sesame": "ثاقبة القرون (الحشرة الرئيسية) والتورد (بتنقله الجاسيد) والذبول الفيوزاريومي والعفن الفحمي في التربة والذبابة البيضاء.",
}

GAPS_GLOBAL_AR = [
    "احتياج المياه هنا مستوى (قليل / متوسط / كبير) للمقارنة بين المحاصيل، مش كمية ري. خلية بيانات ناسا بتقرا طلب الهوا للمياه في الصيف أعلى بحوالي 40% من محطة منشورة في شمال الدلتا.",
    "درجة توفير المصاريف مؤشر لتوفير التكلفة (مستوى المياه واحتياج السماد)، مش ربح. الأسعار بتظهر جنبها ومبتتضافش عليها.",
    "الطقس لخلية واحدة مساحتها حوالي 55 × 60 كم، والخضرة لست نقط (كل نقطة 250 متر)، فده وصف للمنطقة مش لحقل واحد.",
    "رطوبة التربة من SMAP L4 ‏(SPL4SMGP، 9 كم) مبتشوفش ري النيل، فهي معلومة خلفية مش داخلة في الدرجات.",
    "مواعيد المواسم دي مواعيد نموذجية من مكتبة المحاصيل، مش مواعيد حقلك.",
]

UI = {
    "en": {"plan": "Plan", "summer": "summer", "winter": "winter", "why": "Why this plan", "benefits": "What you gain",
           "trade_offs": "What you give up", "evidence": "NASA evidence", "warnings": "Watch out",
           "gaps": "What we do not know", "risks": "Check locally", "intro_title": "Your three plans",
           "marks": {"water": "Water mark", "soil": "Soil mark", "money": "Cost-saving mark (not profit)",
                     "heat": "Heat level", "goal": "Mark for your goal"},
           "tier": {"LOW": "Low", "MIDDLE": "Medium", "HIGH": "High"},
           "goals": {"save_money": "Save money", "save_water": "Save water", "improve_soil": "Improve the soil"},
           "main_only_box": "Only crops most farmers here grow"},
    "ar": {"plan": "الخطة", "summer": "صيفي", "winter": "شتوي", "why": "ليه الخطة دي", "benefits": "هتكسب إيه",
           "trade_offs": "هتتنازل عن إيه", "evidence": "أدلة ناسا", "warnings": "خد بالك",
           "gaps": "اللي منعرفوش", "risks": "اتأكد محليًا", "intro_title": "خططك التلاتة",
           "marks": {"water": "درجة المياه", "soil": "درجة التربة", "money": "درجة توفير المصاريف (مش ربح)",
                     "heat": "مستوى الحرارة", "goal": "درجة هدفك"},
           "tier": {"LOW": "قليل", "MIDDLE": "متوسط", "HIGH": "عالي"},
           "goals": {"save_money": "توفير الفلوس", "save_water": "توفير المياه", "improve_soil": "تحسين التربة"},
           "main_only_box": "المحاصيل اللي أغلب المزارعين هنا بيزرعوها بس"},
}
DISCLAIMER = {
    "en": "This tool compares plans using NASA data and written rules. It supports your own judgment and your "
          "local agronomist; it does not replace them, and it does not forecast yield or profit.",
    "ar": "الأداة دي بتقارن الخطط ببيانات ناسا وقواعد مكتوبة. هي بتدعم حكمك وحكم المهندس الزراعي عندكم، "
          "مش بتحل مكانهم، ومش بتتوقع المحصول ولا الربح.",
}
SOURCE_EN = "Source: NASA POWER (weather) and NASA MODIS (greenness), average of the 2011–2024 seasons, on the model season dates."
SOURCE_AR = "المصدر: ناسا POWER (الطقس) وناسا MODIS (الخضرة)، متوسط مواسم 2011 إلى 2024، على مواعيد الموسم النموذجية."


# ------------------------------------------------------------------ small helpers
def _r(x: float) -> int:
    return int(x + 0.5)


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _date(s: str, lang: str) -> str:
    day, mon = s.split()
    return f"{int(day)} {mon}" if lang == "en" else f"{int(day)} {MONTH_AR[mon]}"


def _days_ar(n: int) -> str:
    """Arabic counted noun: 3 to 10 and zero take the plural (أيام); other numbers take the singular (يوم)."""
    return f"{n} أيام" if (n == 0 or 3 <= n <= 10) else f"{n} يوم"


def _ar(c: str, definite: bool = True) -> str:
    return CROP_AR[c][1 if definite else 0]


# ------------------------------------------------------------------ facts (no language yet)
def facts(eng: Engine, res: dict, tag: str) -> dict:
    o, a, b = res[tag], res["A"], res["B"]
    s, w = o["summer"], o["winter"]
    P = eng.pairs
    row = P[(P.summer == s) & (P.winter == w)].iloc[0]
    arow = P[(P.summer == a["summer"]) & (P.winter == a["winter"])].iloc[0]
    sc, asc = o["scores"], a["scores"]
    ev = {}
    for c in (s, w):
        e = eng.ev.loc[c]
        ev[c] = {"sow": e["model_sow"], "end": e["model_end"], "h": _r(e["hot_days_35"]), "rain": float(e["rain_mm"]),
                 "r": _r(e["rain_mm"]), "g": round(float(e["greenness"]), 2)}
    return {
        "tag": tag, "s": s, "w": w, "goal": res["goal"], "main_only": res["main_crops_only"],
        "a_best": res["a_is_best_or_tied"], "soil_min": res["soil_minimum"],
        "g": _r(sc["goal"]), "a_g": _r(asc["goal"]), "best": _r(max(asc["goal"], b["scores"]["goal"])),
        "water": _r(sc["water"]), "soil": _r(sc["soil"]), "money": _r(sc["money_saving_proxy"]),
        "a_water": _r(asc["water"]), "a_soil": _r(asc["soil"]), "a_money": _r(asc["money_saving_proxy"]),
        "heat_level": sc["heat_level"], "heat": _r(row["heat_days_35"]), "a_heat": _r(arow["heat_days_35"]),
        "tiers": (row["water_tier_summer"], row["water_tier_winter"]),
        "ncls": (eng.ncls[s], eng.ncls[w]), "a_ncls": (eng.ncls[a["summer"]], eng.ncls[a["winter"]]),
        "same_family": bool(row["same_family"]), "family": eng.family[s],
        "clash": bool(row["timing_clash"]), "gap_w2s": int(row["gap_winter_end_to_summer_sow_days"]),
        "gap_s2w": int(row["gap_summer_end_to_winter_sow_days"]),
        "warn_codes": [x["code"] for x in o["warnings"]],
        "warn_en": [x["text"] for x in o["warnings"]],
        "fallback": any(x["code"] == "SOIL_MINIMUM_NOT_MET" for x in o["warnings"]),
        "passes": bool(sc["passes_soil_minimum"]),
        "gaps_en": list(o["information_gaps"]),
        "sow_s": eng.lib.loc[s, "model_sow"], "end_w": eng.lib.loc[w, "model_end"],
        "ev": ev,
    }


def _deltas(f: dict) -> dict:
    return {"water": f["water"] - f["a_water"], "soil": f["soil"] - f["a_soil"],
            "money": f["money"] - f["a_money"], "heat": f["a_heat"] - f["heat"]}      # heat: positive = fewer hot days


def _strong_legumes(f: dict) -> list[str]:
    return [c for c, k in zip((f["s"], f["w"]), f["ncls"]) if k == "legume"]


def _gap_lines_ar(f: dict) -> list[str]:
    out = list(GAPS_GLOBAL_AR)
    for c in (f["s"], f["w"]):
        if c in NO_CROSS_CHECK:
            out.append(f"مستوى المياه بتاع {_ar(c)} جاي من بيانات ناسا بس: مفيش قيمة من الفاو (GAEZ) نراجعه بيها.")
        if c in NO_COST_DATA:
            out.append(f"ملقيناش أرقام تكلفة بتاعة {_ar(c)}.")
    return out


# ------------------------------------------------------------------ English
def _text_en(f: dict) -> dict:
    s, w, tag, goal = f["s"], f["w"], f["tag"], f["goal"]
    S, W = CROP_EN[s], CROP_EN[w]
    G = GOAL_EN[goal]
    scope = " among everyday crops" if f["main_only"] else ""
    money_note = " The money mark counts running costs (water and fertiliser), not profit." if goal == "save_money" else ""
    d = _deltas(f)

    if tag == "A":
        goal_s = (f"On your goal ({G}), your plan scores {f['g']} out of 100, at least as high as the best other plan{scope}."
                  if f["a_best"] else
                  f"On your goal ({G}), your plan scores {f['g']} out of 100; the best plan{scope} scores {f['best']}.")
    elif tag == "B":
        goal_s = (f"Your plan already scores {f['a_g']} on your goal ({G}), at least as high as this plan ({f['g']}). "
                  f"We show this one as the best other choice."
                  if f["a_best"] else
                  f"This is the best plan we found{scope} for your goal ({G}): it scores {f['g']} out of 100, "
                  f"against {f['a_g']} for your plan.")
    else:
        goal_s = (f"No other plan reaches our soil minimum of {f['soil_min']}; this one has the best soil mark left "
                  f"({f['soil']}) and scores {f['g']} out of 100 on your goal ({G})."
                  if f["fallback"] else
                  f"This plan scores {f['g']} out of 100 on your goal ({G}) and {f['soil']} on soil health, "
                  f"above our minimum of {f['soil_min']}.")
    goal_s += money_note

    t1, t2 = f["tiers"]
    water_s = (f"Water: both {S} and {W} need {TIER_EN[t1]} water." if t1 == t2 else
               f"Water: {S} needs {TIER_EN[t1]} water and {W} needs {TIER_EN[t2]} water.")

    clauses = []
    for c, k in zip((s, w), f["ncls"]):
        C = CROP_EN[c]
        clauses.append({
            "legume": f"{C} fixes nitrogen and leaves some for the next crop",
            "legume_weak": f"{C} fixes nitrogen, but its seed takes most of it, so the gain is small",
            "heavy": f"{C} takes a lot of nitrogen from the soil",
            "moderate": f"{C} takes a moderate amount of nitrogen",
            "light": f"{C} takes little nitrogen"}[k])
    clauses.append(
        f"the two crops are from the same plant family ({FAMILY_EN[f['family']]}), so diseases and pests can carry over"
        if f["same_family"] else
        "the two crops are from different plant families, which helps break disease cycles")
    soil_s = "Soil: " + "; ".join(clauses) + "."

    benefits, trade = [], []
    if tag == "A":
        if f["water"] >= 100:
            benefits.append(f"Needs little water: water mark {f['water']} out of 100.")
        elif f["water"] >= 75:
            benefits.append(f"Fairly low water need: water mark {f['water']} out of 100.")
        if f["soil"] >= 75:
            benefits.append(f"Good for the soil: soil mark {f['soil']} out of 100.")
        if f["money"] >= 75:
            benefits.append(f"Low running costs: cost-saving mark {f['money']} out of 100 (this is not profit).")
    else:
        if d["water"] >= 10:
            benefits.append(f"Needs less water: the water mark goes from {f['a_water']} to {f['water']} out of 100.")
        if d["soil"] >= 10:
            benefits.append(f"Better for the soil: the soil mark goes from {f['a_soil']} to {f['soil']} out of 100.")
        if d["money"] >= 10:
            benefits.append(f"Lower running costs: the cost-saving mark goes from {f['a_money']} to {f['money']} out of 100 (this is not profit).")
        if d["heat"] >= 10:
            benefits.append(f"Fewer very hot days: about {f['heat']} days a year at 35 °C or more during the two seasons, against {f['a_heat']} for your plan.")
        new = _strong_legumes(f)
        if new and not any(k == "legume" for k in f["a_ncls"]):
            benefits.append(f"Includes {CROP_EN[new[0]]}, which fixes nitrogen for the next crop.")
        if not benefits:
            benefits.append("No clear gain over your plan on the marks we measure.")
        if d["water"] <= -10:
            trade.append(f"Needs more water: the water mark goes from {f['a_water']} to {f['water']} out of 100.")
        if d["soil"] <= -10:
            trade.append(f"Less good for the soil: the soil mark goes from {f['a_soil']} to {f['soil']} out of 100.")
        if d["money"] <= -10:
            trade.append(f"Higher running costs: the cost-saving mark goes from {f['a_money']} to {f['money']} out of 100 (this is not profit).")
        if d["heat"] <= -10:
            trade.append(f"More very hot days: about {f['heat']} days a year at 35 °C or more during the two seasons, against {f['a_heat']} for your plan.")

    evidence = []
    for c in (s, w):
        e = f["ev"][c]
        line = (f"{_cap(CROP_EN[c])}, {_date(e['sow'], 'en')} to {_date(e['end'], 'en')}: about {e['h']} days at 35 °C or more, "
                f"about {e['r']} mm of rain and plant greenness (NDVI) of about {e['g']:.2f}.")
        if e["rain"] < 5:
            line += " There is almost no rain, so it depends on irrigation."
        evidence.append(line)

    return {
        "title": f"{_cap(S)} (summer), then {W} (winter)",
        "role": {"A": "Your current plan",
                 "B": "Best other plan for your goal" if f["a_best"] else "Best plan for your goal",
                 "C": ("Best remaining plan (below our soil minimum)" if f["fallback"]
                      else "Good for your goal and kind to the soil")}[tag],
        "why": {"goal": goal_s, "water": water_s, "soil": soil_s},
        "benefits": benefits, "trade_offs": trade, "evidence": evidence, "evidence_source": SOURCE_EN,
        "warnings": list(f["warn_en"]), "information_gaps": list(f["gaps_en"]),
        "risks_for_local_review": [f"{_cap(CROP_EN[c])}: {PEST_EN[c]}" for c in (s, w)],
    }


# ------------------------------------------------------------------ Arabic (simple Egyptian; sentences avoid gender agreement)
def _text_ar(f: dict) -> dict:
    s, w, tag, goal = f["s"], f["w"], f["tag"], f["goal"]
    S, W = _ar(s), _ar(w)
    G = GOAL_AR[goal]
    scope = " بين المحاصيل المعروفة" if f["main_only"] else ""
    money_note = " درجة توفير المصاريف بتحسب تكلفة التشغيل (المياه والسماد) مش الربح." if goal == "save_money" else ""
    d = _deltas(f)

    if tag == "A":
        goal_s = (f"في هدفك ({G}) خطتك الحالية درجتها {f['g']} من 100، ومش أقل من أحسن خطة تانية{scope}."
                  if f["a_best"] else
                  f"في هدفك ({G}) خطتك الحالية درجتها {f['g']} من 100، وأحسن خطة{scope} درجتها {f['best']}.")
    elif tag == "B":
        goal_s = (f"خطتك الحالية درجتها {f['a_g']} في هدفك ({G})، ومش أقل من الخطة دي ({f['g']}). عرضناها كأحسن اختيار تاني."
                  if f["a_best"] else
                  f"دي أحسن خطة{scope} لقيناها لهدفك ({G}): درجتها {f['g']} من 100، مقابل {f['a_g']} لخطتك الحالية.")
    else:
        goal_s = (f"مفيش خطة تانية توصل للحد الأدنى بتاعنا للتربة ({f['soil_min']})؛ دي أحسن درجة تربة فاضلة ({f['soil']})، "
                  f"ودرجتها {f['g']} من 100 في هدفك ({G})."
                  if f["fallback"] else
                  f"الخطة دي درجتها {f['g']} من 100 في هدفك ({G})، ودرجتها في صحة التربة {f['soil']}، فوق الحد الأدنى بتاعنا ({f['soil_min']}).")
    goal_s += money_note

    t1, t2 = f["tiers"]
    water_s = (f"المياه: احتياج {S} و{W} للمياه {TIER_AR_ADJ[t1]}." if t1 == t2 else
               f"المياه: احتياج {S} للمياه {TIER_AR_ADJ[t1]}، واحتياج {W} للمياه {TIER_AR_ADJ[t2]}.")

    clauses = []
    for c, k in zip((s, w), f["ncls"]):
        C = _ar(c)
        clauses.append({
            "legume": f"{C} من المحاصيل اللي بتثبّت النيتروجين وبتسيب جزء منه للمحصول اللي بعده",
            "legume_weak": f"{C} من المحاصيل اللي بتثبّت النيتروجين، بس البذرة بتاخد معظمه فالفايدة صغيرة",
            "heavy": f"{C} من المحاصيل اللي بتاخد نيتروجين كتير من التربة",
            "moderate": f"{C} من المحاصيل اللي بتاخد نيتروجين متوسط",
            "light": f"{C} من المحاصيل اللي بتاخد نيتروجين قليل"}[k])
    clauses.append(
        f"المحصولين من نفس العيلة النباتية ({FAMILY_AR[f['family']]})، فالأمراض والآفات ممكن تنتقل من واحد للتاني"
        if f["same_family"] else
        "المحصولين من عيلتين نباتيتين مختلفتين، وده بيساعد على كسر دورة الأمراض")
    soil_s = "التربة: " + "؛ ".join(clauses) + "."

    benefits, trade = [], []
    if tag == "A":
        if f["water"] >= 100:
            benefits.append(f"محتاجة مياه قليلة: درجة المياه {f['water']} من 100.")
        elif f["water"] >= 75:
            benefits.append(f"احتياجها للمياه قليل نسبيًا: درجة المياه {f['water']} من 100.")
        if f["soil"] >= 75:
            benefits.append(f"كويسة للتربة: درجة التربة {f['soil']} من 100.")
        if f["money"] >= 75:
            benefits.append(f"مصاريف تشغيل قليلة: درجة توفير المصاريف {f['money']} من 100 (ده مش ربح).")
    else:
        if d["water"] >= 10:
            benefits.append(f"محتاجة مياه أقل: درجة المياه ترتفع من {f['a_water']} إلى {f['water']} من 100.")
        if d["soil"] >= 10:
            benefits.append(f"أحسن للتربة: درجة التربة ترتفع من {f['a_soil']} إلى {f['soil']} من 100.")
        if d["money"] >= 10:
            benefits.append(f"مصاريف تشغيل أقل: درجة توفير المصاريف ترتفع من {f['a_money']} إلى {f['money']} من 100 (ده مش ربح).")
        if d["heat"] >= 10:
            benefits.append(f"أيام حر شديد أقل: حوالي {_days_ar(f['heat'])} في السنة حرارتها 35 درجة أو أكتر خلال الموسمين، مقابل {f['a_heat']} في خطتك.")
        new = _strong_legumes(f)
        if new and not any(k == "legume" for k in f["a_ncls"]):
            benefits.append(f"فيها {_ar(new[0])}، ودي من المحاصيل اللي بتثبّت النيتروجين للمحصول اللي بعده.")
        if not benefits:
            benefits.append("مفيش مكسب واضح عن خطتك في الدرجات اللي بنقيسها.")
        if d["water"] <= -10:
            trade.append(f"محتاجة مياه أكتر: درجة المياه تنزل من {f['a_water']} إلى {f['water']} من 100.")
        if d["soil"] <= -10:
            trade.append(f"أقل في صحة التربة: درجة التربة تنزل من {f['a_soil']} إلى {f['soil']} من 100.")
        if d["money"] <= -10:
            trade.append(f"مصاريف تشغيل أكتر: درجة توفير المصاريف تنزل من {f['a_money']} إلى {f['money']} من 100 (ده مش ربح).")
        if d["heat"] <= -10:
            trade.append(f"أيام حر شديد أكتر: حوالي {_days_ar(f['heat'])} في السنة حرارتها 35 درجة أو أكتر خلال الموسمين، مقابل {f['a_heat']} في خطتك.")

    evidence = []
    for c in (s, w):
        e = f["ev"][c]
        line = (f"{_ar(c)}، من {_date(e['sow'], 'ar')} لحد {_date(e['end'], 'ar')}: حوالي {_days_ar(e['h'])} حرارتها 35 درجة أو أكتر، "
                f"وحوالي {e['r']} مم مطر، وخضرة النبات (NDVI) حوالي {e['g']:.2f}.")
        if e["rain"] < 5:
            line += " المطر شبه معدوم، فالمحصول بيعتمد على الري."
        evidence.append(line)

    warnings = []
    for code in f["warn_codes"]:
        if code == "TIMING_CLASH":
            if f["gap_w2s"] < 0:
                warnings.append(
                    f"ميعاد زراعة {S} تقريبًا {_date(f['sow_s'], 'ar')}، فلازم المحصول الشتوي اللي قبله يتحصد قبل كده. "
                    f"ميعاد انتهاء {W} عادةً بعد كده بحوالي {_days_ar(-f['gap_w2s'])} ({_date(f['end_w'], 'ar')})، "
                    f"فهتحتاج تحصد بدري أو تأخّر زراعة {S}. ملقيناش مصدر لميعاد زراعة متأخر، فالأداة مش بتقول ميعاد معين.")
            else:
                warnings.append(f"زراعة {W} هتبقى قبل حصاد {S}.")
        elif code == "SAME_FAMILY":
            warnings.append(f"{S} و{W} من نفس العيلة النباتية ({FAMILY_AR[f['family']]})، وده ممكن ينقل الأمراض والآفات من محصول للتاني.")
        elif code == "MINOR_CROP":
            pass     # added below, once per small crop, in the same order as the engine
        elif code == "SOIL_MINIMUM_NOT_MET":
            warnings.append(f"مفيش خطة تانية توصل للحد الأدنى للتربة ({f['soil_min']}) بالإعدادات دي؛ دي أحسن درجة تربة فاضلة.")
    # small-crop warnings sit after the others in the engine, one per small crop in (summer, winter) order
    for c in (s, w):
        if c in MINOR_CROPS:
            warnings.append(f"{_ar(c)} محصول صغير في مصر ومالقيناش له مساحة في المنوفية: اتأكد من التقاوي والمشتري قبل ما تعتمد عليه.")

    return {
        "title": f"{CROP_AR[s][0]} (صيفي)، وبعده {CROP_AR[w][0]} (شتوي)",
        "role": {"A": "خطتك الحالية",
                 "B": "أحسن خطة تانية لهدفك" if f["a_best"] else "أحسن خطة لهدفك",
                 "C": ("أحسن خطة متاحة (تحت الحد الأدنى للتربة)" if f["fallback"]
                      else "كويسة لهدفك وكويسة للتربة")}[tag],
        "why": {"goal": goal_s, "water": water_s, "soil": soil_s},
        "benefits": benefits, "trade_offs": trade, "evidence": evidence, "evidence_source": SOURCE_AR,
        "warnings": warnings, "information_gaps": _gap_lines_ar(f),
        "risks_for_local_review": [f"{_ar(c)}: {PEST_AR[c]}" for c in (s, w)],
    }


# ------------------------------------------------------------------ public function
def explain(eng: Engine, res: dict, lang: str = "en") -> dict:
    if lang not in LANGS:
        raise ValueError(f"lang must be one of {LANGS}")
    build = _text_en if lang == "en" else _text_ar
    goal = res["goal"]
    out = {tag: build(facts(eng, res, tag)) for tag in "ABC"}
    if lang == "en":
        intro = f"Your goal: {GOAL_EN[goal]}. Plan A is what you grow now. Plans B and C are alternatives."
        if res["a_is_best_or_tied"]:
            intro += " Your plan already scores at least as high on this goal as the best other plan."
    else:
        intro = f"هدفك: {GOAL_AR[goal]}. الخطة A هي اللي بتزرعها دلوقتي. الخطتين B وC بدايل."
        if res["a_is_best_or_tied"]:
            intro += " خطتك درجتها في الهدف ده مش أقل من أحسن خطة تانية."
    out["intro"] = intro
    out["disclaimer"] = DISCLAIMER[lang]
    out["ui"] = UI[lang]
    return out


# ------------------------------------------------------------------ the checker
NUM = re.compile(r"\d+(?:\.\d+)?")
CONST_NUMBERS = {100, 35, 2011, 2024, 40, 55, 60, 250, 9}
ALLOWED_LATIN = ("SPL4SMGP", "NASA", "NDVI", "MODIS", "POWER", "SMAP", "GAEZ", "FAO", "L4")
PRODUCT_TOKENS = ("SPL4SMGP", "SMAP L4")        # names that carry a digit; removed before numbers are checked


def _nums(text: str) -> list[float]:
    for tok in PRODUCT_TOKENS:
        text = text.replace(tok, "")
    return [float(x) for x in NUM.findall(text)]


def _sections(opt: dict):
    for k, v in opt["why"].items():
        yield f"why.{k}", [v]
    for k in ("benefits", "trade_offs", "evidence", "warnings", "information_gaps", "risks_for_local_review"):
        yield k, opt[k]
    yield "evidence_source", [opt["evidence_source"]]


def check_option(eng: Engine, res: dict, tag: str, en: dict, ar: dict) -> list[str]:
    """Return a list of problems (empty = all good) for one option in both languages."""
    f = facts(eng, res, tag)
    problems = []
    allowed = set(CONST_NUMBERS) | {f["soil_min"], f["g"], f["a_g"], f["best"], f["water"], f["soil"], f["money"],
                                    f["a_water"], f["a_soil"], f["a_money"], f["heat"], f["a_heat"]}
    for c in (f["s"], f["w"]):
        e = f["ev"][c]
        allowed |= {e["h"], e["r"], e["g"], int(e["sow"].split()[0]), int(e["end"].split()[0])}
    allowed |= {int(f["sow_s"].split()[0]), int(f["end_w"].split()[0]), abs(f["gap_w2s"])}
    plan_crops = {f["s"], f["w"]}
    other_en = [CROP_EN[c] for c in CROP_EN if c not in plan_crops]
    other_ar = [x for c in CROP_AR if c not in plan_crops for x in CROP_AR[c]]
    minor_in_plan = any(c in MINOR_CROPS for c in plan_crops)

    for lang, opt in (("en", en), ("ar", ar)):
        for sec, items in _sections(opt):
            for text in items:
                where = f"[{tag} {lang} {sec}]"
                if not text.strip():
                    problems.append(f"{where} empty text")
                if any(b in text for b in ("{", "}", "None", "nan", "NaN")):
                    problems.append(f"{where} leftover placeholder or blank value: {text[:60]}")
                for n in _nums(text):
                    if n not in allowed:
                        problems.append(f"{where} number {n} is not one of the engine's facts: {text[:70]}")
                if sec not in ("risks_for_local_review", "information_gaps"):
                    for name in (other_en if lang == "en" else other_ar):
                        if re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", text):
                            problems.append(f"{where} mentions {name}, which is not in this plan")
                if lang == "ar":
                    t = text
                    for tok in ALLOWED_LATIN:
                        t = t.replace(tok, "")
                    if re.search(r"[A-Za-z]", t):
                        problems.append(f"{where} has English letters in the Arabic text: {text[:60]}")
                    if not re.search(r"[؀-ۿ]", text):
                        problems.append(f"{where} has no Arabic letters")
    # the English and the Arabic must say the same things: same sections, same item counts, same numbers
    for (sec_e, it_e), (sec_a, it_a) in zip(_sections(en), _sections(ar)):
        if sec_e != sec_a or len(it_e) != len(it_a):
            problems.append(f"[{tag}] English and Arabic differ in {sec_e}: {len(it_e)} vs {len(it_a)} items")
            continue
        if sec_e in ("risks_for_local_review",):
            continue
        for te, ta in zip(it_e, it_a):
            if sorted(_nums(te)) != sorted(_nums(ta)):
                problems.append(f"[{tag}] numbers differ between English and Arabic in {sec_e}: {_nums(te)} vs {_nums(ta)}")
    # claims must be true
    flat_en = " ".join(t for _, items in _sections(en) for t in items if _ != "information_gaps")
    flat_en_nogap = " ".join(t for sec, items in _sections(en) if sec != "information_gaps" for t in items)
    legume_in_plan = any(k in ("legume", "legume_weak") for k in f["ncls"])
    if "fixes nitrogen" in flat_en_nogap and not legume_in_plan:
        problems.append(f"[{tag}] says 'fixes nitrogen' but no legume is in the plan")
    if legume_in_plan and "fixes nitrogen" not in en["why"]["soil"]:
        problems.append(f"[{tag}] soil sentence misses the legume")
    if ("same plant family" in flat_en_nogap) != f["same_family"]:
        problems.append(f"[{tag}] same-family wording does not match the facts")
    if ("harvested by then" in flat_en_nogap) != f["clash"]:
        problems.append(f"[{tag}] timing warning does not match the facts")
    if ("small crop" in flat_en_nogap) != minor_in_plan:
        problems.append(f"[{tag}] small-crop warning does not match the facts")
    if f["clash"] != (len([c for c in f["warn_codes"] if c == "TIMING_CLASH"]) > 0):
        problems.append(f"[{tag}] clash flag and warning codes disagree")
    if ("Needs little water" in flat_en_nogap) and f["water"] < 100:
        problems.append(f"[{tag}] says 'little water' but the water mark is {f['water']}")
    if ("Good for the soil" in flat_en_nogap) and f["soil"] < 75:
        problems.append(f"[{tag}] says 'good for the soil' but the soil mark is {f['soil']}")
    if f["fallback"] != ("below our soil minimum" in en["role"]):
        problems.append(f"[{tag}] role label does not match the soil-minimum fallback")
    if en["information_gaps"] != f["gaps_en"] or len(ar["information_gaps"]) != len(en["information_gaps"]) \
            or en["information_gaps"][:len(GLOBAL_GAPS)] != list(GLOBAL_GAPS):
        problems.append(f"[{tag}] information gaps differ from the engine's list")
    if len(en["warnings"]) != len(ar["warnings"]):
        problems.append(f"[{tag}] different number of warnings in English and Arabic")
    if tag == "B" and "best plan we found" in en["why"]["goal"]:
        pool = eng.pairs[~eng.pairs.timing_clash & ~((eng.pairs.summer == res["A"]["summer"]) & (eng.pairs.winter == res["A"]["winter"]))]
        if res["main_crops_only"]:
            pool = pool[~pool.summer.isin(MINOR_CROPS) & ~pool.winter.isin(MINOR_CROPS)]
        from rotation_engine import GOAL_COLUMN
        if res["B"]["scores"]["goal"] != pool[GOAL_COLUMN[res["goal"]]].max():
            problems.append(f"[{tag}] says 'best plan' but it is not the top mark")
    if tag == "C" and "above our minimum" in en["why"]["goal"] and not f["passes"]:
        problems.append(f"[{tag}] says it passes the soil minimum but it does not")
    if tag == "C" and f["fallback"] and ("No other plan reaches" not in en["why"]["goal"] or
                                          not any("No other plan reaches" in x for x in en["warnings"])):
        problems.append(f"[{tag}] soil-minimum fallback is not announced")
    return problems


def check_all(eng: Engine | None = None) -> tuple[int, list[str]]:
    eng = eng or Engine()
    problems, runs = [], 0
    for main_only, goal, s, w in itertools.product((False, True), GOALS, eng.summer, eng.winter):
        res = eng.recommend(s, w, goal, main_crops_only=main_only)
        en, ar = explain(eng, res, "en"), explain(eng, res, "ar")
        runs += 1
        for tag in "ABC":
            problems += [f"({s}+{w}, {goal}, main_only={main_only}) " + p for p in check_option(eng, res, tag, en[tag], ar[tag])]
        if explain(eng, res, "en") != en or explain(eng, res, "ar") != ar:
            problems.append("explanations are not repeatable")
    return runs, problems


if __name__ == "__main__":
    engine = Engine()
    n, probs = check_all(engine)
    print(f"checked {n} farmer situations x 3 plans x 2 languages")
    print("ALL CHECKS PASSED" if not probs else f"{len(probs)} PROBLEMS")
    for p in probs[:25]:
        print(" -", p)
    sys.exit(1 if probs else 0)
