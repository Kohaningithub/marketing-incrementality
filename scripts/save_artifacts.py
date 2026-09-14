"""Publish aggregate artifacts only; never raw records, row predictions or credentials."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
dest=root/'artifacts';dest.mkdir(exist_ok=True)
for name in ['report.html','qa.json','reconciliation_summary.json','criteo_experiment_summary.json','uplift_summary.json','delivery_summary.json']:
    shutil.copy2(root/'outputs'/name,dest/name)
for directory,extension in [('tables','*.csv'),('figures','*.png')]:
    target=dest/directory;target.mkdir(exist_ok=True)
    for path in (root/'outputs'/directory).glob(extension): shutil.copy2(path,target/path.name)
print('Saved aggregate report, figures, tables and run summaries; no raw records')
