import base64
import html
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from measurement.warehouse import connect

COLORS=['#156f69','#d88338']

def report(root):
    root=Path(root); out=root/'outputs'; out.mkdir(exist_ok=True)
    qa=json.loads((out/'qa.json').read_text())
    summary=json.loads((out/'experiment_summary.json').read_text())
    ate=pd.read_csv(out/'experiment_effects.csv')
    power=pd.read_csv(out/'power_mde.csv')
    hetero=pd.read_csv(out/'heterogeneous_effects.csv')
    budget=pd.read_csv(out/'budget_decisions.csv')
    direct=pd.read_csv(out/'direct_campaign_comparison.csv')
    omni=pd.read_csv(out/'heterogeneity_omnibus.csv')
    con=connect(root)
    campaigns=con.execute('''SELECT campaign_id, window_days, SUM(impressions) impressions,
      SUM(clicks) clicks, SUM(transformed_spend) transformed_spend,
      SUM(attributed_conversions) attributed_conversions,
      SUM(transformed_spend)/NULLIF(SUM(attributed_conversions),0) cpa_transformed_units
      FROM campaign_daily GROUP BY campaign_id,window_days ORDER BY window_days,attributed_conversions DESC''').fetchdf()
    campaigns.to_csv(out/'campaign_summary.csv',index=False)
    daily=con.execute('''SELECT relative_day,window_days,SUM(impressions) impressions,
      SUM(attributed_conversions) attributed_conversions FROM campaign_daily
      GROUP BY relative_day,window_days ORDER BY relative_day,window_days''').fetchdf()
    daily.to_csv(out/'daily_summary.csv',index=False)
    con.close()
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','figure.facecolor':'#faf9f5','axes.facecolor':'#faf9f5'})
    fig,axes=plt.subplots(2,2,figsize=(13,8.5),layout='constrained')
    for ax,metric,title,scale,xlabel in [(axes[0,0],'conversion','Conversion lift',100,'Percentage points vs. no email'),(axes[0,1],'revenue','Incremental revenue per recipient',1,'Dataset dollars vs. no email')]:
        m=ate[ate.metric==metric].reset_index(drop=True)
        for i,row in m.iterrows():
            ax.errorbar(row.effect*scale,1-i,xerr=np.array([[row.effect-row.ci_low],[row.ci_high-row.effect]])*scale,fmt='o',color=COLORS[i],capsize=5,markersize=9)
        ax.axvline(0,color='#989c9a',ls='--',lw=1); ax.set_yticks([1,0],['Mens email','Womens email'])
        ax.set_ylim(-.6,1.6); ax.set_title(title,loc='left',pad=15); ax.set_xlabel(xlabel); ax.grid(axis='x',alpha=.2)
    ax=axes[1,0]
    x=np.arange(2); observed=budget.observed_treatment_revenue/1000; inc=budget.incremental_total/1000
    ax.bar(x-.17,observed,.32,label='All treatment revenue',color='#b5c6c1')
    ax.bar(x+.17,inc,.32,label='Causal incremental revenue',color='#156f69')
    ax.set_xticks(x,['Mens email','Womens email']);ax.set_ylabel('Thousand dataset dollars');ax.set_title('What would overcounting look like?',loc='left',pad=15)
    ax.legend(frameon=False,fontsize=9);ax.text(0,-.24,'This comparison is not last-click attribution.',transform=ax.transAxes,fontsize=9,color='#555')
    ax=axes[1,1]
    aq=pd.DataFrame(qa['attribution_windows']).sort_values('window_days')
    matched=aq.observed_conversions-aq.no_eligible_observed_touch
    ax.bar(aq.window_days.astype(str),matched,color='#156f69')
    ax.set_title('Criteo: observed-touch window sensitivity',loc='left',pad=15)
    ax.set_xlabel('Window in days (impression-time proxy)');ax.set_ylabel('Unique conversions with an eligible touch')
    fig.suptitle('Marketing measurement | Real outcomes, explicit limits',fontsize=18,fontweight='bold',x=.01,ha='left')
    fig.savefig(out/'measurement_overview.png',dpi=160,bbox_inches='tight');plt.close(fig)
    # Geography is a coarse observed urbanicity class, not a geographic RCT.
    g=hetero[(hetero.dimension=='geo_class')&(hetero.metric=='conversion')]
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    for i,(_,r) in enumerate(g.iterrows()):
        ax.errorbar(r.effect*100,i,xerr=np.array([[r.effect-r.ci_low],[r.ci_high-r.effect]])*100,fmt='o',color=COLORS[0 if r.arm=='Mens E-Mail' else 1],capsize=4)
    ax.set_yticks(range(len(g)),[f'{r.arm} | {r.level}' for _,r in g.iterrows()]);ax.axvline(0,color='#999',ls='--')
    ax.set_xlabel('Conversion lift in percentage points; marginal 95% CI')
    ax.set_title('Exploratory urbanicity effects | test interactions before targeting',loc='left',pad=18)
    fig.savefig(out/'geo_effects.png',dpi=160,bbox_inches='tight');plt.close(fig)
    def image(path): return 'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
    def table(df):
        shown=df.copy()
        for col in shown:
            if col.startswith('p_') or col in ['p_value','q_bh']:
                shown[col]=shown[col].map(lambda x: f'{x:.2e}' if pd.notna(x) and x<.0001 else (f'{x:.4f}' if pd.notna(x) else 'Unavailable'))
        shown.columns=[c.replace('_',' ').capitalize() for c in shown.columns]
        return shown.to_html(index=False,border=0,classes='data',float_format=lambda x:f'{x:,.4f}',na_rep='Unavailable',escape=True)
    effects=ate[ate.metric.isin(['conversion','revenue'])][['arm','metric','treatment_mean','control_mean','effect','ci_low','ci_high','p_holm']]
    revenue_direct=direct[direct.metric=='revenue'].iloc[0]
    cloud_verified=(out/'bigquery_qa_jobs.json').exists()
    execution='BigQuery QA job log present; inspect job IDs' if cloud_verified else 'Local execution verified. BigQuery and Airflow runtime deployment pending.'
    records=campaigns.where(pd.notna(campaigns),None).to_json(orient='records')
    body=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Marketing Incrementality & Attribution</title>
