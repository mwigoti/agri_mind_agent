FROM python:3.12-slim

# Install system geospatial libraries (GDAL, GEOS, PROJ) and build essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    binutils \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
COPY agentic_layer_2/requirements.txt requirements-agent.txt
RUN pip install --no-cache-dir -r requirements.txt -r requirements-agent.txt

# Copy application source
COPY . .

# Environment defaults
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

EXPOSE 8000 8001

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

