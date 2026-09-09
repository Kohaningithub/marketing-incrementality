"""Intent-to-treat analysis of all 64,000 observed Hillstrom customers."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import brentq
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.power import NormalIndPower

CONTROL = 'No E-Mail'
TREATMENTS = ['Mens E-Mail', 'Womens E-Mail']
GROUPS = ['geo_class', 'newbie', 'channel', 'history_segment', 'mens', 'womens']

def clean_hillstrom(root):
    root = Path(root)
    df = pd.read_csv(root / 'data/raw/hillstrom.csv')
    expected = {'recency','history_segment','history','mens','womens','zip_code','newbie','channel','segment','visit','conversion','spend'}
    if set(df.columns) != expected or len(df) != 64000 or df.isna().any().any():
        raise ValueError('Hillstrom schema, completeness, or row-count validation failed')
    if not set(df.segment) == {CONTROL, *TREATMENTS}:
        raise ValueError('Unexpected experiment arms')
    for col in ['mens','womens','newbie','visit','conversion']:
        if not df[col].isin([0,1]).all(): raise ValueError(f'Invalid binary value: {col}')
    if (df.spend < 0).any() or not np.isfinite(df[['history','spend']]).all().all():
        raise ValueError('Invalid monetary value')
    if not ((df.spend > 0).astype(int) == df.conversion).all() or (df.conversion > df.visit).any():
        raise ValueError('Outcome reconciliation failed')
    # No original customer ID exists. Row IDs prevent replay duplication only.
    df.insert(0, 'participant_id', ['hillstrom:' + str(i) for i in range(len(df))])
    df['geo_class'] = df.zip_code.replace({'Surburban': 'Suburban'})
    if not df.geo_class.isin(['Urban','Suburban','Rural']).all(): raise ValueError('Invalid geo class')
    df = df.rename(columns={'segment':'arm', 'spend':'revenue'})
    out = root / 'data/processed'
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / 'experiment_participants.parquet', index=False)
    return df

def effect(t, c, binary=False):
    t, c = np.asarray(t, dtype=float), np.asarray(c, dtype=float)
    nt, nc = len(t), len(c)
    if min(nt, nc) < 2: raise ValueError('Need at least two observations per arm')
    mt, mc = t.mean(), c.mean()
    diff = mt - mc
    vt, vc = t.var(ddof=1)/nt, c.var(ddof=1)/nc
    se = np.sqrt(vt+vc)
    if binary:
        lo, hi = confint_proportions_2indep(int(t.sum()), nt, int(c.sum()), nc, method='newcomb')
        p = float(proportions_ztest([t.sum(),c.sum()], [nt,nc])[1]) if (t.sum()+c.sum()) not in [0,nt+nc] else 1.0
    else:
        dof = (vt+vc)**2 / (vt**2/(nt-1)+vc**2/(nc-1)) if se else np.inf
        crit = stats.t.ppf(.975, dof)
        lo, hi = diff-crit*se, diff+crit*se
        p = 2*stats.t.sf(abs(diff/se), dof) if se else (1. if diff==0 else 0.)
    return dict(n_treatment=nt, n_control=nc, treatment_mean=float(mt), control_mean=float(mc),
                effect=float(diff), se=float(se), ci_low=float(lo), ci_high=float(hi), p_value=float(p),
                relative_lift=float(diff/mc) if mc else None,
                incremental_total=float(diff*nt), incremental_total_ci_low=float(lo*nt), incremental_total_ci_high=float(hi*nt))

def design(p0, nt, nc, relative_target=.2, alpha=.05, target_power=.8):
    """Planning sensitivity using observed control rate; not post-hoc observed power."""
    calc = NormalIndPower()
    def h(delta): return 2*np.arcsin(np.sqrt(p0+delta))-2*np.arcsin(np.sqrt(p0))
    def power(delta): return float(calc.power(h(delta), nt, alpha=alpha, ratio=nc/nt, alternative='two-sided'))
    max_delta = 1-p0-1e-9
    mde = brentq(lambda d: power(d)-target_power, 1e-9, max_delta)
    target = p0*relative_target
    return dict(alpha=alpha, target_power=target_power, mde_absolute=float(mde),
                mde_relative=float(mde/p0), planned_relative_lift=relative_target,
                power_at_planned_lift=power(target),
                required_treatment_n=int(np.ceil(calc.solve_power(h(target), power=target_power, alpha=alpha, ratio=nc/nt))),
                method='Two-sided normal approximation with arcsine effect size; baseline estimated from this control sample')

def balance(df):
    numerical = df[['recency','history','mens','womens','newbie']].astype(float)
    categorical = pd.get_dummies(df[['geo_class','channel','history_segment']], dtype=float)
    x = pd.concat([numerical,categorical],axis=1)
    result=[]
    for arm in TREATMENTS:
        t,c=x[df.arm==arm],x[df.arm==CONTROL]
        for col in x:
            denom=np.sqrt((t[col].var(ddof=1)+c[col].var(ddof=1))/2)
            smd=(t[col].mean()-c[col].mean())/denom if denom else 0.
            result.append(dict(arm=arm,covariate=col,treatment_mean=float(t[col].mean()),control_mean=float(c[col].mean()),smd=float(smd)))
    return pd.DataFrame(result)

def analyze(root, costs_path=None):
    root=Path(root)
    out=root/'outputs'
    out.mkdir(exist_ok=True)
    df=clean_hillstrom(root)
    control=df[df.arm==CONTROL]
    rows=[]
    for arm in TREATMENTS:
        t=df[df.arm==arm]
        for metric in ['conversion','revenue','visit']:
            rows.append(dict(arm=arm,metric=metric,**effect(t[metric],control[metric],metric!='revenue')))
    ate=pd.DataFrame(rows)
    # Primary conversion family = two campaign-vs-control hypotheses.
    # Revenue and visit each have separate clearly-labelled secondary families.
    for metric in ate.metric.unique():
        mask=ate.metric==metric
        ate.loc[mask,'p_holm']=multipletests(ate.loc[mask,'p_value'], method='holm')[1]
    ate.to_csv(out/'experiment_effects.csv',index=False)
    bal=balance(df)
    bal.to_csv(out/'balance.csv',index=False)
    srm=stats.chisquare(df.arm.value_counts().reindex([CONTROL,*TREATMENTS]).values)
    plan=[]
    for arm in TREATMENTS:
        for alpha in [.05,.025]:
            plan.append(dict(arm=arm,**design(control.conversion.mean(),int((df.arm==arm).sum()),len(control),alpha=alpha)))
    pd.DataFrame(plan).to_csv(out/'power_mde.csv',index=False)
    hetero=[]
    omnibus=[]
    for arm in TREATMENTS:
        a=df[df.arm.isin([arm,CONTROL])]
        for group in GROUPS:
            for metric in ['conversion','revenue']:
                levels=[]
                for level in sorted(a[group].unique(),key=str):
                    sub=a[a[group]==level]; rest=a[a[group]!=level]
                    e=effect(sub[sub.arm==arm][metric],sub[sub.arm==CONTROL][metric],metric=='conversion')
                    other=effect(rest[rest.arm==arm][metric],rest[rest.arm==CONTROL][metric],metric=='conversion')
                    contrast=e['effect']-other['effect']; se=np.sqrt(e['se']**2+other['se']**2)
                    p=2*stats.norm.sf(abs(contrast/se)) if se else 1.
                    hetero.append(dict(arm=arm,dimension=group,level=str(level),metric=metric,**e,
                                       versus_rest_effect=contrast,interaction_p=float(p)))
                    levels.append(e)
                es=np.array([e['effect'] for e in levels]); vs=np.array([e['se']**2 for e in levels])
                if np.all(vs>0):
                    pooled=np.sum(es/vs)/np.sum(1/vs)
                    q=np.sum((es-pooled)**2/vs)
                    omnibus.append(dict(arm=arm,dimension=group,metric=metric,chi_square=float(q),df=len(es)-1,p_value=float(stats.chi2.sf(q,len(es)-1))))
    h=pd.DataFrame(hetero)
    h['interaction_q_bh']=multipletests(h.interaction_p,method='fdr_bh')[1]
    h.to_csv(out/'heterogeneous_effects.csv',index=False)
    omni=pd.DataFrame(omnibus)
    omni['q_bh']=multipletests(omni.p_value,method='fdr_bh')[1]
    omni.to_csv(out/'heterogeneity_omnibus.csv',index=False)
    comp=[]
    for metric in ['conversion','revenue','visit']:
        comp.append(dict(metric=metric,**effect(df[df.arm==TREATMENTS[0]][metric],df[df.arm==TREATMENTS[1]][metric],metric!='revenue')))
    pd.DataFrame(comp).to_csv(out/'direct_campaign_comparison.csv',index=False)
    budget=ate[ate.metric=='revenue'].copy()
    budget['observed_treatment_revenue']=budget.treatment_mean*budget.n_treatment
    budget['all_treatment_revenue_to_incremental_ratio']=budget.observed_treatment_revenue/budget.incremental_total.replace(0,np.nan)
    budget['break_even_incremental_cost_per_recipient']=budget.effect
    budget['conservative_break_even_cost_per_recipient']=budget.ci_low
    budget['incremental_spend']=np.nan
    budget['incremental_roas']=np.nan
    budget['iroas_ci_low']=np.nan
    budget['iroas_ci_high']=np.nan
    budget['iroas_rank']=pd.Series([pd.NA]*len(budget),index=budget.index,dtype='Int64')
    budget['decision']='Collect observed campaign costs; no spend recommendation supported'
    if costs_path:
        costs=pd.read_csv(costs_path)
        needed={'arm','incremental_spend','source_reference','same_experiment_dollar_units'}
        if not needed.issubset(costs.columns) or costs.arm.duplicated().any() or set(costs.arm)!=set(TREATMENTS):
            raise ValueError('Cost file must cover both arms uniquely with provenance and units attestation')
        if not (np.isfinite(costs.incremental_spend)&(costs.incremental_spend>0)).all() or costs.source_reference.isna().any() or not costs.same_experiment_dollar_units.eq(True).all():
            raise ValueError('Costs require positive observed incremental spend, provenance, and matching revenue units')
        mapping=costs.set_index('arm').incremental_spend
        budget['incremental_spend']=budget.arm.map(mapping)
        budget['incremental_roas']=budget.incremental_total/budget.incremental_spend
        budget['iroas_ci_low']=budget.incremental_total_ci_low/budget.incremental_spend
        budget['iroas_ci_high']=budget.incremental_total_ci_high/budget.incremental_spend
        budget['iroas_rank']=budget.iroas_ci_low.rank(ascending=False,method='min').astype('Int64')
        budget['decision']='Rank by iROAS lower bound; validate marginal response and margin before scaling'
    budget.to_csv(out/'budget_decisions.csv',index=False)
    summary={'participants':len(df),'allocation':{str(k):int(v) for k,v in df.arm.value_counts().items()},
             'srm_p_value':float(srm.pvalue),'max_absolute_smd':float(bal.smd.abs().max()),
             'outcome_window_days':14,'customer_id_status':'Source-row surrogate; true customer duplicates are not identifiable',
             'confidence_intervals':'Marginal 95%; Newcombe score difference for binary outcomes; Welch t for revenue',
             'multiple_testing':'Holm within each two-arm outcome family; BH over all exploratory segment interactions',
             'causal_scope':'ITT within the released randomized email experiment; no cross-dataset linkage',
             'iroas_status':'Calculated from supplied observed costs' if costs_path else 'Unavailable: experiment has no campaign costs'}
    (out/'experiment_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(f'Analyzed {len(df):,} randomized customers; max |SMD|={summary["max_absolute_smd"]:.4f}',flush=True)
    return summary
