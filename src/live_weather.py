"""
live_weather.py
===============
Real-time weather fetcher for Sentin-AI using OpenWeatherMap API.

Responsibilities:
  - Fetch live meteorological data for Bengaluru (or custom lat/lon)
  - Convert OpenWeatherMap API fields to Sentin-AI's 6 weather features:
      1. temperature_2m_c             (°C)
      2. relative_humidity_pct        (%)
      3. precipitation_imerg_mm       (mm/day)
      4. dew_frost_point_c            (°C, Magnus formula approximation)
      5. wind_speed_10m_ms            (m/s)
      6. all_sky_insolation_clearness (0.0 – 1.0, estimated from cloudiness)

Usage:
  python src/live_weather.py
"""

import os
import requests
import math
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
TARGET_LAT = float(os.getenv("TARGET_LAT", 12.98))
TARGET_LON = float(os.getenv("TARGET_LON", 77.58))


def calculate_dew_point(temp_c: float, humidity_pct: float) -> float:
    """
    Magnus-Tetens formula approximation for dew point calculation.
    """
    a = 17.27
    b = 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(max(humidity_pct, 1.0) / 100.0)
    dew_point = (b * alpha) / (a - alpha)
    return round(dew_point, 2)


class LiveWeatherFetcher:
    """Fetches real-time weather from OpenWeatherMap API."""

    def __init__(self, api_key: str = OPENWEATHERMAP_API_KEY, lat: float = TARGET_LAT, lon: float = TARGET_LON):
        self.api_key = api_key
        self.lat = lat
        self.lon = lon

        if not self.api_key:
            raise ValueError("OPENWEATHERMAP_API_KEY not found in environment or .env file.")

    def fetch_current_weather(self) -> dict:
        """
        Calls OpenWeatherMap API and returns parsed Sentin-AI weather feature dictionary.
        """
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={self.lat}&lon={self.lon}&appid={self.api_key}&units=metric"
        )

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        main_data = data.get("main", {})
        wind_data = data.get("wind", {})
        cloud_data = data.get("clouds", {})
        rain_data = data.get("rain", {})

        temp = float(main_data.get("temp", 25.0))
        humidity = float(main_data.get("humidity", 70.0))
        wind_speed = float(wind_data.get("speed", 2.5))
        clouds = float(cloud_data.get("all", 50.0))

        # Rain in last 1h or 3h converted to 24h rate estimate
        rain_1h = rain_data.get("1h", 0.0)
        rain_3h = rain_data.get("3h", 0.0)
        if rain_1h > 0:
            rain_mm = rain_1h * 24.0   # daily rate proxy
        elif rain_3h > 0:
            rain_mm = (rain_3h / 3.0) * 24.0
        else:
            rain_mm = 0.0

        dew_point = calculate_dew_point(temp, humidity)

        # Insolation clearness index proxy (1.0 = clear sky, 0.0 = total overcast)
        insolation = round(max(0.0, min(1.0, 1.0 - (clouds / 100.0) * 0.75)), 2)

        weather_dict = {
            "temperature_2m_c": round(temp, 2),
            "relative_humidity_pct": round(humidity, 1),
            "precipitation_imerg_mm": round(rain_mm, 2),
            "dew_frost_point_c": dew_point,
            "wind_speed_10m_ms": round(wind_speed, 2),
            "all_sky_insolation_clearness": insolation,
            "city_name": data.get("name", "Bengaluru"),
            "description": data.get("weather", [{}])[0].get("description", "clear sky"),
        }

        return weather_dict


def main():
    fetcher = LiveWeatherFetcher()
    data = fetcher.fetch_current_weather()
    print("=" * 50)
    print(f"  Live Weather Data — {data['city_name']} ({TARGET_LAT}°N, {TARGET_LON}°E)")
    print("=" * 50)
    print(f"  Description:  {data['description'].title()}")
    print(f"  Temperature:  {data['temperature_2m_c']} °C")
    print(f"  Humidity:     {data['relative_humidity_pct']} %")
    print(f"  Rain Rate:    {data['precipitation_imerg_mm']} mm/day")
    print(f"  Dew Point:    {data['dew_frost_point_c']} °C")
    print(f"  Wind Speed:   {data['wind_speed_10m_ms']} m/s")
    print(f"  Insolation:   {data['all_sky_insolation_clearness']} (0-1 index)")
    print("=" * 50)


if __name__ == "__main__":
    main()
