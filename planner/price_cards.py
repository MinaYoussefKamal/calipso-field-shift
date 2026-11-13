"""Price facts shown beside each plan (English + Egyptian Arabic).

These are EXTERNAL facts (sourced 13 Nov 2026, see crop_prices_costs_sources.md). They are shown for
information only and are NEVER added to any mark.

Safety net: `check()` makes sure
  1. every number in an English line also appears in that crop's `price_card` text in the crop library
     (so no number was invented while rewriting), and
  2. the Arabic line has exactly the same numbers as the English line (so the translation did not
     change a number).
Run   python3 -I price_cards.py   to check.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

LINES = {
    "wheat": {
        "en": ["Government price for the 2026 harvest: EGP 2,500 per ardeb (150 kg). Announced for 2027: EGP 2,650.",
               "Average yield: 20 ardeb per feddan (Agriculture Minister, Nov 2026).",
               "Cost: about EGP 50,000 per feddan (said by one farmers' union head, so only a rough guide)."],
        "ar": ["سعر الحكومة لحصاد 2026: 2,500 جنيه للأردب (150 كيلو). والمعلن لموسم 2027: 2,650 جنيه.",
               "متوسط المحصول: 20 أردب للفدان (وزير الزراعة، نوفمبر 2026).",
               "التكلفة: حوالي 50,000 جنيه للفدان (كلام رئيس اتحاد مزارعين واحد، فهي تقدير تقريبي بس)."],
    },
    "berseem": {
        "en": ["No market price found. It is mainly fodder for animals.",
               "Area planted: 1.403 million feddan in 2022/23."],
        "ar": ["ملقيناش سعر سوق. هو أساسًا علف للحيوانات.",
               "المساحة المزروعة: 1.403 مليون فدان في موسم 2022/23."],
    },
    "faba_bean": {
        "en": ["No current price or cost in 2026 pounds.",
               "An old study (year not stated) gave a cost of EGP 11,369 and revenue of EGP 14,925 per feddan. "
               "Good for comparing crops only, not as today's prices."],
        "ar": ["ملقيناش سعر أو تكلفة حالية بجنيه 2026.",
               "دراسة قديمة (السنة مش مكتوبة): التكلفة 11,369 جنيه والإيراد 14,925 جنيه للفدان. "
               "تنفع للمقارنة بين المحاصيل بس، مش كأسعار النهارده."],
    },
    "sugar_beet": {
        "en": ["Price: EGP 2,000 per ton (cabinet price for 2025/26, cut by 16%).",
               "Risk: state sugar companies stopped the usual advance contracts with beet farmers for next season, "
               "and some beet farmers are still waiting for payment.",
               "Yield and cost per feddan: not found."],
        "ar": ["السعر: 2,000 جنيه للطن (سعر مجلس الوزراء لموسم 2025/26، بعد خفضه 16%).",
               "خطر: شركات السكر الحكومية وقّفت العقود المقدمة المعتادة مع مزارعي البنجر للموسم الجاي، "
               "وبعض المزارعين لسه مستنيين فلوسهم.",
               "المحصول والتكلفة للفدان: ملقيناهمش."],
    },
    "potato": {
        "en": ["Shop price about EGP 15 per kg (June 2026). It swings a lot.",
               "Farm-gate price, yield and cost: not found."],
        "ar": ["سعر المحل حوالي 15 جنيه للكيلو (يونيو 2026)، وبيتقلب جامد.",
               "سعر باب الغيط والمحصول والتكلفة: ملقيناهمش."],
    },
    "onion": {
        "en": ["Shop price about EGP 14.5 per kg (June 2026).",
               "Wholesale price swung between EGP 6,000 and 15,000 per ton in 2024.",
               "Farm-gate price, yield and cost: not found."],
        "ar": ["سعر المحل حوالي 14.5 جنيه للكيلو (يونيو 2026).",
               "سعر الجملة اتقلب بين 6,000 و15,000 جنيه للطن في 2024.",
               "سعر باب الغيط والمحصول والتكلفة: ملقيناهمش."],
    },
    "maize": {
        "en": ["No farm-gate price found (only import prices).",
               "FAO says maize area was cut in 2025 because of high input costs and low domestic prices."],
        "ar": ["ملقيناش سعر باب الغيط (فيه أسعار استيراد بس).",
               "الفاو بتقول إن مساحة الذرة الشامية قلّت في 2025 بسبب غلا المستلزمات ورخص الأسعار المحلية."],
    },
    "cotton": {
        "en": ["2025/26 sales: about EGP 9,200 to 9,800 per kantar in Lower Egypt (the 2024/25 guaranteed price was EGP 12,000).",
               "Cost: EGP 25,000 to 26,000 per feddan (one farmer, 2024/25).",
               "About 7.7 kantar per feddan (our own sum: 1.5 million kantar on 195,000 feddan)."],
        "ar": ["مبيعات 2025/26: حوالي 9,200 إلى 9,800 جنيه للقنطار في الوجه البحري (السعر المضمون في 2024/25 كان 12,000 جنيه).",
               "التكلفة: من 25,000 إلى 26,000 جنيه للفدان (مزارع واحد، موسم 2024/25).",
               "حوالي 7.7 قنطار للفدان (حسبناها إحنا: 1.5 مليون قنطار على 195,000 فدان)."],
    },
    "soybean": {
        "en": ["No Egyptian farm-gate price found (the 2026 US Department of Agriculture report from Cairo gives none).",
               "Local output is about 85,000 tons, under 2% of demand, so buyers exist; a ministry contract-farming programme is mentioned.",
               "The same report says farmers avoid soybean because of high costs, heat at planting and a preference for other crops."],
        "ar": ["ملقيناش سعر باب الغيط في مصر (تقرير وزارة الزراعة الأمريكية من القاهرة لسنة 2026 مفيهوش سعر).",
               "الإنتاج المحلي حوالي 85,000 طن، أقل من 2% من الطلب، يعني فيه مشترين؛ وفيه برنامج زراعة تعاقدية من الوزارة مذكور.",
               "نفس التقرير بيقول إن المزارعين بيبعدوا عن فول الصويا بسبب التكلفة العالية والحر وقت الزراعة وتفضيلهم محاصيل تانية."],
    },
    "sesame": {
        "en": ["No 2026 farm-gate price found.",
               "Export price, NOT what the farmer gets: natural sesame FOB Cairo EUR 1.44 per kg (25 Sep 2026).",
               "An old study (2000-2018 average, old pounds) gave a cost of 2,629 and revenue of 4,762 per feddan."],
        "ar": ["ملقيناش سعر باب الغيط لسنة 2026.",
               "ده سعر تصدير، مش اللي المزارع بياخده: سمسم طبيعي FOB القاهرة 1.44 يورو للكيلو (25 سبتمبر 2026).",
               "دراسة قديمة (متوسط 2000-2018، بجنيه قديم): التكلفة 2,629 والإيراد 4,762 للفدان."],
    },
}

TITLE = {"en": "Price facts (shown for information, never added to the marks)",
         "ar": "الأسعار (للمعلومة بس، ومبتتضافش على الدرجات)"}
SOURCE_NOTE = {"en": "Searched on 13 Nov 2026 in public news and research pages. Check current prices locally before you decide.",
               "ar": "اتدوّر عليها يوم 13 نوفمبر 2026 في أخبار وأبحاث منشورة. اتأكد من الأسعار الحالية محليًا قبل ما تقرر."}


def lines(crop: str, lang: str) -> list[str]:
    return LINES[crop][lang]


# ------------------------------------------------------------------ safety net
_NUM = re.compile(r"\d[\d,]*\.?\d*")


def _numbers(text: str) -> Counter:
    out = Counter()
    for m in _NUM.findall(text):
        out[m.replace(",", "").rstrip(".")] += 1
    return out


def _source_numbers(card: str) -> set[str]:
    """Numbers in the library's price card; '195k' also counts as 195000."""
    nums = set(_numbers(card))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*k\b", card):
        nums.add(str(int(float(m.group(1)) * 1000)))
    return nums


def check(library_csv: Path | None = None) -> list[str]:
    import pandas as pd
    lib = pd.read_csv(library_csv or HERE / "crop_library_monufia.csv").set_index("crop")
    problems: list[str] = []
    for crop, both in LINES.items():
        if crop not in lib.index:
            problems.append(f"{crop}: not in the crop library")
            continue
        src = _source_numbers(str(lib.loc[crop, "price_card"]))
        en, ar = both["en"], both["ar"]
        if len(en) != len(ar):
            problems.append(f"{crop}: English has {len(en)} lines, Arabic has {len(ar)}")
        for i, (e, a) in enumerate(zip(en, ar), 1):
            ne, na = _numbers(e), _numbers(a)
            if ne != na:
                problems.append(f"{crop} line {i}: numbers differ, EN {dict(ne)} vs AR {dict(na)}")
            extra = [n for n in ne if n not in src]
            if extra:
                problems.append(f"{crop} line {i}: number(s) {extra} not found in the library's price card")
            if re.search(r"[A-Za-z]{2,}", re.sub(r"\bFOB\b", "", a)):
                problems.append(f"{crop} line {i}: Latin letters in the Arabic line")
    return problems


if __name__ == "__main__":
    probs = check()
    if probs:
        print("PROBLEMS:")
        for p in probs:
            print(" -", p)
        sys.exit(1)
    print(f"ALL PRICE CHECKS PASSED ({len(LINES)} crops, English vs Arabic vs library)")
