import json
from pathlib import Path
# Editorial bilingual catalogue. Crop types, not a claim of 250 distinct species.
GROUPS = [
('Poaceae','annual','حبوب','Cereals', '''Wheat|قمح
Durum wheat|قمح صلب
Barley|شعير
Oats|شوفان
Rye|جاودار
Triticale|تريتيكال
Maize|ذرة شامية
Sweetcorn|ذرة سكرية
Rice|أرز
Sorghum|ذرة رفيعة
Pearl millet|دخن لؤلؤي
Finger millet|دخن إصبعي
Foxtail millet|دخن ذيل الثعلب
Proso millet|دخن بروسو
Teff|تيف
Fonio|فونيو
Japanese millet|دخن ياباني
Little millet|دخن صغير
Kodo millet|دخن كودو
Canary seed|فلارس'''),
('Fabaceae','annual','بقوليات','Pulses', '''Faba bean|فول بلدي
Pea|بسلة
Chickpea|حمص
Lentil|عدس
Common bean|فاصوليا
Cowpea|لوبيا
Soyabean|فول صويا
Groundnut|فول سوداني
Mung bean|ماش
Black gram|ماش أسود
Adzuki bean|فاصوليا أزوكي
Bambara groundnut|فول بامبارا
Lima bean|فاصوليا ليما
Runner bean|فاصوليا عداءة
Winged bean|فاصوليا مجنحة
Lablab bean|لوبيا لبلاب
Moth bean|فاصوليا موث
Rice bean|فاصوليا الأرز
Horse gram|كولثي
Grass pea|جلبان
White lupin|ترمس أبيض
Narrow-leaved lupin|ترمس ضيق الأوراق
Yellow lupin|ترمس أصفر
Fenugreek|حلبة
Guar|جوار'''),
('Fabaceae','perennial','بقول وعلف معمر','Perennial legumes', '''Pigeon pea|بازلاء الحمام
Alfalfa|برسيم حجازي
Red clover|برسيم أحمر
White clover|برسيم أبيض
Sainfoin|علف إسبارسيت
Birdsfoot trefoil|لوتس قرني
Leucaena|لوسينا'''),
('Fabaceae','annual','علف','Forage', '''Egyptian clover|برسيم مصري
Crimson clover|برسيم قرمزي
Common vetch|بيقية شائعة
Hairy vetch|بيقية وبرية
Sunn hemp|كروتالاريا
Serradella|سيراديلا'''),
('Solanaceae','annual','خضار','Vegetables', '''Tomato|طماطم
Potato|بطاطس
Aubergine|باذنجان
Sweet pepper|فلفل حلو
Chilli pepper|فلفل حار
Tomatillo|طماطم مكسيكية
Tobacco|تبغ'''),
('Solanaceae','perennial','فاكهة','Fruit', '''Cape gooseberry|حرنكش
Pepino|بيبينو
Tamarillo|طماطم شجرية
Goji berry|توت جوجي'''),
('Cucurbitaceae','annual','قرعيات','Cucurbits', '''Cucumber|خيار
Courgette|كوسة
Pumpkin|قرع عسلي
Butternut squash|قرع جوزي
Watermelon|بطيخ
Melon|شمام
Bottle gourd|قرع زجاجي
Bitter gourd|قرع مر
Sponge gourd|لوف
Ridge gourd|لوف مضلع
Snake gourd|قرع ثعباني
Wax gourd|قرع شمعي
Cucamelon|خيار مكسيكي صغير
Kiwano|خيار إفريقي مقرن'''),
('Cucurbitaceae','perennial','قرعيات معمرة','Perennial cucurbits', '''Chayote|شايوت
Ivy gourd|قرع لبلابي
Pointed gourd|قرع مدبب'''),
('Brassicaceae','annual','خضار ورقية وجذرية','Brassicas', '''Cabbage|كرنب
Red cabbage|كرنب أحمر
Cauliflower|قرنبيط
Broccoli|بروكلي
Brussels sprouts|كرنب بروكسل
Kale|كرنب أجعد
Kohlrabi|كرنب أبو ركبة
Pak choi|باك تشوي
Chinese cabbage|كرنب صيني
Turnip|لفت
Swede|لفت سويدي
Radish|فجل
Daikon|فجل أبيض طويل
Rocket|جرجير
Garden cress|حب الرشاد
Mustard greens|خردل ورقي
Brown mustard|خردل بني
White mustard|خردل أبيض
Black mustard|خردل أسود
Rapeseed|لفت زيتي
Mizuna|ميزونا
Tatsoi|تاتسوي'''),
('Brassicaceae','perennial','أعشاب وخضار معمرة','Perennial greens', '''Watercress|جرجير مائي
Horseradish|فجل حار
Wasabi|واسابي'''),
('Amaryllidaceae','annual','بصليات','Alliums', '''Onion|بصل
Garlic|ثوم
Leek|كرات
Shallot|بصل شالوت
Spring onion|بصل أخضر'''),
('Amaryllidaceae','perennial','بصليات معمرة','Perennial alliums', '''Chives|ثوم معمر
Garlic chives|ثوم معمر صيني
Welsh onion|بصل ويلزي'''),
('Apiaceae','annual','خضار وأعشاب','Vegetables and herbs', '''Carrot|جزر
Parsnip|جزر أبيض
Celery|كرفس
Celeriac|كرفس جذري
Parsley|بقدونس
Coriander|كزبرة
Dill|شبت
Cumin|كمون
Anise|يانسون
Caraway|كراوية
Chervil|بقدونس إفرنجي
Florence fennel|شمر بصلي'''),
('Apiaceae','perennial','أعشاب معمرة','Perennial herbs', '''Fennel|شمر
Lovage|كاشم
Angelica|حشيشة الملاك
Asafoetida|حلتيت'''),
('Amaranthaceae','annual','ورقيات وجذور','Leaf and root crops', '''Spinach|سبانخ
Swiss chard|سلق
Beetroot|بنجر مائدة
Sugar beet|بنجر سكر
Quinoa|كينوا
Grain amaranth|قطيفة للحبوب
Leaf amaranth|قطيفة ورقية
Orach|قطف بستاني
Good King Henry|سبانخ برية معمرة'''),
('Asteraceae','annual','خضار وزيوت وأعشاب','Salads, oils and herbs', '''Lettuce|خس
Endive|هندباء إنديف
Chicory|شيكوريا
Radicchio|راديكيو
Sunflower|عباد الشمس
Safflower|قرطم
Niger seed|نوج
German chamomile|بابونج ألماني
Calendula|أقحوان طبي
Stevia|ستيفيا'''),
('Asteraceae','perennial','خضار وأعشاب معمرة','Perennial crops', '''Globe artichoke|خرشوف
Jerusalem artichoke|طرطوفة
Cardoon|خرشوف بري
Tarragon|طرخون
Roman chamomile|بابونج روماني
Yacon|ياكون
Salsify|سالسيفاي
Scorzonera|سكورزونيرا'''),
('Lamiaceae','perennial','أعشاب عطرية','Aromatic herbs', '''Mint|نعناع
Peppermint|نعناع فلفلي
Spearmint|نعناع بلدي
Rosemary|روزماري
Thyme|زعتر
Sage|مريمية
Oregano|أوريجانو
Marjoram|بردقوش
Lavender|لافندر
Lemon balm|مليسة
Hyssop|زوفا
Winter savory|ندغ شتوي
Holy basil|ريحان مقدس'''),
('Lamiaceae','annual','أعشاب وبذور','Herbs and seeds', '''Basil|ريحان
Chia|شيا
Perilla|بريلا
Summer savory|ندغ صيفي'''),
('Malvaceae','annual','ألياف وخضار','Fibre and vegetables', '''Okra|بامية
Cotton|قطن
Roselle|كركديه
Kenaf|تيل
Jute|جوت
Jew's mallow|ملوخية'''),
('Malvaceae','perennial','أشجار','Trees', '''Cocoa|كاكاو
Kola nut|جوز الكولا'''),
('Rosaceae','perennial','فاكهة','Fruit', '''Apple|تفاح
Pear|كمثرى
Quince|سفرجل
Peach|خوخ
Nectarine|نكتارين
Apricot|مشمش
Plum|برقوق
Sweet cherry|كرز حلو
Sour cherry|كرز حامض
Almond|لوز
Strawberry|فراولة
Raspberry|توت العليق
Blackberry|عليق أسود
Loquat|بشملة
Medlar|زعرور ألماني
Rose hip|ثمار الورد
Aronia|أرونيا'''),
('Rutaceae','perennial','موالح','Citrus', '''Orange|برتقال
Mandarin|يوسفي
Clementine|كلمنتينا
Lemon|ليمون أصفر
Lime|ليمون أخضر
Grapefruit|جريب فروت
Pomelo|بوميلو
Kumquat|برتقال ذهبي
Citron|أترج
Bergamot|برغموت
Yuzu|يوزو'''),
('Zingiberaceae','perennial','توابل','Spices', '''Ginger|زنجبيل
Turmeric|كركم
Cardamom|حبهان
Galangal|خولنجان'''),
('Arecaceae','perennial','نخيل','Palms', '''Date palm|نخيل بلح
Coconut|جوز هند
Oil palm|نخيل زيت
Areca nut|فوفل
Sago palm|نخيل ساجو'''),
('Myrtaceae','perennial','فاكهة وتوابل','Fruit and spices', '''Guava|جوافة
Feijoa|فيجوا
Clove|قرنفل
Allspice|بهار حلو
Java plum|جامون
Rose apple|تفاح وردي'''),
('Moraceae','perennial','فاكهة','Fruit', '''Fig|تين
Mulberry|توت
Jackfruit|جاك فروت
Breadfruit|فاكهة الخبز'''),
('Anacardiaceae','perennial','فاكهة ومكسرات','Fruit and nuts', '''Mango|مانجو
Cashew|كاجو
Pistachio|فستق'''),
('Ericaceae','perennial','توتيات','Berries', '''Blueberry|توت أزرق
Cranberry|توت بري أحمر
Lingonberry|لينجونبيري'''),
('Sapindaceae','perennial','فاكهة','Fruit', '''Lychee|ليتشي
Longan|لونجان
Rambutan|رامبوتان'''),
]
# Remaining distinct crop entries with their own families.
EXTRA = '''Banana|موز|Musaceae|perennial
Pineapple|أناناس|Bromeliaceae|perennial
Papaya|بابايا|Caricaceae|perennial
Avocado|أفوكادو|Lauraceae|perennial
Olive|زيتون|Oleaceae|perennial
Grape|عنب|Vitaceae|perennial
Pomegranate|رمان|Lythraceae|perennial
Passion fruit|باشن فروت|Passifloraceae|perennial
Kiwifruit|كيوي|Actinidiaceae|perennial
Persimmon|كاكا|Ebenaceae|perennial
Walnut|عين جمل|Juglandaceae|perennial
Hazelnut|بندق|Betulaceae|perennial
Sweet potato|بطاطا|Convolvulaceae|annual
Cassava|كسافا|Euphorbiaceae|perennial
Taro|قلقاس|Araceae|perennial
Yam|يام|Dioscoreaceae|perennial
Sesame|سمسم|Pedaliaceae|annual
Flax|كتان|Linaceae|annual
Buckwheat|حنطة سوداء|Polygonaceae|annual
Sugar cane|قصب سكر|Poaceae|perennial
Coffee|قهوة|Rubiaceae|perennial
Tea|شاي|Theaceae|perennial
Black pepper|فلفل أسود|Piperaceae|perennial
Vanilla|فانيليا|Orchidaceae|perennial
Saffron|زعفران|Iridaceae|perennial'''
rows=[]
for family,cycle,ar_group,en_group,lines in GROUPS:
    for line in lines.splitlines():
        en,ar=line.split('|'); rows.append(dict(en=en,ar=ar,family=family,cycle=cycle,group_en=en_group,group_ar=ar_group))
for line in EXTRA.splitlines():
    en,ar,family,cycle=line.split('|'); rows.append(dict(en=en,ar=ar,family=family,cycle=cycle,group_en='Other crops',group_ar='محاصيل متنوعة'))
# Correct perennials sometimes grown as annual crops.
for r in rows:
    if r['en'] in ['Good King Henry','Stevia']: r['cycle']='perennial'
omit = {'Canary seed','Little millet','Kodo millet','Rice bean','Moth bean','Horse gram','Serradella','Birdsfoot trefoil','Pointed gourd','Kiwano','Good King Henry','Angelica','Asafoetida','Kola nut','Medlar','Rose hip','Aronia','Areca nut'}
rows = [r for r in rows if r['en'] not in omit]
assert len(rows) == 250
print('Catalogue entries:',len(rows))
assert len({r['en'] for r in rows})==len(rows)
for i,r in enumerate(rows): r['id']=f'crop_{i+1:03d}'; r['local_suitability']='not_validated'
Path(__file__).with_name('crops.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
