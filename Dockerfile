FROM apache/airflow:3.1.7-python3.12
WORKDIR /opt/project
COPY --chown=airflow:root pyproject.toml /opt/project/
COPY --chown=airflow:root src /opt/project/src
COPY --chown=airflow:root sql /opt/project/sql
COPY --chown=airflow:root sources.lock.json /opt/project/sources.lock.json
RUN pip install --no-cache-dir "apache-airflow==3.1.7" ".[cloud,test]"
COPY --chown=airflow:root dags /opt/airflow/dags
COPY --chown=airflow:root tests /opt/project/tests