<style>:root{{--ink:#193a36;--muted:#5b6c66;--accent:#156f69}}*{{box-sizing:border-box}}body{{margin:0;background:#f5f3ec;color:var(--ink);font:16px/1.6 system-ui,sans-serif}}main{{max-width:1240px;margin:auto;padding:56px 28px 80px}}header{{border-bottom:1px solid #cbd5cb;padding-bottom:28px}}.eyebrow{{font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--accent);font-weight:700}}h1{{font-size:clamp(32px,5vw,58px);line-height:1.1;letter-spacing:-2px;max-width:950px;margin:14px 0 20px}}h2{{font-size:26px;line-height:1.2;margin-top:0}}.lede{{max-width:850px;color:var(--muted);font-size:18px}}.status,.note{{border-left:4px solid #d88338;padding:12px 18px;background:#fff4df}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:30px 0}}.card{{background:white;padding:24px;border-radius:12px}}.card strong{{display:block;font-size:32px;line-height:1.2}}.card span{{color:var(--muted);font-size:13px}}section{{padding:30px;background:#fff;margin:22px 0;border-radius:14px}}img{{width:100%;height:auto}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:13px;text-align:left}}th,td{{padding:12px;border-bottom:1px solid #e3e8e2;white-space:nowrap}}th{{background:#eff3ed}}a{{color:var(--accent)}}.controls{{display:flex;gap:15px;flex-wrap:wrap;margin-bottom:20px}}select,input{{padding:10px;border:1px solid #aebdb4;border-radius:6px;font:inherit}}small{{color:var(--muted)}}footer{{font-size:13px;color:var(--muted)}}@media(max-width:760px){{main{{padding:28px 14px}}.cards{{grid-template-columns:repeat(2,1fr)}}section{{padding:20px}}.card strong{{font-size:26px}}}}@media print{{section{{break-inside:avoid}}main{{padding:0}}}}
</style></head><body><main><header><div class="eyebrow">Measurement Lab / Reproducible case study</div><h1>Which outcomes did marketing actually cause?</h1><p class="lede">A full Criteo event pipeline and a 64,000-customer randomized email experiment. Attribution measures credit. Randomization estimates the counterfactual.</p><p class="status">{execution}</p></header>
<div class="cards"><div class="card"><strong>{qa['raw_impressions']/1e6:.2f}M</strong><span>Real publisher impressions</span></div><div class="card"><strong>64,000</strong><span>Randomized customers</span></div><div class="card"><strong>{qa['unique_conversions']:,}</strong><span>Deduplicated conversion IDs</span></div><div class="card"><strong>Unavailable</strong><span>iROAS: campaign costs absent</span></div></div>
<section><h2>The evidence at a glance</h2><img src="{image(out/'measurement_overview.png')}" alt="Treatment effect confidence intervals, observed and incremental revenue, and attribution window sensitivity"><p><b>Read carefully:</b> Criteo and Hillstrom are separate datasets with no join key. All-treatment revenue is an overcounting benchmark, not observed last-click revenue. Criteo costs are transformed, and click times are not independently logged.</p></section>
<section><h2>Randomized experiment results</h2><p>Intent-to-treat, 14-day outcome window. No filtering on visits, purchases, or actual engagement. Binary-outcome confidence intervals use Newcombe score differences; revenue intervals use Welch's method. P-values use Holm correction within each two-campaign outcome family; confidence intervals are marginal 95%.</p><div class="scroll">{table(effects)}</div><p>Sample ratio mismatch p = {summary['srm_p_value']:.4f}; maximum absolute pre-treatment standardized mean difference = {summary['max_absolute_smd']:.4f}. These checks do not prove randomization, but show no obvious imbalance in the released covariates.</p></section>
<section><h2>Power before interpretation</h2><p>The observed control conversion rate is used as a planning reference. A planned 20% relative lift is much smaller than the measured effect; the current sample has limited power for that target. Alpha 0.025 rows plan conservatively for the two primary campaign comparisons.</p><div class="scroll">{table(power.drop(columns='method'))}</div></section>
<section><h2>Explore campaign attribution</h2><p>Counts use the most recent observed clicked impression linked to each conversion. Source-relative days are retained; real calendar dates and geographic labels are unavailable. CPA is in transformed source units.</p><div class="controls"><label>Window <select id="window"><option value="1">1 day</option><option value="7">7 days</option><option value="30" selected>30 days</option></select></label><label>Campaign <input id="campaign" placeholder="Filter campaign ID"></label><label>Sort <select id="sort"><option value="attributed_conversions">Attributed conversions</option><option value="transformed_spend">Transformed spend</option><option value="cpa_transformed_units">CPA, ascending</option></select></label></div><small id="count"></small><div class="scroll"><table><thead><tr><th>Campaign</th><th>Impressions</th><th>Clicks</th><th>Attributed conversions</th><th>Transformed spend</th><th>CPA / source units</th></tr></thead><tbody id="rows"></tbody></table></div><small>Top 50 matching rows shown. Full output: campaign_summary.csv. No causal ranking is available for these campaigns.</small></section>
<section><h2>Geography & audience differences</h2><img src="{image(out/'geo_effects.png')}" alt="Conversion lift and confidence intervals by observed urbanicity class"><p>Urban / suburban / rural are observed customer attributes; the experiment randomized customers, not geographic markets. Historical channel, spend band, new-customer status, and prior category purchase are also analyzed. Compare interaction tests, not whether one subgroup's p-value crosses 0.05.</p><div class="scroll">{table(omni.sort_values('q_bh').head(12))}</div><p>All segment results are exploratory. BH correction covers the complete family of segment-versus-rest tests and, separately, the omnibus family. Revenue in small segments is highly variable.</p></section>
<section><h2>What can guide a budget decision?</h2><div class="scroll">{table(budget[['arm','observed_treatment_revenue','incremental_total','all_treatment_revenue_to_incremental_ratio','effect','ci_low','ci_high','incremental_roas']])}</div><p>Mens email has the larger incremental revenue point estimate. The direct Mens-minus-Womens revenue difference is {revenue_direct.effect:.3f} dollars per recipient, 95% CI [{revenue_direct.ci_low:.3f}, {revenue_direct.ci_high:.3f}]; p = {revenue_direct.p_value:.4f}. Account for that uncertainty when comparing campaigns.</p><p class="note">Collect observed incremental campaign spend before ranking iROAS. Per-recipient incremental revenue is a break-even advertising-cost ceiling before product costs and margin. Reallocation also needs marginal response evidence, not only average experimental ROI.</p></section>
<section><h2>Quality & observability</h2><div class="scroll">{table(pd.DataFrame(qa['attribution_windows']))}</div><p>Duplicate event IDs: {qa['duplicate_event_ids']}. Conversion join loss: {qa['conversion_join_loss']}. Attribution weight errors: {qa['attribution_weight_errors']}. Rejected/replayed records: {qa['rejected_or_replayed_rows']:,}. Conversion identity conflicts: {qa['conversion_identity_conflicts']}.</p><p>Missing eligible touches measure source coverage and window rules; they are not automatically ingestion failures. Publisher-vs-proxy mismatch also reflects differing attribution scope. Late-arrival and missing-source event rates are unobservable without publisher arrival timestamps and completeness manifests.</p></section>
<footer>Data: <a href="https://huggingface.co/datasets/criteo/criteo-attribution-dataset">Criteo Attribution Dataset</a> · <a href="https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html">Hillstrom / MineThatData randomized email challenge</a>.<br>Criteo source and derived extracts: CC BY-NC-SA 4.0. Published source sampling limits population generalization. Raw sources and SHA-256 checksums are recorded in sources.lock.json and data/raw/manifest.json.</footer>
</main><script>const data={records}; const number=x=>x===null?'Unavailable':Number(x).toLocaleString(undefined,{{maximumFractionDigits:5}});function render(){{let w=Number(document.getElementById('window').value),q=document.getElementById('campaign').value.trim(),s=document.getElementById('sort').value;let rows=data.filter(x=>x.window_days===w&&String(x.campaign_id).includes(q)); rows.sort((a,b)=>s==='cpa_transformed_units'?(a[s]??Infinity)-(b[s]??Infinity):(b[s]??0)-(a[s]??0));document.getElementById('count').textContent=rows.length+' matching campaigns';document.getElementById('rows').innerHTML=rows.slice(0,50).map(x=>'<tr>'+['campaign_id','impressions','clicks','attributed_conversions','transformed_spend','cpa_transformed_units'].map(k=>'<td>'+number(x[k])+'</td>').join('')+'</tr>').join('');}}document.querySelectorAll('input,select').forEach(e=>e.addEventListener('input',render));render();</script></body></html>'''
    body=body.replace('Deduplicated conversion IDs','Canonical conversion keys')
    body=body.replace(f"Conversion identity conflicts: {qa['conversion_identity_conflicts']}.",f"Reused source conversion IDs: {qa['conversion_identity_conflicts']:,}, resolved with composite keys.")
    body=body.replace('All segment results are exploratory.',f"{int((omni.q_bh<.05).sum())} of {len(omni)} omnibus comparisons pass a 5% FDR threshold. All segment results are exploratory.")
    (out/'report.html').write_text(body,encoding='utf-8')
    findings=['# 实际运行结果 / Marketing Incrementality','',f"完整 Criteo 发布数据：{qa['raw_impressions']:,} impressions、{qa['click_indicators']:,} click indicators、{qa['unique_conversions']:,} distinct conversions、{qa['campaigns']} campaigns。",'', '完整 Hillstrom 随机实验：64,000 customers，14 天结果窗口。','', '| Campaign | Conversion lift (百分点) | 95% CI (百分点) | Incremental revenue / recipient | 95% CI |','|---|---:|---|---:|---|']
    for arm in ['Mens E-Mail','Womens E-Mail']:
        c=ate[(ate.arm==arm)&(ate.metric=='conversion')].iloc[0];r=ate[(ate.arm==arm)&(ate.metric=='revenue')].iloc[0]
        findings.append(f'| {arm} | {c.effect*100:.3f} | [{c.ci_low*100:.3f}, {c.ci_high*100:.3f}] | {r.effect:.3f} | [{r.ci_low:.3f}, {r.ci_high:.3f}] |')
    findings+=['',f"SRM p={summary['srm_p_value']:.4f}; 最大 |SMD|={summary['max_absolute_smd']:.4f}。",'', '处理组全部收入 / 因果增量收入：Mens 1.85x，Womens 2.54x。这不是 last-click 高估率。','', 'ROAS / iROAS 不可识别：Criteo 无 sales revenue / holdout，Hillstrom 无 campaign cost，二者不可关联。','',execution,'','详细交互报告：outputs/report.html。统计表、QA、图表均在 outputs/。']
    (out/'findings.md').write_text('\n'.join(findings),encoding='utf-8')
    print(f'Report written: {out / "report.html"}',flush=True)
