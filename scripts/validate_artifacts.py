"""Validate published aggregate evidence without downloading any source data."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import json
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/'artifacts'
load=lambda n:json.loads((ROOT/f'{n}.json').read_text(encoding='utf-8'))
read=lambda n:pd.read_csv(ROOT/'tables'/f'{n}.csv')
qa=load('qa');model=load('uplift_summary');exp=load('criteo_experiment_summary')
assert read('daily_campaign_metrics').impressions.sum()==qa['clean_impressions']==16468027
assert read('daily_measurement').impressions.sum()==qa['clean_impressions']
assert read('daily_measurement').clicks.sum()==qa['click_indicators']
assert read('criteo_arm_summary').n.sum()==exp['rows']==13979592
itt=read('criteo_itt')
assert ((itt.control_rate>=0)&(itt.treatment_rate<=1)).all()
assert np.allclose(itt.treatment_rate-itt.control_rate,itt.absolute_lift)
assert ((itt.ci_low<itt.absolute_lift)&(itt.ci_high>itt.absolute_lift)).all()
deciles=read('uplift_deciles')
assert deciles.sample_size.sum()==model['test_rows']==559064
assert read('uplift_split_counts').n.sum()==model['model_rows']==2797402
assert (deciles.n_treatment+deciles.n_control==deciles.sample_size).all()
assert np.allclose(deciles.treatment_events/deciles.n_treatment,deciles.treatment_rate)
assert np.allclose(deciles.control_events/deciles.n_control,deciles.control_rate)
windows=read('window_comparison');campaign=read('campaign_reconciliation')
for (m,w),rows in campaign.groupby(['model','window_days']):
    expected=windows[(windows.model==m)&(windows.window_days==w)].credited_conversions.iloc[0]
    assert np.isclose(rows.credited_conversions.sum(),expected,rtol=1e-10)
curve=read('uplift_curve')
assert np.isclose(curve.incremental_per_person.iloc[-1],model['treated_all_gain_per_person'])
assert np.allclose(curve.incremental_per_person-curve.random_per_person,curve.qini_gain_per_person)
assert len(read('measurement_health').query("severity == 'review'"))==5

class Links(HTMLParser):
    def __init__(self): super().__init__();self.links=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.add(attrs['id'])
        for key in ['href','src']:
            if key in attrs:self.links.append(attrs[key])
parser=Links();parser.feed((ROOT/'report.html').read_text(encoding='utf-8'))
for value in parser.links:
    url=urlsplit(value)
    if url.scheme or url.netloc:continue
    if url.path:assert (ROOT/unquote(url.path)).is_file(),value
    elif url.fragment:assert url.fragment in parser.ids,value
print('Aggregate counts, rates, credit totals, split accounting, curve identities and report asset links passed.')
