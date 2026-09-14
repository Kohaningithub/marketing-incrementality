import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest
from measurement.warehouse import connect
from measurement.uplift_source import register_uplift
from measurement.experiment_design import readiness

LOG=logging.getLogger(__name__)
FEATURES=[f'f{i}' for i in range(12)]

def binary_effect(yt,nt,yc,nc):
    if min(nt,nc)<2 or not (0<=yt<=nt and 0<=yc<=nc): raise ValueError('Invalid binary sufficient statistics')
    pt,pc=yt/nt,yc/nc;diff=pt-pc
    low,high=confint_proportions_2indep(yt,nt,yc,nc,method='newcomb')
    p=float(proportions_ztest([yt,yc],[nt,nc])[1]) if 0<yt+yc<nt+nc else 1.
    return dict(n_treatment=int(nt),n_control=int(nc),treatment_events=int(yt),control_events=int(yc),
      treatment_rate=pt,control_rate=pc,absolute_lift=diff,relative_lift=diff/pc if pc else None,
      ci_low=float(low),ci_high=float(high),p_value=p,incremental_per_100k=diff*100000,
      incremental_per_100k_low=float(low*100000),incremental_per_100k_high=float(high*100000))

def analyze_criteo(root):
    root=Path(root);out=root/'outputs/tables';out.mkdir(parents=True,exist_ok=True)
    con=connect(root)
    try:
        register_uplift(con,root)
        cols=[f'SUM(CASE WHEN {f} IS NULL OR NOT isfinite({f}) THEN 1 ELSE 0 END) AS {f}' for f in FEATURES]
        missing=con.execute('SELECT '+','.join(cols)+' FROM uplift_raw').fetchdf()
        invalid=con.execute('''SELECT COUNT(*) FROM uplift_raw WHERE treatment IS NULL OR treatment NOT IN(0,1)
          OR exposure IS NULL OR exposure NOT IN(0,1) OR visit IS NULL OR visit NOT IN(0,1)
          OR conversion IS NULL OR conversion NOT IN(0,1)''').fetchone()[0]
        counts=con.execute('''SELECT treatment,COUNT(*) AS n,SUM(conversion) AS conversions,SUM(visit) AS visits,
          SUM(exposure) AS exposures FROM uplift_raw GROUP BY treatment ORDER BY treatment''').fetchdf()
        n=int(counts.n.sum())
        if n!=13979592 or invalid: raise ValueError(f'Unexpected uplift release: n={n}, invalid assignment/outcome rows={invalid}')
        counts.to_csv(out/'criteo_arm_summary.csv',index=False)
        t=counts[counts.treatment==1].iloc[0];c=counts[counts.treatment==0].iloc[0]
        effects=pd.DataFrame([{'outcome':outcome,**binary_effect(int(t[col]),int(t.n),int(c[col]),int(c.n))} for outcome,col in [('conversion','conversions'),('visit','visits')]])
        effects.to_csv(out/'criteo_itt.csv',index=False)
        balances=[]
        for f in FEATURES:
            rows=con.execute(f'SELECT treatment,AVG({f}),VAR_SAMP({f}) FROM uplift_raw GROUP BY treatment ORDER BY treatment').fetchall()
            mc,vc=rows[0][1:];mt,vt=rows[1][1:];den=np.sqrt((vt+vc)/2)
            balances.append(dict(feature=f,control_mean=mc,treatment_mean=mt,smd=(mt-mc)/den if den else 0.,missing_or_nonfinite=int(missing[f].iloc[0])))
        pd.DataFrame(balances).to_csv(out/'criteo_feature_balance.csv',index=False)
        exposure=con.execute('''SELECT treatment,exposure,COUNT(*) AS n,AVG(conversion) AS conversion_rate,
          AVG(visit) AS visit_rate FROM uplift_raw GROUP BY treatment,exposure ORDER BY treatment,exposure''').fetchdf()
        exposure.to_csv(out/'criteo_exposure.csv',index=False)
        baseline=float(c.conversions/c.n)
        plan=[readiness(baseline,int(total),float(t.n/n),relative_lift=.2) for total in [100000,250000,500000,1000000,2000000,5000000,10000000,n]]
        pd.DataFrame(plan).to_csv(out/'experiment_readiness.csv',index=False)
        summary=dict(rows=n,coverage='full four-shard publisher release',treatment_n=int(t.n),control_n=int(c.n),
          treatment_fraction=float(t.n/n),exposure_given_treatment=float(t.exposures/t.n),exposure_given_control=float(c.exposures/c.n),
          rounded_allocation_reference=.85,allocation_reference_p=float(stats.binomtest(int(t.n),n,p=.85).pvalue),
          srm_status='Not a confirmatory SRM test: .85 is a rounded release statistic, original assignment probabilities and trial IDs unavailable',
          max_absolute_smd=float(max(abs(b['smd']) for b in balances)),missing_feature_values=int(missing.sum(axis=1).iloc[0]),
          invalid_assignment_outcome_rows=int(invalid),
          causal_scope='Assignment-based benchmark contrast. Non-uniform release sampling prevents recovery of original population incrementality.',
          iv_status='Not estimated: exclusion, monotonicity and sampling assumptions cannot be verified from anonymized release',
          cloud_executed=False,airflow_executed=False)
        (root/'outputs/criteo_experiment_summary.json').write_text(json.dumps(summary,indent=2))
        LOG.info('Full Criteo uplift ITT: %s rows',n)
        return summary
    finally: con.close()
