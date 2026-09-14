"""Two-arm T-learner; feature-group splits; validation selection; untouched test."""
import hashlib
import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits
import joblib
from measurement.warehouse import connect
from measurement.uplift_source import register_uplift
from measurement.criteo_experiment import FEATURES,binary_effect

LOG=logging.getLogger(__name__)

def uplift_curve(y,t,score,propensity,points=100):
    """IPW cumulative incremental outcomes per total evaluated participant.

    G(q)=sum_top_q[Y*T/p - Y*(1-T)/(1-p)] / N.
    AUUC=integral G; Qini=integral(G-q*G(1)); both in outcomes/person.
    The random line is the expected random-ranking baseline, not simulated users.
    Equal scores are averaged as a block, avoiding arbitrary tie advantages.
    """
    y=np.asarray(y,float);t=np.asarray(t,int);score=np.asarray(score,float)
    if not (len(y)==len(t)==len(score)) or len(y)==0 or not 0<propensity<1: raise ValueError('Invalid evaluation input')
    if not np.isfinite(score).all() or not np.isin(t,[0,1]).all() or not np.isin(y,[0,1]).all(): raise ValueError('Invalid outcomes, assignment or scores')
    order=np.argsort(-score,kind='stable');s=score[order]
    z=(y*t/propensity-y*(1-t)/(1-propensity))[order]
    ends=np.r_[np.flatnonzero(np.diff(s)!=0)+1,len(s)]
    x=np.r_[0,ends/len(s)];gain=np.r_[0,np.cumsum(z)[ends-1]/len(s)]
    grid=np.linspace(0,1,points+1);g=np.interp(grid,x,gain)
    random=grid*gain[-1]
    # Exact integration over score-block endpoints, not the display-grid approximation.
    auuc=float(np.trapezoid(gain,x));qini=auuc-float(gain[-1])/2
    return pd.DataFrame({'target_fraction':grid,'incremental_per_person':g,'random_per_person':random,'qini_gain_per_person':g-random}),dict(auuc=auuc,qini=qini,treated_all_gain_per_person=float(gain[-1]))

def prepare_sample(root):
    root=Path(root);cfg=json.loads((root/'settings.json').read_text());dest=root/'data/processed/uplift_model_sample.parquet'
    meta=root/'data/processed/uplift_model_sample.json'
    spec={'version':1,'fraction':cfg['uplift_model_fraction'],'train':cfg['train_fraction'],'validation':cfg['validation_fraction'],'seed':cfg['seed'],
          'source':json.loads((root/'uplift.lock.json').read_text())['revision']}
    if dest.exists() and meta.exists() and json.loads(meta.read_text())==spec:
        LOG.info('Reusing deterministic uplift feature-group sample');return dest
    con=connect(root)
    try:
        register_uplift(con,root)
        # Only features determine group membership; outcomes and treatment never enter the split.
        fields=','.join(f'CAST({f} AS VARCHAR)' for f in FEATURES)
        con.execute(f'''CREATE OR REPLACE TEMP VIEW uplift_grouped AS SELECT *,
          md5('{cfg['seed']}:'||concat_ws('|',{fields})) AS feature_group FROM uplift_raw''')
        fraction=cfg['uplift_model_fraction'];train=cfg['train_fraction'];val=cfg['validation_fraction']
        if not 0<fraction<=1 or abs(train+val+cfg['test_fraction']-1)>1e-9: raise ValueError('Invalid split settings')
        query=f'''SELECT row_id,feature_group,{','.join(FEATURES)},treatment,conversion,visit,
          CASE WHEN CAST('0x'||substr(feature_group,9,8) AS UBIGINT)/4294967296.0 < {train} THEN 'train'
          WHEN CAST('0x'||substr(feature_group,9,8) AS UBIGINT)/4294967296.0 < {train+val} THEN 'validation' ELSE 'test' END AS split
          FROM uplift_grouped WHERE CAST('0x'||substr(feature_group,1,8) AS UBIGINT)/4294967296.0 < {fraction}'''
        path=dest.resolve().as_posix().replace("'","''")
        con.execute(f"COPY ({query}) TO '{path}' (FORMAT PARQUET)")
        meta.write_text(json.dumps(spec,indent=2))
    finally: con.close()
    return dest

