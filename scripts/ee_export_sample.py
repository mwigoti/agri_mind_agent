import os

import ee
import geemap

# Initialize Earth Engine using the configured project when available,
# otherwise falling back to the default authenticated credentials.
gee_project = os.environ.get("AGRIVISION_GEE_PROJECT")
if gee_project:
    ee.Initialize(project=gee_project)
else:
    ee.Initialize()

geojson_path = os.environ.get("SAMPLE_GEOJSON_PATH", "data/sample.geojson")
if os.path.exists(geojson_path):
    ee_object = geemap.geojson_to_ee(geojson_path)
    asset_id = os.environ.get("GEE_ASSET_ID", "users/agrivision/sample_field")
    export_task = ee.batch.Export.table.toAsset(
        collection=ee_object,
        description="GeoJSON Upload",
        assetId=asset_id,
    )
    export_task.start()
    print(f"Export task started for {geojson_path} -> {asset_id}")
else:
    print(f"Sample GeoJSON file not found at: {geojson_path}. Set SAMPLE_GEOJSON_PATH to run.")
