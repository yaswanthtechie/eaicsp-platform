FROM apache/spark:3.5.3-python3
USER root
RUN pip install --no-cache-dir pyspark==3.5.3 psycopg2-binary
WORKDIR /opt/airflow
COPY spark /opt/airflow/spark
ENV PYTHONPATH=/opt/airflow
USER spark
