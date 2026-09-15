import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from measurement.warehouse import connect

LOG=logging.getLogger(__name__)
TABLES=['daily_campaign_metrics','conversion_paths','conversion_lag_quantiles','conversion_lag_histogram',
 'last_click_attribution','first_click_attribution','linear_attribution','publisher_attribution','model_credits',
 'window_comparison','campaign_reconciliation','daily_measurement','attribution_reconciliation']
EXPORT=['daily_campaign_metrics','conversion_lag_quantiles','conversion_lag_histogram','window_comparison','campaign_reconciliation','daily_measurement','attribution_reconciliation']

def run_sql(root):
    root=Path(root);con=connect(root)
    try:
        for path in sorted((root/'sql/analysis').glob('*.sql')):
            LOG.info('Executing %s',path.name);con.execute(path.read_text())
        invalid=con.execute('''SELECT COUNT(*) FROM (SELECT model,window_days,conversion_key FROM model_credits
          GROUP BY model,window_days,conversion_key HAVING ABS(SUM(attribution_weight)-1)>1e-8)''').fetchone()[0]
        if invalid: raise ValueError(f'{invalid} conversion-credit conservation errors')
        out=root/'outputs/tables';out.mkdir(parents=True,exist_ok=True)
        for name in EXPORT: con.execute(f'SELECT * FROM {name} ORDER BY ALL').fetchdf().to_csv(out/f'{name}.csv',index=False)
        summary=con.execute('''SELECT COUNT(*) AS conversions,
          SUM(CASE WHEN linked_clicks>0 THEN 1 ELSE 0 END)*1.0/COUNT(*) AS click_through_conversion_share,
          SUM(CASE WHEN campaign_count>1 THEN 1 ELSE 0 END) AS multi_campaign_paths,
          SUM(CASE WHEN linked_clicks>1 THEN 1 ELSE 0 END) AS multi_click_paths FROM conversion_paths''').fetchdf().to_dict('records')[0]
        rank=con.execute('''SELECT MAX(ABS(a.campaign_rank-b.campaign_rank)) FROM campaign_reconciliation a
          JOIN campaign_reconciliation b ON a.campaign_id=b.campaign_id AND a.window_days=b.window_days
          WHERE a.model='first_click_proxy' AND b.model='last_click_proxy' ''').fetchone()[0]
        summary.update(first_last_max_campaign_rank_change=int(rank),credit_conservation_errors=int(invalid),rows=int(con.execute('SELECT COUNT(*) FROM impressions').fetchone()[0]))
        (root/'outputs/reconciliation_summary.json').write_text(json.dumps(summary,indent=2))
        return summary
    finally: con.close()

def score_health(daily,lookback=7,threshold=3.):
    if lookback<2 or threshold<=0: raise ValueError('lookback >=2 and threshold >0 required')
    daily=daily.sort_values('relative_day').copy();frames=[]
    metrics=['impressions','clicks','ctr','conversions','attributed_conversions','attribution_rate','unique_users','transformed_cost','malformed_conversion_key_rate','replay_duplicate_rate']
    for metric in metrics:
        values=daily[metric].astype(float)
        prior=values.where(daily.boundary_day.eq(0)).shift(1)
        baseline=prior.rolling(lookback,min_periods=lookback).mean()
        std=prior.rolling(lookback,min_periods=lookback).std(ddof=1)
        delta=values-baseline
        z=delta/std.replace(0,np.nan)
        z=z.where(std.ne(0),np.where(delta.abs()<1e-12,0.,np.nan))
        severity=np.where(baseline.isna(),'warmup',np.where(std.eq(0)&delta.abs().ge(1e-12),'zero_variance_review',np.where(z.abs()>=threshold,'review','normal')))
        severity=np.where(daily.boundary_day.eq(1),'boundary_excluded',severity)
        frames.append(pd.DataFrame({'relative_day':daily.relative_day,'metric':metric,'observed_value':values,'baseline':baseline,'deviation':delta,'z_score':z,'severity':severity}))
    return pd.concat(frames,ignore_index=True)

def health(root):
    root=Path(root);cfg=json.loads((root/'settings.json').read_text())
    daily=pd.read_csv(root/'outputs/tables/daily_measurement.csv')
    frame=score_health(daily,cfg['health_lookback_days'],cfg['health_z_threshold'])
    frame.to_csv(root/'outputs/tables/measurement_health.csv',index=False)
    return frame
