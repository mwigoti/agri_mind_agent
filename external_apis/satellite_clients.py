import requests
from django.conf import settings
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class SatelliteDataService:
    """Satellite and drone data service orchestrator"""
    
    def __init__(self):
        self.providers = {
            'planet': PlanetClient(),
            'sentinel': SentinelHubClient(),
        }
        self.default_provider = 'sentinel'
    
    def get_ndvi_data(self, location, date_range, provider=None):
        """Get NDVI data for location and date range"""
        if provider is None:
            provider = self.default_provider
        
        try:
            client = self.providers[provider]
            return client.get_ndvi_data(location, date_range)
        except Exception as e:
            logger.error(f"NDVI data retrieval failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_field_imagery(self, field_boundary, date, provider=None):
        """Get satellite imagery for field"""
        if provider is None:
            provider = self.default_provider
        
        try:
            client = self.providers[provider]
            return client.get_field_imagery(field_boundary, date)
        except Exception as e:
            logger.error(f"Field imagery retrieval failed: {e}")
            return {'success': False, 'error': str(e)}

class PlanetClient:
    """Planet Labs satellite data client"""
    
    def __init__(self):
        self.api_key = settings.WEATHER_API_SETTINGS.get('PLANET_API_KEY', '')
        self.base_url = "https://api.planet.com/data/v1"
    
    def get_ndvi_data(self, location, date_range):
        """Get NDVI data from Planet"""
        # This is a simplified implementation
        # Real implementation would use Planet's Analytics API
        
        headers = {
            'Authorization': f'api-key {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # Search for imagery
        search_request = {
            "item_types": ["PSScene"],
            "filter": {
                "type": "AndFilter",
                "config": [
                    {
                        "type": "GeometryFilter",
                        "field_name": "geometry",
                        "config": {
                            "type": "Point",
                            "coordinates": [location.x, location.y]
                        }
                    },
                    {
                        "type": "DateRangeFilter",
                        "field_name": "acquired",
                        "config": {
                            "gte": date_range['start'].isoformat(),
                            "lte": date_range['end'].isoformat()
                        }
                    }
                ]
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/quick-search",
                json=search_request,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'imagery_count': len(response.json()['features']),
                    'data': response.json()
                }
            else:
                return {'success': False, 'error': f"Planet API error: {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_field_imagery(self, field_boundary, date):
        """Get field imagery from Planet"""
        # Implementation would download and process imagery
        return {'success': True, 'message': 'Field imagery retrieval not implemented yet'}

class SentinelHubClient:
    """Sentinel Hub satellite data client"""
    
    def __init__(self):
        self.client_id = getattr(settings, 'SENTINEL_HUB_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'SENTINEL_HUB_CLIENT_SECRET', '')
        self.base_url = "https://services.sentinel-hub.com"
    
    def _get_access_token(self):
        """Get OAuth access token"""
        token_url = f"{self.base_url}/oauth/token"
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            return response.json()['access_token']
        else:
            raise Exception(f"Token acquisition failed: {response.status_code}")
    
    def get_ndvi_data(self, location, date_range):
        """Get NDVI data from Sentinel Hub"""
        try:
            token = self._get_access_token()
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Simplified NDVI request
            evalscript = """
            //VERSION=3
            function setup() {
                return {
                    input: ["B04", "B08"],
                    output: { bands: 1 }
                };
            }
            
            function evaluatePixel(sample) {
                let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                return [ndvi];
            }
            """
            
            request_payload = {
                "input": {
                    "bounds": {
                        "bbox": [
                            location.x - 0.01, location.y - 0.01,
                            location.x + 0.01, location.y + 0.01
                        ]
                    },
                    "data": [
                        {
                            "type": "sentinel-2-l2a",
                            "dataFilter": {
                                "timeRange": {
                                    "from": date_range['start'].isoformat() + "Z",
                                    "to": date_range['end'].isoformat() + "Z"
                                }
                            }
                        }
                    ]
                },
                "output": {
                    "width": 256,
                    "height": 256
                },
                "evalscript": evalscript
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/process",
                json=request_payload,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'ndvi_data': response.content,  # Binary image data
                    'content_type': response.headers.get('content-type')
                }
            else:
                return {'success': False, 'error': f"Sentinel Hub error: {response.status_code}"}
                
        except Exception as e:
            return {'success': False}
        