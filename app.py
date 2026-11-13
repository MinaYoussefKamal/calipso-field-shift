"""Field Shift · Monufia: a crop-rotation planner built on NASA data (team CALIPSO).

Pages
  1. Your plans     - the farmer enters his summer crop, winter crop and goal; three plans come back (A, B, C).
  2. NASA evidence  - monthly weather and greenness for Monufia, from the files shipped in planner/.
  3. How it works   - the rules, the data, and what the tool cannot do.

The plan engine (planner/rotation_engine.py) is a written-rules "expert system", not machine learning.
The sentences (planner/explainer.py) are pre-written recipes filled with the engine's numbers, in English and
Egyptian Arabic. No live AI, no live API: every number on the site comes from the files in planner/.
"""
from __future__ import annotations

import base64
import calendar
import html
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
PLANNER = ROOT / "planner"
sys.path.insert(0, str(PLANNER))
import explainer as ex  # noqa: E402
import plan_text  # noqa: E402
import price_cards as pc  # noqa: E402
from rotation_engine import GOALS, Engine  # noqa: E402

st.set_page_config(page_title="Field Shift · Monufia", page_icon="🌱", layout="wide")

# ---------------------------------------------------------------- language
if "lang" not in st.session_state:
    st.session_state.lang = "en"
LANG = st.session_state.lang


def t(en: str, ar: str) -> str:
    return ar if LANG == "ar" else en


def esc(s: str) -> str:
    return html.escape(str(s))


# ---------------------------------------------------------------- data
@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    return Engine()


@st.cache_data(show_spinner=False)
def load_profile() -> pd.DataFrame:
    return pd.read_csv(PLANNER / "monufia_month_profile.csv")


ENG = get_engine()
SUMMER = list(dict.fromkeys(ENG.pairs["summer"]))
WINTER = list(dict.fromkeys(ENG.pairs["winter"]))
MONTH_ABBR = list(calendar.month_abbr)[1:]


def crop_label(c: str) -> str:
    return plan_text.crop_label(c, LANG)


def month_label(m: int) -> str:
    """m = 1..12"""
    return ex.MONTH_AR[MONTH_ABBR[m - 1]] if LANG == "ar" else calendar.month_name[m]


def join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if LANG == "ar":
        return "، ".join(names[:-1]) + " و" + names[-1]
    return ", ".join(names[:-1]) + " and " + names[-1]


DEFAULT_PROFILE = dict(summer="maize", winter="wheat", goal="save_water", main_only=True)
if "profile" not in st.session_state:
    st.session_state.profile = DEFAULT_PROFILE.copy()


# ---------------------------------------------------------------- small pieces
def hero(label: str, title: str, body: str) -> None:
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{esc(label)}</div><h1>{esc(title)}</h1><p>{esc(body)}</p>'
        f'<span class="pill">{t("RESEARCH PROTOTYPE", "نموذج تجريبي")} · CALIPSO</span></div>',
        unsafe_allow_html=True)


def bullets(items: list[str]) -> None:
    if items:
        st.markdown("\n".join(f"- {s}" for s in items))


def mark_bar(label: str, value: float, is_goal: bool) -> str:
    v = ex._r(value)
    cls = "fill goal" if is_goal else "fill"
    return (f'<div class="mark"><div class="mrow"><span>{esc(label)}</span>'
            f'<b><bdi dir="ltr">{v}/100</bdi></b></div>'
            f'<div class="track"><div class="{cls}" style="width:{max(0, min(100, v))}%"></div></div></div>')


