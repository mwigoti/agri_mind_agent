import requests
from typing import Optional, Dict
import pandas as pd

def get_soilgrid_data() -> Optional[pd.DataFrame]:
    """Fetch soil data from SoilGrids API for specified properties and depths."""
    url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    params = {
        "lon": 37,
        "lat": 0.7,
        "property": ["bdod", "cec", "cfvo", "clay", "nitrogen", "ocd", "ocs", "phh2o", "sand", "silt", "soc", "wv0010", "wv0033", "wv1500"],
        "depth": ["0-5cm", "0-30cm", "5-15cm", "15-30cm", "30-60cm"],
        "value": "mean"
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        soil_data = {}
        properties = data['properties']['layers']
        for prop in properties:
            soil_data[prop['name']] = prop['depths'][0]['values']['mean']
            
        return pd.DataFrame([soil_data])
        
    except requests.RequestException as e:
        print(f"SoilGrids API Error: {e}")
        return pd.DataFrame()

# Execute directly
df = get_soilgrid_data()
print(df)