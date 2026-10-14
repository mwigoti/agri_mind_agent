 #weather_utils.py
def get_weather_suitability_score(weather_data, activity_type):
    """Calculate weather suitability score for activities"""
    scores = {
        'planting': _planting_weather_score,
        'harvest': _harvest_weather_score,
        'irrigation': _irrigation_weather_score,
        'maintenance': _maintenance_weather_score,
        'fertilizing': _fertilizing_weather_score,
        'pest_control': _pest_control_weather_score,
    }
    
    score_func = scores.get(activity_type, lambda x: 0.5)
    return score_func(weather_data)

def _planting_weather_score(weather):
    """Calculate planting suitability score"""
    score = 1.0
    
    # Temperature check (18-25°C optimal)
    temp = weather.get('temperature', 20)
    if temp < 10 or temp > 35:
        score *= 0.2
    elif temp < 15 or temp > 30:
        score *= 0.6
    elif temp < 18 or temp > 25:
        score *= 0.8
    
    # Precipitation check (light rain good, heavy rain bad)
    rain = weather.get('precipitation', 0)
    if rain > 20:
        score *= 0.3
    elif rain > 10:
        score *= 0.7
    elif 2 <= rain <= 5:
        score *= 1.1  # Light rain is good
    
    # Wind check (strong winds bad for planting)
    wind = weather.get('wind_speed', 0)
    if wind > 25:
        score *= 0.4
    elif wind > 15:
        score *= 0.7
    
    return min(1.0, score)

def _harvest_weather_score(weather):
    """Calculate harvest suitability score"""
    score = 1.0
    
    # Dry conditions preferred
    rain = weather.get('precipitation', 0)
    if rain > 5:
        score *= 0.2
    elif rain > 1:
        score *= 0.6
    
    # Moderate winds okay
    wind = weather.get('wind_speed', 0)
    if wind > 30:
        score *= 0.3
    elif wind > 20:
        score *= 0.7
    
    return min(1.0, score)

def _irrigation_weather_score(weather):
    """Calculate irrigation suitability score"""
    score = 1.0
    
    # Low humidity indicates need for irrigation
    humidity = weather.get('humidity', 50)
    if humidity < 40:
        score *= 1.2  # Higher score when dry
    elif humidity > 80:
        score *= 0.3  # Lower score when already wet
    
    # Recent precipitation affects need
    rain = weather.get('precipitation', 0)
    if rain > 10:
        score *= 0.2  # Less need if recent rain
    
    return min(1.0, score)

def _maintenance_weather_score(weather):
    """Calculate maintenance activity suitability score"""
    score = 1.0
    
    # Avoid during rain
    rain = weather.get('precipitation', 0)
    if rain > 2:
        score *= 0.3
    
    # Avoid during extreme temperatures
    temp = weather.get('temperature', 20)
    if temp < 5 or temp > 35:
        score *= 0.4
    
    return min(1.0, score)

def _fertilizing_weather_score(weather):
    """Calculate fertilizing suitability score"""
    score = 1.0
    
    # Light rain after fertilizing is good
    rain = weather.get('precipitation', 0)
    if rain > 15:
        score *= 0.3  # Too much rain washes away fertilizer
    elif 5 <= rain <= 10:
        score *= 1.1  # Light rain helps absorption
    
    # Avoid windy conditions
    wind = weather.get('wind_speed', 0)
    if wind > 20:
        score *= 0.4
    
    return min(1.0, score)

def _pest_control_weather_score(weather):
    """Calculate pest control suitability score"""
    score = 1.0
    
    # Avoid rain (washes away treatments)
    rain = weather.get('precipitation', 0)
    if rain > 2:
        score *= 0.2
    
    # Avoid strong winds
    wind = weather.get('wind_speed', 0)
    if wind > 15:
        score *= 0.3
    elif wind > 10:
        score *= 0.6
    
    # Early morning or late evening preferred (temperature consideration)
    temp = weather.get('temperature', 20)
    if temp > 30:
        score *= 0.6  # High temperature reduces effectiveness
    
    return min(1.0, score)