def fit_uplift(root):
    root=Path(root);cfg=json.loads((root/'settings.json').read_text());out=root/'outputs/tables';out.mkdir(parents=True,exist_ok=True)
    path=prepare_sample(root)
    cache=root/'data/processed/uplift_model_cache.json'
    fingerprint=hashlib.sha256((Path(__file__).read_text()+(root/'settings.json').read_text()+(root/'uplift.lock.json').read_text()).encode()).hexdigest()
    if cache.exists() and json.loads(cache.read_text()).get('fingerprint')==fingerprint and all((out/f'{n}.csv').exists() for n in ['uplift_curve','uplift_deciles','uplift_validation']):
        LOG.info('Reusing versioned model/evaluation outputs');return json.loads((root/'outputs/uplift_summary.json').read_text())
    data=pd.read_parquet(path)
    if data.groupby('feature_group').split.nunique().max()!=1: raise ValueError('Feature groups leak across splits')
    if data[FEATURES].isna().any().any(): raise ValueError('Unexpected missing model features; review imputation policy')
    splits={s:data[data.split==s] for s in ['train','validation','test']}
    counts=data.groupby(['split','treatment']).agg(n=('conversion','size'),conversions=('conversion','sum')).reset_index()
    counts.to_csv(out/'uplift_split_counts.csv',index=False)
    train=splits['train'];valid=splits['validation'];test=splits['test']
    candidates=[];models={}
    with threadpool_limits(limits=2):
        for iterations in cfg['model_iterations']:
            pair=[]
            for arm in [0,1]:
                rows=train[train.treatment==arm]
                model=HistGradientBoostingClassifier(max_iter=iterations,max_leaf_nodes=cfg['model_max_leaf_nodes'],
                    learning_rate=cfg['model_learning_rate'],min_samples_leaf=200,l2_regularization=1.,
                    early_stopping=False,random_state=cfg['seed'])
                model.fit(rows[FEATURES].to_numpy(dtype=np.float32),rows.conversion)
                pair.append(model)
            x=valid[FEATURES].to_numpy(dtype=np.float32)
            score=pair[1].predict_proba(x)[:,1]-pair[0].predict_proba(x)[:,1]
            _,metrics=uplift_curve(valid.conversion,valid.treatment,score,float(valid.treatment.mean()))
            candidates.append(dict(iterations=iterations,**metrics));models[iterations]=pair
            LOG.info('Validation T-learner iterations=%s Qini=%.6g',iterations,metrics['qini'])
        chosen=max(candidates,key=lambda d:d['qini'])['iterations'];pair=models[chosen]
        x=test[FEATURES].to_numpy(dtype=np.float32)
        score=pair[1].predict_proba(x)[:,1]-pair[0].predict_proba(x)[:,1]
    curve,metrics=uplift_curve(test.conversion,test.treatment,score,float(test.treatment.mean()))
    curve.to_csv(out/'uplift_curve.csv',index=False);pd.DataFrame(candidates).to_csv(out/'uplift_validation.csv',index=False)
    ranked=test.assign(score=score).sort_values(['score','row_id'],ascending=[False,True]).copy()
    ranked['decile']=(np.arange(len(ranked))*10//len(ranked)+1).astype(int)
    deciles=[]
    for d,rows in ranked.groupby('decile'):
        t=rows[rows.treatment==1];c=rows[rows.treatment==0]
        deciles.append(dict(decile=int(d),sample_size=len(rows),mean_predicted_lift=float(rows.score.mean()),**binary_effect(int(t.conversion.sum()),len(t),int(c.conversion.sum()),len(c))))
    pd.DataFrame(deciles).to_csv(out/'uplift_deciles.csv',index=False)
    joblib.dump(pair,root/'data/processed/uplift_t_learner.joblib')
    # Actual held-out outcomes are local-only, never published as individual records.
    ranked[['row_id','split','treatment','conversion','score','decile']].to_parquet(root/'data/processed/uplift_test_predictions.parquet',index=False)
    summary=dict(source_rows=13979592,model_rows=len(data),train_rows=len(train),validation_rows=len(valid),test_rows=len(test),
      sample_fraction=cfg['uplift_model_fraction'],sample_method='MD5 of anonymized feature vector + fixed seed; exact-feature groups never cross splits',
      primary_outcome='conversion',chosen_iterations=chosen,propensity=float(test.treatment.mean()),**metrics,
      unit='incremental conversions per evaluated participant; multiply by 100000 for per-100k units',
      uncertainty='Decile marginal Newcombe 95% intervals; model ranking/curve has no population-level confidence claim',
      interpretation='Held-out benchmark targeting evidence; not a validated advertiser policy, demographic segment or ROI forecast')
    (root/'outputs/uplift_summary.json').write_text(json.dumps(summary,indent=2))
    cache.write_text(json.dumps({'fingerprint':fingerprint}))
    LOG.info('Uplift test evaluation: n=%s Qini=%s',len(test),metrics['qini'])
    return summary
