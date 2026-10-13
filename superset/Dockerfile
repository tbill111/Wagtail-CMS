# Image Superset chính thức không kèm driver PostgreSQL -> cài thêm psycopg2.
FROM apache/superset:4.1.2

USER root
RUN pip install --no-cache-dir "psycopg2-binary==2.9.10"
COPY --chown=superset:superset superset_config.py /app/pythonpath/superset_config.py
USER superset
