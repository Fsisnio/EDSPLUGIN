# EDHS Core API - production-oriented image
FROM python:3.12-slim

WORKDIR /app

# System deps for geopandas / pyreadstat
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY edhs_core/ ./edhs_core/
# Optional: copy .env when building; usually env is set via docker-compose or -e
# COPY .env ./

ENV TEMP_DATA_DIR=/tmp/edhs_core_sessions
ENV ADMIN_BOUNDARIES_ROOT=/opt/edhs/admin_boundaries
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "edhs_core.main:app", "--host", "0.0.0.0", "--port", "8000"]
