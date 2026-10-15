import ee
ee.Initialize()

aoi = ee.Geometry.Point([35.177686, 0.635520]).buffer(1000)
col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
         .filterBounds(aoi)
         .filterDate('2026-03-26', '2026-05-06')
         .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50)))

print("Scene count:", col.size().getInfo())