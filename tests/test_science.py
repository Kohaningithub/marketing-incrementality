"""Small hand-authored fixtures are unit-test inputs only, never portfolio results."""
from pathlib import Path
import ast
import duckdb
import numpy as np
import pandas as pd
import pytest
import sqlglot
from sqlglot import exp
from measurement.criteo_experiment import binary_effect
from measurement.experiment_design import readiness
from measurement.reconciliation import score_health
from measurement.uplift_model import uplift_curve
from measurement.cloud import render

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def raw():
    con=duckdb.connect()
    con.execute('''CREATE TABLE raw_criteo(event_id VARCHAR,uid BIGINT,campaign BIGINT,timestamp BIGINT,
     cat1 BIGINT,click INTEGER,conversion INTEGER,conversion_id BIGINT,conversion_timestamp BIGINT,
     attribution INTEGER,click_pos INTEGER,click_nb INTEGER,cost DOUBLE,cpo DOUBLE)''')
    # Conversion at 200000: first is exactly one day before; outside is 1s too old.
    rows=[('first',1,10,113600,0,1,1,7,200000,1,1,3,1.,0.),
          ('last',1,20,199999,0,1,1,7,200000,1,2,3,1.,0.),
          ('outside',1,30,113599,0,1,1,7,200000,1,0,3,1.,0.),
          ('other-user',2,10,120000,0,1,1,7,200000,0,0,1,1.,0.),
          ('no-conversion',3,10,120001,0,0,0,-1,-1,0,0,0,1.,0.),
          ('future',4,10,200001,0,1,1,8,200000,0,0,1,1.,0.)]
    con.executemany('INSERT INTO raw_criteo VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',rows)
    yield con
    con.close()

def run(con):
    for folder in ['local','analysis']:
        for path in sorted((ROOT/'sql'/folder).glob('*.sql')): con.execute(path.read_text())

def test_window_boundary_first_last_and_linear(raw):
    run(raw)
    key='7:1:200000'
    assert raw.execute('SELECT event_id FROM first_click_attribution WHERE window_days=1 AND conversion_key=?',[key]).fetchone()==('first',)
    assert raw.execute('SELECT event_id FROM last_click_attribution WHERE window_days=1 AND conversion_key=?',[key]).fetchone()==('last',)
    assert raw.execute('SELECT event_id FROM first_click_attribution WHERE window_days=7 AND conversion_key=?',[key]).fetchone()==('outside',)
    assert raw.execute('SELECT event_id FROM impressions WHERE event_id=?',['future']).fetchone() is None
    weights=raw.execute('SELECT attribution_weight FROM linear_attribution WHERE window_days=1 AND conversion_key=?',[key]).fetchall()
    assert weights==[(.5,),(.5,)]
    assert raw.execute('SELECT COUNT(*) FROM (SELECT model,window_days,conversion_key FROM model_credits GROUP BY ALL HAVING ABS(SUM(attribution_weight)-1)>1e-8)').fetchone()[0]==0

def test_identity_dedup_daily_and_reconciliation(raw):
    raw.execute("INSERT INTO raw_criteo SELECT * FROM raw_criteo WHERE event_id='last'")
    run(raw)
    assert raw.execute('SELECT COUNT(*) FROM impressions').fetchone()[0]==5
    assert raw.execute('SELECT COUNT(*) FROM conversions').fetchone()[0]==2
    assert raw.execute('SELECT COUNT(*) FROM conversion_conflicts').fetchone()[0]==1
    assert raw.execute('SELECT SUM(impressions),SUM(clicks) FROM daily_campaign_metrics').fetchone()==(5,4)
    assert raw.execute("SELECT credited_conversions,absolute_difference,percentage_difference FROM window_comparison WHERE model='last_click_proxy' AND window_days=1").fetchone()==(2.,1.,100.)
    assert raw.execute('SELECT COUNT(*) FROM campaign_daily WHERE geo IS NOT NULL OR attributed_roas IS NOT NULL OR incremental_roas IS NOT NULL').fetchone()[0]==0

def test_binary_effect_and_score_interval():
    result=binary_effect(30,1000,10,1000)
    assert result['absolute_lift']==pytest.approx(.02)
    assert result['relative_lift']==pytest.approx(2.)
    assert result['incremental_per_100k']==pytest.approx(2000)
    assert 0<result['ci_low']<.02<result['ci_high']
    assert result['p_value']<.01
    reverse=binary_effect(10,1000,30,1000)
    assert reverse['ci_low']==pytest.approx(-result['ci_high'])
    assert binary_effect(0,1000,0,1000)['p_value']==1
    assert binary_effect(1,1000,0,1000)['relative_lift'] is None
    with pytest.raises(ValueError): binary_effect(1001,1000,1,1000)

