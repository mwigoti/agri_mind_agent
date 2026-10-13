import os
import cdsapi

def configure_cds_api():
    try:
        cds_url = os.environ.get('CDS_URL')
        cds_key = os.environ.get('CDS_KEY')

        if not cds_url or not cds_key:
            raise ValueError("CDS API and KEY must be configured")
        
        cds_config_path = os.path.expanduser('~/.cdsapirc')
        with open(cds_config_path, 'w') as f:
            f.write(f'url: {cds_url}\n')
            f.write(f'key: {cds_key}\n')

        os.environ['CDSAPI_RC'] = cds_config_path
        return True
    except Exception as e:
        print(f"CDS API consig error: {e}")
        return False
    
    configure_cds_api()