def plan_card(tag: str, o: dict, r: dict, ui: dict, goal: str, summer: str, winter: str) -> None:
    sc = r["scores"]
    goal_key = {"save_money": "money", "save_water": "water", "improve_soil": "soil"}[goal]
    with st.container(border=True, key=f"plan_{tag}"):
        st.markdown(
            f'<div class="role role-{tag}">{esc(ui["plan"])} {tag} · {esc(o["role"])}</div>'
            f'<h3 class="ptitle">{esc(o["title"])}</h3>'
            f'<div class="goalmark"><span>{esc(ui["marks"]["goal"])}</span>'
            f'<b><bdi dir="ltr">{ex._r(sc["goal"])}<small>/100</small></bdi></b></div>'
            + mark_bar(ui["marks"]["water"], sc["water"], goal_key == "water")
            + mark_bar(ui["marks"]["soil"], sc["soil"], goal_key == "soil")
            + mark_bar(ui["marks"]["money"], sc["money_saving_proxy"], goal_key == "money")
            + f'<div class="heat">{esc(ui["marks"]["heat"])}: <b>{esc(ui["tier"][sc["heat_level"]])}</b></div>',
            unsafe_allow_html=True)

        st.markdown(f'**{ui["why"]}**')
        st.markdown(o["why"]["goal"])
        st.markdown(o["why"]["water"])
        st.markdown(o["why"]["soil"])

        if o["benefits"]:
            st.markdown(f'**{ui["benefits"]}**')
            bullets(o["benefits"])
        if o["trade_offs"]:
            st.markdown(f'**{ui["trade_offs"]}**')
            bullets(o["trade_offs"])
        for w in o["warnings"]:
            st.warning(w)

        with st.expander(ui["evidence"]):
            bullets(o["evidence"])
            st.caption(o["evidence_source"])
        with st.expander(pc.TITLE[LANG]):
            for c in (summer, winter):
                st.markdown(f"**{crop_label(c)}**")
                bullets(pc.lines(c, LANG))
            st.caption(pc.SOURCE_NOTE[LANG])
        with st.expander(ui["gaps"]):
            bullets(o["information_gaps"])
        with st.expander(ui["risks"]):
            bullets(o["risks_for_local_review"])


# ---------------------------------------------------------------- page 1: your plans
def plans() -> None:
    hero(t("MONUFIA · YOUR ROTATION", "المنوفية · دورتك الزراعية"),
         t("Which crops should follow each other on your land?", "إيه المحاصيل اللي تيجي ورا بعض في أرضك؟"),
         t("Tell us what you grow now and what you want most. NASA data and simple written rules show three plans side by side.",
           "قولنا بتزرع إيه دلوقتي وإيه أهم حاجة عندك. بيانات ناسا وقواعد مكتوبة بسيطة بتعرض لك تلات خطط جنب بعض."))
    ui0 = ex.UI[LANG]
    prof = st.session_state.profile
    # Widget keys carry the language: when the language changes the widgets are rebuilt, so the drop-downs show
    # the new language (otherwise the browser keeps the old text). Widgets also forget their value when you
    # leave the page, so the choice is restored from the saved profile.
    wk = {k: f"w_{k}_{LANG}" for k in DEFAULT_PROFILE}
    for k in DEFAULT_PROFILE:
        if wk[k] not in st.session_state:
            st.session_state[wk[k]] = prof[k]

    left, right = st.columns([1.65, 1], gap="large")
    with left:
        st.subheader(t("Your rotation now", "دورتك دلوقتي"))
        st.caption(t("One summer crop and one winter crop, in one year.", "محصول صيفي ومحصول شتوي في السنة."))
        c1, c2 = st.columns(2)
        summer = c1.selectbox(t("Summer crop", "المحصول الصيفي"), SUMMER, format_func=crop_label, key=wk["summer"])
        winter = c2.selectbox(t("Winter crop", "المحصول الشتوي"), WINTER, format_func=crop_label, key=wk["winter"])
        goal = st.radio(t("What do you want most?", "إيه أهم حاجة عندك؟"), list(GOALS),
                        format_func=lambda g: ui0["goals"][g], horizontal=True, key=wk["goal"])
        main_only = st.checkbox(
            ui0["main_only_box"], key=wk["main_only"],
            help=t("Soybean and sesame are grown by few farmers here. Untick to include them in plans B and C.",
                   "الصويا والسمسم قليل اللي بيزرعهم هنا. شيل العلامة عشان يدخلوا في الخطتين B وC."))
    with right:
        st.markdown(
            f'<div class="note"><div class="eyebrow">CALIPSO · FIELD SHIFT</div>'
            f'<h2>{t("Three plans, one page.", "تلات خطط في صفحة واحدة")}</h2>'
            f'<p>{t("Plan A is what you grow now. Plan B is the best plan for your goal. Plan C is the best plan for your goal that also keeps the soil healthy.", "الخطة A هي اللي بتزرعه دلوقتي. الخطة B أحسن خطة لهدفك. الخطة C أحسن خطة لهدفك وكمان بتحافظ على التربة.")}</p></div>',
            unsafe_allow_html=True)
    prof.update(summer=summer, winter=winter, goal=goal, main_only=main_only)

    res = ENG.recommend(summer, winter, goal, main_crops_only=main_only)
    out = ex.explain(ENG, res, LANG)
    ui = out["ui"]

    st.subheader(ui["intro_title"])
    st.write(out["intro"])
    for tag, col in zip("ABC", st.columns(3, gap="medium")):
        with col:
            plan_card(tag, out[tag], res[tag], ui, goal, summer, winter)
    st.info(out["disclaimer"])
    st.download_button(t("Download my plans (text file)", "نزّل خططي (ملف نصي)"),
                       plan_text.build(out, res, summer, winter, LANG).encode("utf-8-sig"),
                       file_name="field-shift-monufia-plans.txt", mime="text/plain", type="primary")