def test_prospective_power_and_input_validation():
    a=readiness(.002,100000,.85,relative_lift=.2)
    b=readiness(.002,1000000,.85,absolute_lift=.0004)
    assert b['achieved_power']>a['achieved_power']
    assert b['mde_absolute']<a['mde_absolute']
    assert b['total_required_n']==a['total_required_n']
    assert a['readiness_status']=='underpowered' and b['readiness_status']=='ready'
    balanced=readiness(.002,100000,.5,relative_lift=.2)
    assert balanced['total_required_n']<a['total_required_n']
    for kwargs in [{'baseline_rate':0},{'treatment_fraction':1},{'relative_lift':None},{'relative_lift':1000},{'available_n':1}]:
        opts=dict(baseline_rate=.002,available_n=1000,treatment_fraction=.85,relative_lift=.2);opts.update(kwargs)
        with pytest.raises(ValueError): readiness(**opts)

def test_health_has_no_current_day_leakage_and_handles_boundaries():
    fields=['impressions','clicks','ctr','conversions','attributed_conversions','attribution_rate','unique_users','transformed_cost','malformed_conversion_key_rate','replay_duplicate_rate']
    daily=pd.DataFrame({f:[10.,10.,10.,10.,10.,100.,10.] for f in fields})
    daily['relative_day']=range(7);daily['boundary_day']=[1,0,0,0,0,0,1]
    result=score_health(daily,lookback=3)
    spike=result[(result.metric=='impressions')&(result.relative_day==5)].iloc[0]
    assert spike.baseline==10 and spike.deviation==90 and spike.severity=='zero_variance_review'
    assert (result[result.relative_day.isin([0,6])].severity=='boundary_excluded').all()
    assert (result[result.relative_day==4].severity=='normal').all()
    assert (result[result.relative_day==2].severity=='warmup').all()

def test_uplift_curve_random_ties_and_exact_area():
    y=[1,0,0,1];t=[1,0,1,0]
    _,tied=uplift_curve(y,t,[0,0,0,0],.5)
    assert tied['qini']==0
    curve,perfect=uplift_curve(y,t,[4,3,2,1],.5)
    assert perfect['qini']==pytest.approx(.375)
    assert perfect['treated_all_gain_per_person']==0
    assert curve.target_fraction.iloc[-1]==1
    with pytest.raises(ValueError): uplift_curve(y,t,[np.nan,0,0,0],.5)

def test_all_analytical_bigquery_sql_round_trip_on_fixture(raw):
    other=duckdb.connect()
    frame=raw.execute('SELECT * FROM raw_criteo').fetchdf();other.register('fixture',frame)
    other.execute('CREATE TABLE raw_criteo AS SELECT * FROM fixture')
    run(raw);directory=render(ROOT,'measurement-demo-2026','marketing_measurement')
    for filename in ['01_clean.sql','02_attribution.sql']+[f'analysis_{p.name}' for p in sorted((ROOT/'sql/analysis').glob('*.sql'))]:
        for tree in sqlglot.parse((directory/filename).read_text(),read='bigquery'):
            if isinstance(tree,exp.Create): tree.set('properties',None)
            for tab in tree.find_all(exp.Table): tab.set('catalog',None);tab.set('db',None)
            other.execute(tree.sql(dialect='duckdb'))
    for name in ['first_click_attribution','last_click_attribution','linear_attribution','publisher_attribution','window_comparison','campaign_reconciliation','daily_measurement','conversion_lag_quantiles','attribution_reconciliation']:
        a=raw.execute(f'SELECT * FROM {name} ORDER BY ALL').fetchdf()
        b=other.execute(f'SELECT * FROM {name} ORDER BY ALL').fetchdf()
        pd.testing.assert_frame_equal(a,b,check_dtype=False,atol=1e-8,rtol=1e-8)
    other.close()

def test_dag_includes_new_stages_without_importing_airflow():
    tree=ast.parse((ROOT/'dags/marketing_measurement.py').read_text())
    names={n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
    assert {'validate','attribution_and_daily_metrics','measurement_health','uplift_evaluation'}<=names


def test_ranking_cohort_correlations_and_ties():
    from measurement.ranking import compare_rankings
    rows=[]
    for method,credits in [('publisher',[10,20,30]),('last_click_proxy',[30,20,10])]:
        for cid,credit in enumerate(credits):
            rows.append(dict(campaign_id=cid,model=method,window_days=30,impressions=10000,
                observed_conversions=100,credited_conversions=credit,
                transformed_cost_per_attributed_conversion=100/credit,attributed_conversion_share=credit/100))
        rows.append(dict(campaign_id=99,model=method,window_days=30,impressions=9999,
                observed_conversions=100,credited_conversions=1000,
                transformed_cost_per_attributed_conversion=.1,attributed_conversion_share=1.))
    ranks,pairs=compare_rankings(pd.DataFrame(rows))
    result=pairs.query("metric=='credited_conversions' and method_a=='publisher' and method_b=='last_click_proxy'").iloc[0]
    assert result.cohort_campaigns==3 and result.paired_campaigns==3
    assert result.spearman_rho==pytest.approx(-1)
    assert result.max_absolute_rank_change==2 and result.campaigns_with_rank_change==2
    assert 99 not in ranks.campaign_id.values
    frame=pd.DataFrame(rows);frame.loc[frame.model=='last_click_proxy','attributed_conversion_share']=1.
    _,pairs=compare_rankings(frame)
    assert pairs.query("metric=='attributed_conversion_share' and method_a=='publisher' and method_b=='last_click_proxy'").spearman_rho.isna().all()
