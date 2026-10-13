import requests
from datetime import datetime, timedelta

def get_weather_predictions(latitude, longitude, days=7):
    """
    Retrieve detailed weather predictions from Open-Meteo
    
    Args:
        latitude (float): Latitude of the location
        longitude (float): Longitude of the location
        days (int): Number of days to forecast (max 7)
    
    Returns:
        dict: Comprehensive weather predictions
    """
    base_url = "https://api.open-meteo.com/v1/forecast"
    
    # Comprehensive prediction parameters
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation_probability",
            "wind_speed_10m",
            "wind_direction_10m",
            "weathercode"
        ],
        "daily": [
            "weathercode",
            "temperature_2m_max",
            "temperature_2m_min",
            "sunrise",
            "sunset",
            "precipitation_probability_max",
            "uv_index_max"
        ],
        "forecast_days": days,
        "timezone": "auto"
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        return response.json()
    
    except requests.RequestException as e:
        print(f"Error fetching weather predictions: {e}")
        return None

def interpret_weather_code(code):
    """
    Interpret Open-Meteo weather codes
    
    Args:
        code (int): Weather code from Open-Meteo
    
    Returns:
        str: Human-readable weather description
    """
    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with light hail",
        99: "Thunderstorm with heavy hail"
    }
    return weather_codes.get(code, "Unknown weather condition")

def format_weather_predictions(predictions):
    """
    Format and print weather predictions in a readable format
    
    Args:
        predictions (dict): Weather predictions from Open-Meteo
    """
    if not predictions:
        print("No predictions available.")
        return
    
    print("\n===== 7-Day Weather Predictions =====")
    
    # Daily predictions
    for i in range(len(predictions['daily']['time'])):
        date = predictions['daily']['time'][i]
        max_temp = predictions['daily']['temperature_2m_max'][i]
        min_temp = predictions['daily']['temperature_2m_min'][i]
        weather_code = predictions['daily']['weathercode'][i]
        precip_prob = predictions['daily']['precipitation_probability_max'][i]
        uv_index = predictions['daily']['uv_index_max'][i]
        
        print(f"\nDate: {date}")
        print(f"Weather: {interpret_weather_code(weather_code)}")
        print(f"Max Temperature: {max_temp}°C")
        print(f"Min Temperature: {min_temp}°C")
        print(f"Precipitation Probability: {precip_prob}%")
        print(f"UV Index: {uv_index}")

def main():
    # Example coordinates (New York City)
    latitude = 40.7128
    longitude = -74.0060
    
    # Get and format weather predictions
    predictions = get_weather_predictions(latitude, longitude)
    
    if predictions:
        format_weather_predictions(predictions)

if __name__ == "__main__":
    main()