# ---------------------------------------------------------------- page 2: NASA evidence
GREEN, BROWN = "#1f8a4c", "#c2571a"  # checked with the colour validator (green/brown pair, brown line is dashed)


def _style(chart: alt.Chart) -> alt.Chart:
    return (chart.properties(height=270, background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(gridColor="#d9e2cd", domainColor="#9fb08f", labelColor="#173d2a", titleColor="#173d2a",
                            labelFontSize=11, titleFontSize=12)
            .configure_legend(labelColor="#173d2a", labelFontSize=12, orient="top", title=None))


def line_chart(df: pd.DataFrame, cols: list[str], names: list[str], ytitle: str, zero: bool = True) -> alt.Chart:
    labels = df["label"].tolist()
    long = df.melt(id_vars="label", value_vars=cols, var_name="col", value_name="value")
    long["series"] = long["col"].map(dict(zip(cols, names)))
    colors = [GREEN, BROWN][: len(cols)]
    dashes = [[1, 0], [6, 4]][: len(cols)]
    base = alt.Chart(long).encode(
        x=alt.X("label:N", sort=labels, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("value:Q", title=ytitle, scale=alt.Scale(zero=zero)),
        color=alt.Color("series:N", scale=alt.Scale(domain=names, range=colors), legend=None),  # legend is drawn in HTML
        strokeDash=alt.StrokeDash("series:N", scale=alt.Scale(domain=names, range=dashes), legend=None),
        tooltip=[alt.Tooltip("label:N", title=""), alt.Tooltip("series:N", title=""),
                 alt.Tooltip("value:Q", title=ytitle, format=".2f")])
    return _style(base.mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=55, filled=True)))


