import os

import ee
import geemap

# Initialize Earth Engine using the configured project when available,
# otherwise falling back to the default authenticated credentials.
gee_project = os.environ.get('AGRIVISION_GEE_PROJECT')
if gee_project:
    ee.Initialize(project=gee_project)
else:
    ee.Initialize()

# Load GeoJSON file into an EE object
ee_object = geemap.geojson_to_ee('/home/mwoha/Documents/Mathare_IGAD/Mathare.geojson')

# Export to GEE Assets
export_task = ee.batch.Export.table.toAsset(
    collection=ee_object,
    description='GeoJSON Upload',
    assetId='users/henrymwoha02/Mathare'
)
export_task.start()   