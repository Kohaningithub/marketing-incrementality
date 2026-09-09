# BigQuery and Airflow deployment

This repository has been run locally with real datasets. Cloud execution and a live Airflow scheduler were not performed in the initial environment: Docker and the GCP CLI/credentials were unavailable, and the user requested local completion plus deployment configuration. Syntax checks do not substitute for service execution.

## BigQuery

The Python adapter uses [the official BigQuery client](https://docs.cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.client.Client) and [Parquet load jobs](https://cloud.google.com/bigquery/docs/loading-data-cloud-storage-parquet). `load_table_from_file` uploads local verified files directly; a GCS bucket is not required. Use Application Default Credentials configured outside this repository. Never commit credentials.

1. Enable the BigQuery API in your selected GCP project and configure ADC with `gcloud auth application-default login`. The principal needs permission to create jobs and the chosen dataset/tables. If a dataset already exists, its location must match `--location`.
2. Install project cloud dependencies and complete the local `run` command.
3. Substitute the actual project ID below. Render SQL first, then load and execute it.

```powershell
.venv/Scripts/python.exe -m pip install -e ".[cloud,test]"
.venv/Scripts/python.exe -m measurement.cli render-cloud --project YOUR_PROJECT_ID
.venv/Scripts/python.exe -m measurement.cli cloud-upload --project YOUR_PROJECT_ID --dataset marketing_measurement --location US
.venv/Scripts/python.exe -m measurement.cli cloud-transform --project YOUR_PROJECT_ID --dataset marketing_measurement --location US --maximum-bytes-billed 5000000000
.venv/Scripts/python.exe -m measurement.cli cloud-qa --project YOUR_PROJECT_ID --dataset marketing_measurement --location US
```

`cloud-upload` verifies the locked hashes, adds the same source-row impression key used locally, and performs a `WRITE_TRUNCATE` snapshot load for each independent shard staging table. The raw view unions the six staging tables. Retrying the complete upload replaces shards rather than appending duplicate events. Each load call uses its own job ID; the client handles retries of that call. The script uploads the cleaned participant table separately and writes an audit log.

`cloud-transform` transpiles the reviewed local SQL to GoogleSQL, qualifies only real table names, creates relative-day range partitions for impressions and campaign/day marts, clusters those tables by campaign/context, and runs the experimental aggregate SQL. The byte cap applies per query statement, not to the whole run, and is not a dollar budget. Staging tables are full snapshots; partitions support downstream queries, not an incremental source ingestion claim.

`cloud-qa` runs BigQuery `ASSERT` statements for nonempty inputs, unique canonical keys, window rules, weight conservation, join integrity and mart reconciliation. Query/load job IDs and processed-byte metadata are written under `outputs/`. Inspect those records and compare BigQuery counts to `outputs/qa.json` before describing the cloud deployment as verified. The user-facing report is computed locally from the same source; it is not a live BigQuery dashboard.

Transforms replace dependent tables sequentially. There is no atomic publication of the entire mart family. The DAG limits this project to one active run; consumers of a production deployment should use versioned datasets and promote a validated run atomically. Partial failure is inspectable and rerunnable, but should not expose an unfinished run as a completed report.

Render examples in the initial artifact use the explicitly nonexecuted identifier `measurement-demo-2026`; this is not a discovered or configured GCP project. Regenerate with your real ID.

## Airflow local development container

The DAG uses the [Airflow Task SDK](https://airflow.apache.org/docs/task-sdk/stable/index.html) and the official Airflow 3.1.7 Python 3.12 image. The supplied single-container `airflow standalone` configuration is a local development setup. It is not a hardened production cluster. See the [Airflow Docker documentation](https://airflow.apache.org/docs/apache-airflow/3.1.7/howto/docker-compose/index.html) for supported deployment guidance.

Install Docker Desktop with Linux containers, then run from the project root:

```powershell
docker compose up --build -d
docker compose logs airflow
docker compose exec airflow python -m pytest /opt/project/tests/test_airflow_runtime.py -q
docker compose exec airflow airflow dags list-import-errors
docker compose exec airflow airflow dags unpause marketing_incrementality
docker compose exec airflow airflow dags trigger marketing_incrementality
```

Open the local UI on `http://localhost:8080` and use the credentials emitted by the standalone process. The host port binds to loopback only. The DAG is manual because the publisher inputs are historical static releases. `catchup=False`, maximum one active run, two retries per task and a one-hour task timeout are configured. The persistent volume retains Airflow metadata; explicit source mounts retain downloaded data, reports and the current DAG. On Linux, make the mounted `data/` and `outputs/` directories writable by the container's Airflow user.

For actual BigQuery execution inside the container, copy `.env.example` to `.env`, set the real project ID and existing ADC file path, and start with the credential overlay:

```powershell
docker compose -f compose.yaml -f compose.cloud.yaml up --build -d
```

The overlay mounts the credential file read-only. Credentials are not copied into the image. The cloud branch executes after successful local analysis and before reporting. BigQuery job failures fail the task and stop publication. No email or Slack messages are sent by this project.

## Late / missing event monitoring

The historical sources have no original received-at timestamps or authoritative complete event manifest. Their measured lateness/missing rates are therefore NULL. Download time is operational provenance and must not be substituted for event arrival time.

`measurement.monitoring.event_health` accepts a future **real** event export containing `event_id`, `event_timestamp_utc`, and `received_timestamp_utc`, plus optional expected IDs from a completed source manifest. It normalizes parseable timestamps to UTC, counts invalid/negative lags and detects events beyond a configurable allowed delay. Missing-rate computation requires the authoritative expected IDs. It does not estimate missing events from volume changes alone. Supplying expected IDs before a batch is complete will create misleading alerts.

For a production event feed, persist ingestion batch lineage, source acknowledgments and watermarks. Recompute a lookback covering the conversion window plus allowed lateness, and merge on source event ID. Add billing/spend and experiment-assignment contracts before filling the currently unavailable economic metrics. These integrations are extensions, not observed results of this historical run.
