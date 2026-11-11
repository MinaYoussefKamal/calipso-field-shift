"""Transparent family-based screening; not a yield, water or suitability model."""
import json
from pathlib import Path
CROPS = json.loads(Path(__file__).with_name('crops.json').read_text(encoding='utf-8'))
BY_ID={r['id']:r for r in CROPS}
BY_NAME={r['en']:r for r in CROPS}
CORE=['Wheat','Barley','Maize','Rice','Sorghum','Faba bean','Chickpea','Lentil','Cowpea','Common bean','Groundnut','Soyabean','Egyptian clover','Onion','Garlic','Potato','Tomato','Aubergine','Cucumber','Courgette','Cabbage','Cauliflower','Carrot','Sunflower','Sesame','Flax','Sugar beet','Okra','Cotton','Jew\'s mallow']

def assess(current_id, target_id):
    current,target=BY_ID[current_id],BY_ID[target_id]
    if current['cycle']=='perennial' or target['cycle']=='perennial': return 'perennial'
    if current_id==target_id: return 'repeat'
    if current['family']==target['family']: return 'same_family'
    return 'different_family'

def shortlist(current_id, priority):
    current=BY_ID[current_id]
    if current['cycle']=='perennial': return []
    candidates=[BY_NAME[n] for n in CORE if assess(current_id,BY_NAME[n]['id'])=='different_family']
    # A visible exploration preference only. Never a recommendation score.
    if priority=='soil': candidates.sort(key=lambda x:(x['family']!='Fabaceae',x['en']))
    else: candidates.sort(key=lambda x:x['en'])
    return candidates[:6]
