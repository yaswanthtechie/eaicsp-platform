FROM apache/airflow:2.10.5-python3.12

USER airflow

# Keep pandas compatible with the Airflow Google/Snowflake providers already
# included in the 2.10.5 image, and add the project's Pandera validation dependency.
RUN pip install --no-cache-dir \
    "pandas==2.1.4" \
    "pandera==0.26.1" \
    "python-dotenv"

USER airflow
