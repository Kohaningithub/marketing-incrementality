"""Copy a small auditable run snapshot; never copy raw records or credentials."""
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
destination=root/'artifacts'
destination.mkdir(exist_ok=True)
names=['report.html','findings.md','measurement_overview.png','geo_effects.png','qa.json','experiment_summary.json','experiment_effects.csv','balance.csv','power_mde.csv','heterogeneous_effects.csv','heterogeneity_omnibus.csv','direct_campaign_comparison.csv','budget_decisions.csv','campaign_summary.csv','daily_summary.csv']
for name in names:
    shutil.copy2(root/'outputs'/name,destination/name)
print(f'Saved {len(names)} report/aggregate artifacts; no raw records')