def bar_chart(df: pd.DataFrame, col: str, ytitle: str, color: str = GREEN) -> alt.Chart:
    labels = df["label"].tolist()
    base = alt.Chart(df).encode(
        x=alt.X("label:N", sort=labels, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{col}:Q", title=ytitle),
        tooltip=[alt.Tooltip("label:N", title=""), alt.Tooltip(f"{col}:Q", title=ytitle, format=".1f")])
    return _style(base.mark_bar(color=color, cornerRadiusTopLeft=4, cornerRadiusTopRight=4))


def _peak_months(s: pd.Series, mode: str = "max") -> list[int]:
    """Months (1..12) where the series is at its highest (or lowest) value; ties return every month."""
    target = s.max() if mode == "max" else s.min()
    return [int(m) for m in s.index if s.loc[m] == target]


def evidence() -> None:
    raw = load_profile().copy()
    raw["month"] = raw["month"].astype(int)
    period = str(raw["period"].iloc[0]).replace("-", "–")
    hero(t("NASA EVIDENCE", "أدلة ناسا"),
         t("What NASA records say about Monufia", "إيه اللي بتقوله سجلات ناسا عن المنوفية"),
         t(f"Monthly averages for {period} for one area around Monufia. They describe the zone, not your field.",
           f"متوسطات شهرية من {period} لمنطقة واحدة حوالين المنوفية. بتوصف المنطقة، مش حقلك."))

    df = raw.copy()
    df["label"] = [month_label(m) for m in df["month"]]
    df["thirst"] = df["et0_mm"] - df["rain_mm"]
    df["thirst"] = (df["thirst"] / df["thirst"].max() * 100).round(0)
    by_month = df.set_index("month")

    change = float(df["t_mean_change_c"].mean())
    rain_year = float(df["rain_mm"].sum())
    hot_year = float(df["hot_days_35"].sum())
    a, b, c = st.columns(3)
    a.metric(t("Warmer than 1981–1990", "أدفى من 1981–1990"), f"\u2066+{change:.1f} °C\u2069")  # isolates keep "+0.9 °C" in order in Arabic
    b.metric(t("Rain in a whole year", "المطر في السنة كلها"), f"{rain_year:.0f} " + t("mm", "مم"))
    c.metric(t("Very hot days a year", "أيام الحر الشديد في السنة"), f"{hot_year:.0f}",
             help=t("Days at 35 °C or more", "أيام حرارتها 35 درجة أو أكتر"))

    unit_c = "°C"
    now_lbl, old_lbl = period, "1981–1990"  # plain numbers: no mixed-direction text in the legend

    # 1. temperature -------------------------------------------------------------------------
    st.subheader(t("Warmer than before", "أدفى من زمان"))
    big = int(df.loc[df["t_mean_change_c"].idxmax(), "month"])
    st.write(t(f"The average is about {change:.1f} {unit_c} warmer than in 1981–1990. The biggest rise is in {month_label(big)}: +{by_month.loc[big, 't_mean_change_c']:.1f} {unit_c}.",
               f"المتوسط أعلى بحوالي {change:.1f} درجة من 1981–1990. أكبر ارتفاع في {month_label(big)}: +{by_month.loc[big, 't_mean_change_c']:.1f} درجة."))
    d1 = df.rename(columns={"t_mean_c": "now", "t_mean_c_1981_90": "old"})
    st.markdown(f'<div class="legend"><span><i class="sw"></i><bdi dir="ltr">{esc(now_lbl)}</bdi></span>'
                f'<span><i class="sw dash"></i><bdi dir="ltr">{esc(old_lbl)}</bdi></span></div>', unsafe_allow_html=True)
    st.altair_chart(line_chart(d1, ["now", "old"], [now_lbl, old_lbl], t("Mean temperature (°C)", "متوسط الحرارة (°C)"),
                               zero=False), width="stretch")

    # 2. very hot days ---------------------------------------------------------------------
    st.subheader(t("Very hot days", "أيام الحر الشديد"))
    dim = {m: calendar.monthrange(2023, m)[1] for m in range(1, 13)}
    peak = _peak_months(by_month["hot_days_35"])
    most = [m for m in by_month.index if by_month.loc[m, "hot_days_35"] > dim[m] / 2]
    first, last = min(most), max(most)
    n_peak = by_month.loc[peak[0], "hot_days_35"]
    st.write(t(f"The most very hot days are in {join_names([month_label(m) for m in peak])}: about {n_peak:.0f} days a month at 35 °C or more. From {month_label(first)} to {month_label(last)}, more than half the days are that hot.",
               f"أكتر أيام حر شديد في {join_names([month_label(m) for m in peak])}: حوالي {ex._days_ar(int(round(n_peak)))} في الشهر حرارتها 35 درجة أو أكتر. من {month_label(first)} لـ{month_label(last)}، أكتر من نص الأيام بالحرارة دي."))
    st.altair_chart(bar_chart(df, "hot_days_35", t("Days at 35 °C or more", "أيام 35 درجة أو أكتر"), BROWN), width="stretch")

    # 3. water -----------------------------------------------------------------------------
    st.subheader(t("Little rain, thirsty air", "مطر قليل وهوا عطشان"))
    low, high = _peak_months(by_month["thirst"], "min"), _peak_months(by_month["thirst"], "max")
    rain_summer = float(by_month.loc[5:9, "rain_mm"].sum())
    st.write(t(f"Rain is small: about {rain_year:.0f} mm in a whole year, and only about {rain_summer:.0f} mm from May to September. The air asks for the most water in {join_names([month_label(m) for m in high])} and the least in {join_names([month_label(m) for m in low])}. These are relative numbers for comparing months, not irrigation amounts.",
               f"المطر قليل: حوالي {rain_year:.0f} مم في السنة كلها، وحوالي {rain_summer:.0f} مم بس من مايو لسبتمبر. الجو بيطلب أكتر مياه في {join_names([month_label(m) for m in high])} وأقل مياه في {join_names([month_label(m) for m in low])}. دي أرقام نسبية للمقارنة بين الشهور، مش كميات ري."))
    st.altair_chart(bar_chart(df, "thirst", t("How thirsty the air is (100 = the thirstiest month)", "عطش الهوا (100 = أعطش شهر)")),
                    width="stretch")

    # 4. greenness -------------------------------------------------------------------------
    st.subheader(t("How green the fields are", "الأرض خضرا قد إيه"))
    hi, lo = _peak_months(by_month["ndvi_mean6"]), _peak_months(by_month["ndvi_mean6"], "min")
    st.write(t(f"Satellites measure greenness (NDVI): higher means more green plants. Fields are greenest in {join_names([month_label(m) for m in hi])} ({by_month.loc[hi[0], 'ndvi_mean6']:.2f}) and least green in {join_names([month_label(m) for m in lo])} ({by_month.loc[lo[0], 'ndvi_mean6']:.2f}).",
               f"الأقمار الصناعية بتقيس الخضرة (NDVI): الرقم الأعلى يعني نبات أخضر أكتر. الأرض أخضر ما تكون في {join_names([month_label(m) for m in hi])} ({by_month.loc[hi[0], 'ndvi_mean6']:.2f}) وأقل خضرة في {join_names([month_label(m) for m in lo])} ({by_month.loc[lo[0], 'ndvi_mean6']:.2f})."))
    st.altair_chart(line_chart(df, ["ndvi_mean6"], [t("Greenness (NDVI)", "الخضرة (NDVI)")], t("Greenness (NDVI)", "الخضرة (NDVI)")),
                    width="stretch")

    with st.expander(t("Show the numbers", "اعرض الأرقام")):
        table = pd.DataFrame({
            t("Month", "الشهر"): df["label"],
            t("Mean temperature now (°C)", "متوسط الحرارة دلوقتي (°C)"): df["t_mean_c"],
            t("Mean temperature 1981–1990 (°C)", "متوسط الحرارة 1981–1990 (°C)"): df["t_mean_c_1981_90"],
            t("Days at 35 °C or more", "أيام 35 درجة أو أكتر"): df["hot_days_35"],
            t("Rain (mm)", "المطر (مم)"): df["rain_mm"],
            t("How thirsty the air is (100 = highest)", "عطش الهوا (100 = الأعلى)"): df["thirst"],
            t("Greenness (NDVI)", "الخضرة (NDVI)"): df["ndvi_mean6"]})
        st.dataframe(table, hide_index=True, width="stretch")
    bullets(ex.GAPS_GLOBAL_AR[2:3] + ex.GAPS_GLOBAL_AR[:1] if LANG == "ar" else ex.GLOBAL_GAPS[2:3] + ex.GLOBAL_GAPS[:1])
    st.caption(t("NASA POWER (weather) and NASA MODIS MOD13Q1 (greenness). Water numbers come from the FAO-56 method on NASA weather.",
                 "ناسا POWER (الطقس) وناسا MODIS MOD13Q1 (الخضرة). أرقام المياه محسوبة بطريقة FAO-56 على طقس ناسا."))


# ---------------------------------------------------------------- page 3: how it works
def about() -> None:
    hero(t("HOW IT WORKS", "إزاي بتشتغل"),
         t("No black box: you can read every rule.", "مفيش صندوق أسود: تقدر تقرا كل قاعدة."),
         t("The plans come from written rules and NASA data. Here is what the tool does, what it uses, and what it cannot do.",
           "الخطط طالعة من قواعد مكتوبة وبيانات ناسا. هنا هتلاقي الأداة بتعمل إيه، وبتستخدم إيه، ومبتعملش إيه."))
    n_plans, n_s, n_w = len(ENG.pairs), len(SUMMER), len(WINTER)
    soil_min = ENG.recommend(SUMMER[0], WINTER[0], "save_water")["soil_minimum"]

    st.subheader(t("What this tool does", "الأداة دي بتعمل إيه"))
    st.write(t("You tell us the summer crop and the winter crop you grow in one year, and what you want most: save money, save water, or improve the soil. We show three plans side by side:",
               "إنت بتقول لنا المحصول الصيفي والمحصول الشتوي اللي بتزرعهم في السنة، وإيه أهم حاجة عندك: توفير الفلوس، أو توفير المياه، أو تحسين التربة. واحنا بنعرض لك تلات خطط جنب بعض:"))
    bullets([t("**Plan A**: what you grow now.", "**الخطة A**: اللي بتزرعه دلوقتي."),
             t("**Plan B**: the best plan for your goal.", "**الخطة B**: أحسن خطة لهدفك."),
             t(f"**Plan C**: the best plan for your goal that also keeps the soil mark at {soil_min} or more.",
               f"**الخطة C**: أحسن خطة لهدفك وكمان درجة التربة فيها {soil_min} أو أكتر.")])

    st.subheader(t("How the plans get their marks", "الخطط بتاخد درجاتها إزاي"))
    st.write(t(f"We looked at {n_plans} yearly plans ({n_s} summer crops × {n_w} winter crops). Each plan gets three marks out of 100: water, soil and cost-saving. The marks come from written rules, not from machine learning, so anyone can read them:",
               f"بصينا على {n_plans} خطة سنوية ({n_s} محاصيل صيفي × {n_w} محاصيل شتوي). كل خطة بتاخد تلات درجات من 100: المياه والتربة وتوفير المصاريف. الدرجات طالعة من قواعد مكتوبة، مش من تعلّم آلي، فأي حد يقدر يقراها:"))
    bullets([t("**Water mark**: each crop needs low, medium or high water. The less water, the higher the mark.",
               "**درجة المياه**: كل محصول احتياجه للمياه قليل أو متوسط أو كبير. كل ما المياه أقل، الدرجة أعلى."),
             t("**Soil mark**: beans and berseem put nitrogen back in the soil, heavy feeders take it out, a change of plant family helps against disease, and land that is covered by a crop for more of the year is better protected.",
               "**درجة التربة**: الفول والبرسيم بيرجّعوا النيتروجين للتربة، والمحاصيل الشرهة بتاخده منها، وتغيير العيلة النباتية بيساعد ضد الأمراض، والأرض اللي عليها زرع أغلب السنة بتتحمي أكتر."),
             t("**Cost-saving mark**: less water and less fertiliser give a higher mark. It is not profit. Prices are shown beside it and are never added to it.",
               "**درجة توفير المصاريف**: مياه أقل وسماد أقل يعني درجة أعلى. دي مش ربح. الأسعار بتظهر جنبها ومبتتضافش عليها."),
             t("**Heat level**: we count the very hot days (35 °C or more) in the two seasons. It is shown but not scored.",
               "**مستوى الحرارة**: بنعدّ أيام الحر الشديد (35 درجة أو أكتر) في الموسمين. بيظهر لكن مش داخل في الدرجات.")])

    st.subheader(t("Where NASA data is used", "بيانات ناسا بتتستخدم فين"))
    bullets([t("**NASA POWER**: daily weather from 1981 to 2025 for one area of about 55 × 60 km around Monufia. We use it for heat, rain and how much water each crop needs.",
               "**ناسا POWER**: طقس يومي من 1981 لـ2025 لمنطقة مساحتها حوالي 55 × 60 كم حوالين المنوفية. بنستخدمه للحرارة والمطر واحتياج كل محصول للمياه."),
             t("**NASA MODIS (MOD13Q1)**: how green the plants are, seen from a satellite, at six points of 250 m.",
               "**ناسا MODIS (MOD13Q1)**: خضرة النبات من القمر الصناعي، عند ست نقط (كل نقطة 250 متر)."),
             t("**NASA SMAP L4 (SPL4SMGP)**: soil moisture at 9 km. Background only: it does not see Nile irrigation, so it never changes a mark.",
               "**ناسا SMAP L4 (SPL4SMGP)**: رطوبة التربة على مسافة 9 كم. معلومة خلفية بس: مبتشوفش ري النيل، فمبتغيّرش أي درجة.")])

    st.subheader(t("What this tool cannot do", "اللي الأداة دي مبتعملوش"))
    bullets(ex.GAPS_GLOBAL_AR if LANG == "ar" else ex.GLOBAL_GAPS)
    st.info(ex.DISCLAIMER[LANG])


# ---------------------------------------------------------------- shell: sidebar, pages, style
# The language switch sits at the top of the page (not in the side menu) so a farmer on a phone sees it at once.
st.radio("Language / اللغة", ["en", "ar"], key="lang", horizontal=True,
         format_func=lambda x: "🇬🇧 English (UK)" if x == "en" else "🇪🇬 عربي مصري")
LANG = st.session_state.lang

with st.sidebar:
    st.markdown("## 🌱 FIELD SHIFT")
    st.caption(t("Monufia, Egypt · research prototype", "المنوفية، مصر · نموذج بحثي"))
    st.caption(t("Developed by team CALIPSO", "اتطوّر بواسطة فريق CALIPSO"))

page = st.navigation([
    st.Page(plans, title=t("Your plans", "خططك"), icon="🌱", default=True, url_path="plan"),
    st.Page(evidence, title=t("NASA evidence", "أدلة ناسا"), icon="🛰️", url_path="evidence"),
    st.Page(about, title=t("How it works", "إزاي بتشتغل"), icon="📖", url_path="about"),
])

background = "data:image/jpeg;base64," + base64.b64encode((ROOT / "assets" / "fields.jpg").read_bytes()).decode()
direction = "rtl" if st.session_state.lang == "ar" else "ltr"
align = "right" if direction == "rtl" else "left"

st.markdown(f'''<style>
[data-testid="stAppViewContainer"] {{background:linear-gradient(120deg,rgba(245,248,240,.96),rgba(245,248,240,.88)),url("{background}") center/cover fixed;color:#173d2a;}}
[data-testid="stSidebar"]{{background:#153e2d;}} [data-testid="stSidebar"] *{{color:#f0f6e8;}}
.block-container{{max-width:1260px;padding-top:2rem;direction:{direction};}} [data-testid="stSidebar"]{{direction:{direction};}}
h1,h2,h3{{letter-spacing:-.02em;color:#173d2a;}}
[data-testid="stHeading"], [data-testid="stCaptionContainer"] {{text-align:{align};}}
.hero{{background:linear-gradient(90deg,rgba(15,49,32,.96),rgba(15,49,32,.3)),url("{background}") center/cover;border-radius:24px;padding:48px 42px;margin-bottom:30px;color:white;min-height:290px;}}
.hero h1{{color:white;font-size:clamp(2rem,4vw,3.5rem);max-width:800px;line-height:1.3;margin:14px 0;}}
.hero p{{max-width:680px;color:#e2eddf;font-size:18px;}}
.eyebrow{{font-size:12px;font-weight:700;}}
.pill{{display:inline-block;padding:8px 12px;border:1px solid #8bad70;border-radius:100px;font-size:11px;margin-top:12px;color:white;}}
.note{{background:#e7efdd;border:1px solid #d4dfc8;border-radius:20px;padding:24px;margin-bottom:16px;color:#173d2a;}}
.note h2{{color:#153e2d;}} .note p{{color:#173d2a;}}
[data-testid="stWidgetLabel"] p, .stSelectbox label, .stRadio label, .stCheckbox label {{color:#173d2a !important; font-weight:600;}}
[data-testid="stMetric"]{{background:#ffffffd9;border-radius:16px;padding:14px 18px;}}
[data-testid="stMetric"] *{{color:#173d2a !important;}}
.stDataFrame th, .stDataFrame td {{color:#173d2a !important;}}
button{{border-radius:10px!important;}}
.st-key-plan_A, .st-key-plan_B, .st-key-plan_C {{background:#ffffffe6;border-radius:20px;padding:6px;}}
.role{{display:inline-block;font-size:12px;font-weight:700;padding:5px 12px;border-radius:100px;margin-bottom:6px;}}
.role-A{{background:#e4e4de;color:#34342d;}} .role-B{{background:#cfe6d3;color:#0f4a2a;}} .role-C{{background:#f1e3b9;color:#5a4300;}}
.ptitle{{font-size:1.25rem;line-height:1.4;margin:4px 0 12px 0;}}
.goalmark{{display:flex;justify-content:space-between;align-items:baseline;background:#e7efdd;border-radius:14px;padding:10px 14px;margin-bottom:12px;color:#153e2d;}}
.goalmark b{{font-size:2rem;}} .goalmark small{{font-size:1rem;font-weight:600;}}
.mark{{margin-bottom:9px;}} .mrow{{display:flex;justify-content:space-between;font-size:14px;color:#173d2a;}}
.track{{background:#e3e9da;height:10px;border-radius:6px;margin-top:4px;}} .fill{{background:#6aa77f;height:10px;border-radius:6px;}} .fill.goal{{background:#1f8a4c;}}
.legend{{display:flex;gap:24px;font-size:13px;margin:6px 0 0 0;color:#173d2a;}}
.legend .sw{{display:inline-block;width:28px;height:0;border-top:3px solid #1f8a4c;vertical-align:middle;margin-inline-end:8px;}}
.legend .sw.dash{{border-top:3px dashed #c2571a;}}
.heat{{font-size:14px;margin:6px 0 12px 0;color:#173d2a;}}
@media(max-width:640px) {{
  .hero {{padding:28px 22px;min-height:240px;}}
  .block-container {{padding:1rem;}}
}}
</style>''', unsafe_allow_html=True)

page.run()
st.divider()
st.caption(t("Developed by team CALIPSO", "اتطوّر بواسطة فريق CALIPSO"))
