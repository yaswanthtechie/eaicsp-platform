FROM apache/spark:3.5.3-python3
USER root
RUN pip install --no-cache-dir pyspark==3.5.3 psycopg2-binary pandas
RUN curl -fsSL -o /opt/spark/jars/postgresql-42.7.4.jar https://jdbc.postgresql.org/download/postgresql-42.7.4.jar
WORKDIR /opt/airflow
COPY spark /opt/airflow/spark
ENV PYTHONPATH=/opt/airflow:/opt/airflow/etl/src
