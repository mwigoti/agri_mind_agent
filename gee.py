

import ee
import os

# ---------------------------
# 1. Initialize GEE
# ---------------------------
ee.Initialize()

# ---------------------------
# 2. Convert polygon coordinates to AOI
# ---------------------------
def create_aoi(polygon_coords):
    """
    polygon_coords: list of [lon, lat] coordinates
    returns: ee.Geometry.Polygon
    """
    return ee.Geometry.Polygon([polygon_coords])

# ---------------------------
# 3. Add vegetation indices
# ---------------------------
def add_indices(image):
    """
    Computes NDVI, EVI, NDWI bands
    """
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

    evi = image.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
        {
            'NIR': image.select('B8'),
            'RED': image.select('B4'),
            'BLUE': image.select('B2')
        }
    ).rename('EVI')

    ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')

    return image.addBands([ndvi, evi, ndwi])

# ---------------------------
# 4. Main vegetation analysis function
# ---------------------------
def analyze_vegetation(polygon_coords, start_date, end_date):
    """
    polygon_coords: list of [lon, lat]
    start_date, end_date: strings 'YYYY-MM-DD'
    returns: dict with mean NDVI, EVI, NDWI
    """
    aoi = create_aoi(polygon_coords)

    # Sentinel-2 SR Harmonized collection with metadata filter
    collection = (
        ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
        .map(add_indices)
    )

    # Compute median composite
    composite = collection.median()

    # Reduce to mean over AOI
    stats = composite.select(['NDVI', 'EVI', 'NDWI']).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=10,
        maxPixels=1e9
    )

    return stats.getInfo()

# ---------------------------
# 5. Example usage
# ---------------------------
if __name__ == "__main__":
    # Example polygon (replace with your coordinates)
    polygon = [
        [36.8219, -1.2921],
        [36.8225, -1.2921],
        [36.8225, -1.2928],
        [36.8219, -1.2928],
        [36.8219, -1.2921]
    ]

    # Time window
    start_date = '2025-01-01'
    end_date   = '2025-01-31'

    # Run analysis
    results = analyze_vegetation(
        polygon_coords=polygon,
        start_date=start_date,
        end_date=end_date
    )

    print("Vegetation Indices over AOI (metadata-filtered only):")
    print(results)
