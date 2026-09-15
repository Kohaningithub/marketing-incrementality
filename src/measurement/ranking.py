"""Campaign ranking sensitivity on a fixed, definition-independent volume cohort."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

METRICS={'credited_conversions':False,'transformed_cost_per_attributed_conversion':True,'attributed_conversion_share':False}

def compare_rankings(frame,min_impressions=10000,min_observed_conversions=100):
    if min_impressions<0 or min_observed_conversions<1: raise ValueError('Invalid volume threshold')
    subset=frame[(frame.impressions>=min_impressions)&(frame.observed_conversions>=min_observed_conversions)].copy()
    if subset.duplicated(['campaign_id','model','window_days']).any(): raise ValueError('Duplicate campaign/definition rows')
    ranks=[];pairs=[]
    for (window,metric),ascending in [((w,m),asc) for w in sorted(subset.window_days.unique()) for m,asc in METRICS.items()]:
        wide=subset[subset.window_days==window].pivot(index='campaign_id',columns='model',values=metric)
        # Fractional-credit accumulation must not invent differences between tied totals.
        if metric=='credited_conversions':wide=wide.round(8)
        else:wide=wide.round(12)
        wide=wide.replace([np.inf,-np.inf],np.nan)
        ordered=wide.rank(ascending=ascending,method='min')
        for method in wide.columns:
            for cid in wide.index:
                base=ordered.loc[cid,'publisher'];rank=ordered.loc[cid,method]
                ranks.append(dict(window_days=int(window),metric=metric,campaign_id=int(cid),method=method,
                    metric_value=wide.loc[cid,method],campaign_rank=rank,publisher_rank=base,
                    rank_change_vs_criteo=rank-base,absolute_rank_change=abs(rank-base)))
        for a in wide.columns:
            for b in wide.columns:
                valid=wide[[a]].notna().iloc[:,0]&wide[[b]].notna().iloc[:,0]
                x=wide.loc[valid,a];y=wide.loc[valid,b]
                rho=x.corr(y,method='spearman') if len(x)>1 and x.nunique()>1 and y.nunique()>1 else np.nan
                dif=(ordered.loc[valid,a]-ordered.loc[valid,b]).abs()
                topa=set(ordered.index[ordered[a]<=10]);topb=set(ordered.index[ordered[b]<=10])
                pairs.append(dict(window_days=int(window),metric=metric,method_a=a,method_b=b,
                    cohort_campaigns=len(wide),paired_campaigns=int(valid.sum()),spearman_rho=rho,
                    mean_absolute_rank_change=dif.mean(),max_absolute_rank_change=dif.max(),
                    campaigns_with_rank_change=int((dif>0).sum()),top10_a=len(topa),top10_b=len(topb),
                    top10_overlap=len(topa&topb),top10_jaccard=len(topa&topb)/len(topa|topb) if topa|topb else np.nan))
    return pd.DataFrame(ranks),pd.DataFrame(pairs)

def analyze_rankings(root):
    root=Path(root);cfg=json.loads((root/'ranking.settings.json').read_text());out=root/'outputs/tables'
    frame=pd.read_csv(out/'campaign_reconciliation.csv')
    ranks,pairs=compare_rankings(frame,cfg['ranking_min_impressions'],cfg['ranking_min_observed_conversions'])
    if ranks.empty: raise ValueError('No campaigns meet configured volume thresholds')
    ranks.to_csv(out/'campaign_ranking_comparison.csv',index=False)
    pairs.to_csv(out/'campaign_rank_correlations.csv',index=False)
    summary=dict(min_impressions=cfg['ranking_min_impressions'],min_observed_conversions=cfg['ranking_min_observed_conversions'],
        eligible_campaigns=int(ranks.campaign_id.nunique()),total_campaigns=int(frame.campaign_id.nunique()),
        cohort_rule='Fixed full-release impressions and observed canonical conversions; independent of attribution model/window',
        rank_rule='Count/share descending, transformed CPA ascending; competition ranks; undefined CPA excluded pairwise; top10 includes ties',
        scope='Descriptive optimization sensitivity, not a causal performance or spending recommendation')
    (root/'outputs/ranking_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary
