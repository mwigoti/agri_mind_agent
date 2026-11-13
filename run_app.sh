#!/bin/bash
cd /home/mwoha/Documents/Agri_vision_agrimind_agent
source venv/bin/activate

echo "Refreshing live field analyses from GEE / ISRIC / NASA SMAP / weather sources..."
python manage.py refresh_stale_field_analysis --max-age-days 0 --limit 50 || true

echo "Warming dashboard summaries from the latest stored analysis bundle..."
python manage.py warmup_dashboard_data

echo "Starting Django app on port 8011..."
python manage.py runserver 0.0.0.0:8011