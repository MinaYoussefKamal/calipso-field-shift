from pathlib import Path
from datetime import date
import base64,calendar,json,html
import pandas as pd
import requests
import streamlit as st
from rotation import CROPS,BY_ID,BY_NAME,assess,shortlist

ROOT=Path(__file__).parent
st.set_page_config(page_title='Field Shift · CALIPSO',page_icon='🌱',layout='wide')
if 'lang' not in st.session_state: st.session_state.lang='en'
LANG=st.session_state.lang
def t(en,ar): return ar if LANG=='ar' else en
def crop_name(cid): return BY_ID[cid][LANG]
REGIONS={'tanta':('Tanta, Gharbia','طنطا، الغربية',30.7865,31.0004),'mansoura':('Mansoura, Dakahlia','المنصورة، الدقهلية',31.0409,31.3785),'damanhur':('Damanhur, Beheira','دمنهور، البحيرة',31.0364,30.4691)}
SOILS={'clay':('Clay','طينية'),'loam':('Loam','طميية'),'sand':('Sandy','رملية'),'unknown':('Unknown','مش معروف')}
PRIORITIES={'water':('Saving water','توفير الميّه'),'soil':('Soil health','صحة التربة'),'balanced':('Balanced planning','تخطيط متوازن')}
MONTHS=['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
def month_name(m): return t(calendar.month_name[m],MONTHS[m-1])
DEFAULT=dict(region='tanta',soil='clay',current=BY_NAME['Wheat']['id'],desired=BY_NAME['Faba bean']['id'],priority='water',month=11)
if 'profile' not in st.session_state:st.session_state.profile=DEFAULT.copy()

def hero(label,title,body):
    st.markdown(f'<div class="hero"><div class="eyebrow">{html.escape(label)}</div><h1>{html.escape(title)}</h1><p>{html.escape(body)}</p><span class="pill">{t("RESEARCH PROTOTYPE","نموذج تجريبي")} · CALIPSO</span></div>',unsafe_allow_html=True)

def field_select(label,options,value,fmt=lambda x:x):
    return st.selectbox(label,options,index=options.index(value),format_func=fmt)

def status_text(status):
    return {'perennial':t('Separate perennial-crop assessment needed','محتاج تقييم خاص بالمحاصيل المعمرة'),'repeat':t('Same crop again — rotation break absent','نفس المحصول تاني — مفيش تغيير في الدورة'),'same_family':t('Same plant family — review shared pest risks','نفس العيلة النباتية — راجع مخاطر الآفات المشتركة'),'different_family':t('Different plant family — candidate for review','عيلة نباتية مختلفة — بديل يستحق المراجعة')}[status]

def advice(status):
    return {'perennial':t('Trees and perennial crops need a separate establishment or replanting plan. This seasonal screening cannot decide whether to remove or replace them. Review root residues, replant diseases, land preparation and the establishment period with an agronomist.','الأشجار والمحاصيل المعمرة محتاجة خطة تأسيس أو إعادة زراعة خاصة. الفحص الموسمي ده ما يقدرش يقرر إزالتها أو استبدالها. راجع بقايا الجذور وأمراض إعادة الزراعة وتجهيز الأرض وفترة التأسيس مع مهندس زراعي.'),'repeat':t('Do not treat repeating the crop as a rotation break. Discuss a different-family break crop, review the field disease history, and verify local planting dates before sowing the preferred crop. No safe waiting period can be set from the crop name alone.','تكرار نفس المحصول مش فاصل في الدورة. ناقش محصول فاصل من عيلة مختلفة، وراجع تاريخ أمراض الأرض ومواعيد الزراعة المحلية قبل زراعة المحصول اللي عايزه. اسم المحصول لوحده مش كفاية لتحديد فترة انتظار آمنة.'),'same_family':t('Changing the crop name does not necessarily break a shared pest or disease cycle. Discuss an appropriate different-family break and the disease-specific interval with an agronomist. A generic one-season gap is not a guarantee.','تغيير اسم المحصول مش بالضرورة بيكسر دورة الآفات أو الأمراض المشتركة. ناقش محصول فاصل مناسب من عيلة مختلفة والفاصل الزمني المطلوب حسب المرض مع مهندس زراعي. موسم واحد مش ضمان.'),'different_family':t('This passes the family-diversity screen only. Before planting, confirm the local sowing window, soil test and drainage, irrigation supply, crop duration, and pest history. Different families can still share pests.','ده اجتاز فحص تنويع العيلة النباتية بس. قبل الزراعة، اتأكد من ميعاد الزراعة المحلي وتحليل التربة والصرف وتوفر الري ومدة المحصول وتاريخ الآفات. عيلتين مختلفتين ممكن برضه يشتركوا في آفات.')}[status]

def priority_note(p):
    return {'water':t('Water-saving options cannot be ranked yet: irrigation demand has not been calculated. The list is alphabetical, not a water-use ranking.','لسه ما ينفعش نرتب البدائل حسب توفير الميّه: احتياجات الري مش محسوبة. ترتيب القايمة أبجدي بالاسم الإنجليزي، مش ترتيب استهلاك ميّه.'),'soil':t('Legumes appear first as a soil-health exploration preference, then alphabetical order. This does not establish a nitrogen benefit, disease safety or the best crop.','البقوليات بتظهر الأول كاختيار للاستكشاف المرتبط بصحة التربة، وبعدها ترتيب أبجدي بالاسم الإنجليزي. ده مش إثبات لتحسين النيتروجين أو الأمان من الأمراض أو إن ده أفضل محصول.'),'balanced':t('Different-family candidates are shown alphabetically. No combined suitability score or best crop is claimed.','البدائل من عيلة مختلفة ظاهرة بترتيب أبجدي بالاسم الإنجليزي. مفيش درجة ملاءمة شاملة أو ادعاء إن محصول هو الأفضل.')}[p]

def farm():
    hero(t('YOUR FARM','أرضك'),t('Every field has a next chapter.','كل أرض ليها زرعة جاية.'),t('Your current crop. Your next choice. A clearer view of what needs checking.','محصولك الحالي، واختيارك الجاي، وصورة أوضح للحاجات اللي محتاجة تتراجع.'))
    left,right=st.columns([1.65,1],gap='large')
    with left:
        st.subheader(t('Tell us about your field','عرّفنا بأرضك'))
        f=st.session_state.profile
        with st.form('profile_form'):
            region=field_select(t('Location','المكان'),list(REGIONS),f['region'],lambda x:t(*REGIONS[x][:2]))
            soil=field_select(t('Soil type','نوع التربة'),list(SOILS),f['soil'],lambda x:t(*SOILS[x]))
            current=field_select(t('Current / most recent crop','المحصول الموجود / آخر محصول'),list(BY_ID),f['current'],crop_name)
            desired=field_select(t('Crop you would like to grow','المحصول اللي نفسك تزرعه'),list(BY_ID),f['desired'],crop_name)
            priority=field_select(t('Your priority','إيه أولويتك؟'),list(PRIORITIES),f['priority'],lambda x:t(*PRIORITIES[x]))
            month=field_select(t('Proposed planting month','شهر الزراعة المقترح'),list(range(1,13)),f['month'],month_name)
            if st.form_submit_button(t('Save my field','احفظ بيانات أرضي'),type='primary',width='stretch'):
                st.session_state.profile=dict(region=region,soil=soil,current=current,desired=desired,priority=priority,month=month)
                st.success(t('Saved. Your crop comparison now uses this profile.','اتحفظت. مقارنة المحاصيل دلوقتي بتستخدم البيانات دي.'))
    with right:
        st.markdown(f'<div class="note"><div class="eyebrow">CALIPSO · FIELD SHIFT</div><h2>{t("Better questions. Clearer choices.","أسئلة أوضح، واختيارات مدروسة.")}</h2><p>{t("Explore what could follow your current crop, or check a crop you already have in mind.","شوف إيه ممكن ييجي بعد محصولك الحالي، أو افحص محصول إنت محدده من الأول.")}</p></div>',unsafe_allow_html=True)
        st.metric(t('Crop entries in the catalogue','محصول ونوع زراعي في الدليل'),len(CROPS))
        st.caption(t('A worldwide catalogue including crop types and perennials; not 250 validated choices for Egypt. Local suitability is not established.','دليل عالمي فيه أنواع زراعية ومحاصيل معمرة؛ مش 250 اختيار معتمد للزراعة في مصر. الملاءمة المحلية لسه مش مثبتة.'))
    with st.expander(t('Browse the crop catalogue','تصفّح دليل المحاصيل')):
        search=st.text_input(t('Search in English or Arabic','دوّر بالإنجليزي أو بالعربي'))
        filtered=[c for c in CROPS if search.casefold() in (c['en']+' '+c['ar']).casefold()]
        st.caption(t(f'{len(filtered)} matching entries',f'{len(filtered)} نتيجة'))
        st.dataframe(pd.DataFrame([{t('Crop','المحصول'):c[st.session_state.lang],t('English name','الاسم الإنجليزي'):c['en'],t('Group','المجموعة'):c['group_'+st.session_state.lang],t('Plant family','العيلة النباتية'):c['family']} for c in filtered]),hide_index=True,width='stretch')

@st.cache_data(ttl=86400,show_spinner=False)
def climate(lat,lon,year):
    r=requests.get('https://power.larc.nasa.gov/api/temporal/daily/point',params=dict(parameters='T2M,PRECTOTCORR',community='AG',latitude=lat,longitude=lon,start=f'{year}0101',end=f'{year}1231',format='JSON'),timeout=45)
    r.raise_for_status(); raw=r.json()['properties']['parameter']
    df=pd.DataFrame(raw).apply(pd.to_numeric,errors='coerce').replace(-999,float('nan'))
    df.index=pd.to_datetime(df.index,format='%Y%m%d')
    df=df.reindex(pd.date_range(f'{year}-01-01',f'{year}-12-31'))
    if not {'T2M','PRECTOTCORR'}.issubset(df.columns) or df.dropna(how='all').empty: raise ValueError('No data')
    return df,r.url

def weather():
    hero(t('CLIMATE CONTEXT','المناخ'),t('A clearer picture of the season.','صورة أوضح عن الموسم.'),t('Historical NASA POWER records, with their limitations in view.','بيانات NASA POWER التاريخية، مع توضيح حدود استخدامها.'))
    f=st.session_state.profile; region=REGIONS[f['region']]
    st.caption(t(*region[:2])+t(' · Regional reference point, not field measurements',' · نقطة مرجعية للمنطقة، مش قياس مباشر لأرضك'))
    year=st.selectbox(t('Historical year','السنة'),list(range(date.today().year-1,2014,-1)))
    if st.button(t('Load NASA data','حمّل بيانات ناسا'),type='primary'):
        try:
            with st.spinner(t('Loading climate records…','بنحمّل بيانات المناخ…')): df,url=climate(region[2],region[3],year)
            st.session_state.weather=(df,url,f['region'],year)
        except (requests.RequestException,ValueError,KeyError):
            st.error(t('Data could not be loaded. Please try again. No substitute values have been generated.','البيانات ما اتحمّلتش. جرّب تاني. مفيش أرقام بديلة اتولدت.'))
    data=st.session_state.get('weather')
    if data and data[2:]==(f['region'],year):
        df,url,_,_=data
        a,b=st.columns(2)
        a.metric(t('Temperature coverage','اكتمال بيانات الحرارة'),f'{df.T2M.notna().mean():.0%}')
        b.metric(t('Precipitation coverage','اكتمال بيانات المطر'),f'{df.PRECTOTCORR.notna().mean():.0%}')
        means=df.T2M.resample('MS').mean()
        rain=df.PRECTOTCORR.resample('MS').apply(lambda s:s.sum() if s.notna().all() else float('nan'))
        a,b=st.columns(2)
        with a:
            st.subheader(t('Mean temperature · °C','متوسط الحرارة · °م'));st.line_chart(means.rename(t('Temperature','الحرارة')),color='#23734d')
        with b:
            st.subheader(t('Monthly precipitation · mm','المطر الشهري · مم'));st.bar_chart(rain.rename(t('Precipitation','المطر')),color='#77a862')
        st.caption(t('Incomplete monthly rainfall totals are omitted; temperature means use available days. These are historical records, not a forecast.','إجمالي المطر للشهور الناقصة مش بيتعرض؛ متوسط الحرارة بيستخدم الأيام المتاحة. دي بيانات تاريخية، مش توقعات.'))
        st.link_button(t('Original NASA response','البيانات الأصلية من ناسا'),url)
        st.download_button(t('Download daily CSV','نزّل البيانات اليومية CSV'),df.to_csv(),'field-shift-climate.csv','text/csv')
    else:st.info(t('Choose a year and load the data to display real charts.','اختار سنة وحمّل البيانات علشان الرسوم الحقيقية تظهر.'))
    st.caption(t('Climate records provide context only. They do not currently determine crop suitability or irrigation demand.','بيانات المناخ هنا للسياق بس. حاليًا مش بتحدد ملاءمة المحصول أو احتياجات الري.'))

def compare():
    hero(t('YOUR NEXT CROP','محصولك الجاي'),t('What comes after your current crop?','تزرع إيه بعد محصولك الحالي؟'),t('Explore a shortlist or check your preferred crop against a transparent family-based screen.','استكشف بدائل، أو افحص المحصول اللي عايزه حسب قاعدة واضحة لتغيير العيلة النباتية.'))
    f=st.session_state.profile
    c1,c2=st.columns(2)
    with c1:current=field_select(t('Current crop','المحصول الحالي'),list(BY_ID),f['current'],crop_name)
    with c2:desired=field_select(t('Preferred next crop','المحصول المطلوب بعده'),list(BY_ID),f['desired'],crop_name)
    f['current']=current;f['desired']=desired
    priority=field_select(t('Comparison priority','أولوية المقارنة'),list(PRIORITIES),f['priority'],lambda x:t(*PRIORITIES[x]));f['priority']=priority
    tab1,tab2=st.tabs([t('Explore alternatives','شوف البدائل'),t('I want this crop','أنا عايز المحصول ده')])
    with tab1:
        st.subheader(t('A starting shortlist, not a confirmed best crop','بدائل كبداية، مش حكم نهائي بأفضل محصول'))
        options=shortlist(current,priority)
        st.info(priority_note(priority))
        if not options:st.warning(advice('perennial'))
        for start in range(0,len(options),3):
            for col,c in zip(st.columns(3),options[start:start+3]):
                with col:
                    st.markdown(f'<div class="rotation"><div class="eyebrow">{t("CANDIDATE TO REVIEW","بديل للمراجعة")}</div><h3>{html.escape(c[st.session_state.lang])}</h3><p>{html.escape(c["family"])}</p><p>{t("Different family from your current crop.","عيلة مختلفة عن محصولك الحالي.")}</p></div>',unsafe_allow_html=True)
                    if st.button(t('Check this crop','افحص المحصول ده'),key='pick_'+c['id']):
                        f['desired']=c['id'];st.rerun()
        st.caption(t('Shortlist: screened from a 30-crop working set. The full 250-entry catalogue is searchable and available for preferred-crop checks. Region, soil, planting month, climate and water supply are not yet suitability filters.','البدائل متفلترة من مجموعة عمل فيها 30 محصول. الدليل الكامل فيه 250 مدخل للبحث وفحص المحصول المطلوب. المنطقة والتربة وشهر الزراعة والمناخ وتوفر الميّه لسه مش فلاتر للملاءمة.'))
    with tab2:
        result=assess(current,desired)
        st.subheader(crop_name(current)+' → '+crop_name(desired))
        st.warning(status_text(result))
        st.write(advice(result))
        st.write(t('**Plant families:** ','**العائلات النباتية:** ')+BY_ID[current]['family']+' → '+BY_ID[desired]['family'])
        if result in ['same_family','repeat']:
            alternatives=shortlist(current,priority)[:3]
            st.write(t('**Different-family crops to discuss:** ','**بدائل من عيلة مختلفة تناقشها:** ')+ '، '.join(c[st.session_state.lang] for c in alternatives))
        st.caption(t('No crop-specific fertiliser dose, pesticide treatment, irrigation amount or waiting period is prescribed by this screen.','الفحص ده ما بيحددش جرعات سماد أو مبيدات أو كمية ري أو فترة انتظار خاصة بالمحصول.'))

def report():
    hero(t('YOUR REPORT','تقريرك'),t('Keep the evidence with the decision.','خلّي الدليل جنب القرار.'),t('Your saved field profile, crop screen and source references.','بيانات أرضك، وفحص المحاصيل، والمصادر المستخدمة.'))
    f=st.session_state.profile; result=assess(f['current'],f['desired'])
    a,b=st.columns([1.3,1])
    with a:
        st.subheader(t('Field summary','ملخص الأرض'))
        rows=[(t('Location','المكان'),t(*REGIONS[f['region']][:2])),(t('Soil','التربة'),t(*SOILS[f['soil']])),(t('Current crop','المحصول الحالي'),crop_name(f['current'])),(t('Preferred crop','المحصول المطلوب'),crop_name(f['desired'])),(t('Priority','الأولوية'),t(*PRIORITIES[f['priority']])),(t('Proposed month','الشهر المقترح'),month_name(f['month']))]
        st.table(pd.DataFrame(rows,columns=[t('Field','البند'),t('Value','القيمة')]))
        st.write(status_text(result))
        brief={'developed_by':'CALIPSO','language':st.session_state.lang,'profile':dict(rows),'screen':status_text(result),'explanation':advice(result),'candidates':[c[st.session_state.lang] for c in shortlist(f['current'],f['priority'])],'limitations':t('Family-based screening only; local season, soil, water and climate suitability not validated.','فحص حسب العيلة النباتية بس؛ ملاءمة الموسم والتربة والميّه والمناخ محليًا مش مثبتة.')}
        st.download_button(t('Download my report · JSON','نزّل تقريري · JSON'),json.dumps(brief,ensure_ascii=False,indent=2),'field-shift-report.json','application/json',type='primary')
    with b:
        st.subheader(t('Sources & limitations','المصادر وحدود النتائج'))
        st.markdown(f'- [NASA POWER — {t("daily climate records","بيانات المناخ اليومية")}](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)\n- [FAO — {t("crop diversification","تنويع المحاصيل")}](https://www.fao.org/conservation-agriculture/in-practice/species-diversification/en/)\n- [FAO — {t("vegetable rotation principles","مبادئ تدوير محاصيل الخضار")}](https://www.fao.org/4/y5031e/y5031e0b.htm)')
        st.caption(t('The catalogue is an editorial list of crop names and types, not a downloaded FAO dataset. Sources support general principles, not each local crop pairing.','الدليل قايمة تحريرية لأسماء وأنواع المحاصيل، مش قاعدة بيانات منزّلة من الفاو. المصادر بتدعم المبادئ العامة، مش كل تتابع محاصيل محلي.'))
        st.caption(t('No measured water saving, yield forecast or NASA endorsement is claimed.','مفيش ادعاء بتوفير ميّه مقاس أو توقع إنتاجية أو اعتماد من ناسا.'))

with st.sidebar:
    st.markdown('## 🌱 FIELD SHIFT')
    st.radio('Language / اللغة',['en','ar'],key='lang',format_func=lambda x:'🇬🇧 English (UK)' if x=='en' else '🇪🇬 عربي مصري')
    LANG=st.session_state.lang
    st.caption(t('Developed by team CALIPSO','اتطوّر بواسطة فريق CALIPSO'))
page=st.navigation([st.Page(farm,title=t('Your farm','أرضك'),icon='🌱',default=True,url_path='farm'),st.Page(weather,title=t('Climate context','المناخ'),icon='☀️',url_path='climate'),st.Page(compare,title=t('Next crop','المحصول الجاي'),icon='🌾',url_path='crops'),st.Page(report,title=t('My report','تقريري'),icon='📋',url_path='report')])
background='data:image/jpeg;base64,'+base64.b64encode((ROOT/'assets'/'fields.jpg').read_bytes()).decode()
direction='rtl' if st.session_state.lang=='ar' else 'ltr'
st.markdown('''<style>
[data-testid="stAppViewContainer"] {background:linear-gradient(120deg,rgba(245,248,240,.96),rgba(245,248,240,.88)),url("'''+background+'''") center/cover fixed;color:#173d2a;}
[data-testid="stSidebar"]{background:#153e2d;} [data-testid="stSidebar"] *{color:#f0f6e8;}
.block-container{max-width:1260px;padding-top:2rem;direction:'''+direction+''';} [data-testid="stSidebar"]{direction:'''+direction+''';}
h1,h2,h3{letter-spacing:-.02em;color:#173d2a;}
.hero{background:linear-gradient(90deg,rgba(15,49,32,.96),rgba(15,49,32,.3)),url("'''+background+'''") center/cover;border-radius:24px;padding:48px 42px;margin-bottom:30px;color:white;min-height:290px;}
.hero h1{color:white;font-size:clamp(2rem,4vw,3.5rem);max-width:800px;line-height:1.3;margin:14px 0;}
.hero p{max-width:680px;color:#e2eddf;font-size:18px;}
.eyebrow{font-size:12px;font-weight:700;}
.pill{display:inline-block;padding:8px 12px;border:1px solid #8bad70;border-radius:100px;font-size:11px;margin-top:12px;color:white;}
.note,.rotation{background:#e7efdd;border:1px solid #d4dfc8;border-radius:20px;padding:24px;margin-bottom:16px;color:#173d2a;}
.rotation{min-height:205px;}
.note h2,.rotation h3{color:#153e2d;}
.note p,.rotation p{color:#173d2a;}
/* Added rules to target form labels and widget text cleanly */
[data-testid="stForm"]{background:#ffffffd9;border-radius:20px;padding:24px;color:#173d2a;}
[data-testid="stForm"] label, [data-testid="stWidgetLabel"] p, .stSelectbox label {color: #173d2a !important; font-weight: 600;}
button{border-radius:10px!important;}
@media(max-width:640px){.hero{padding:28px 22px;min-height:240px;}.block-container{padding:1rem;}}
</style>''',unsafe_allow_html=True)
page.run()
st.divider()
st.caption(t('Developed by team CALIPSO','اتطوّر بواسطة فريق CALIPSO'))
