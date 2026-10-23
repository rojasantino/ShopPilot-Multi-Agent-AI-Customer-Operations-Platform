FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
# Set to requirements-ml.txt to bake real sentence-transformer embeddings into the image.
ARG REQUIREMENTS=requirements.txt
COPY ${REQUIREMENTS} requirements.txt* ./
RUN pip install --no-cache-dir -r ${REQUIREMENTS}
COPY app ./app
COPY data ./data
RUN useradd --create-home appuser && chown -R appuser /srv
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
