"""
ADCC — Weather Tool
====================
Fetches current weather and forecast data using the Open-Meteo API.
Free, no API key required.

API Base: https://api.open-meteo.com/v1/forecast
Docs:     https://open-meteo.com/en/docs

Used by (future):
    - data_collection_agent.py  → fetches weather for active disaster zones
    - severity_agent.py         → uses rainfall/wind to adjust severity score
    - replanning_agent.py       → re-checks weather before resource reallocation

Functions:
    get_current_weather(lat, lon)         → CurrentWeather
    get_forecast(lat, lon, days)          → ForecastData
    get_disaster_weather(lat, lon)        → DisasterWeatherReport (combined)
"""

import time
from datetime import datetime, timezone
from typing import Optional

import requests
from loguru import logger
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds — exponential backoff: 2s, 4s, 8s

# WMO Weather Interpretation Codes → human-readable descriptions
# Source: https://open-meteo.com/en/docs#weathervariables
WMO_WEATHER_CODES: dict[int, str] = {
    0:  "Clear sky",
    1:  "Mainly clear",
    2:  "Partly cloudy",
    3:  "Overcast",
    45: "Foggy",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# Flood risk thresholds (used by severity_agent)
FLOOD_RISK_RAINFALL_MM = 50.0   # mm/hour → high flood risk
CYCLONE_WIND_THRESHOLD = 120.0  # km/h    → cyclone-level winds


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================


class CurrentWeather(BaseModel):
    """Normalized current weather at a point location."""

    latitude: float = Field(..., description="Location latitude (WGS84)")
    longitude: float = Field(..., description="Location longitude (WGS84)")

    # Temperature
    temperature_c: float = Field(..., description="Air temperature (°C) at 2m")
    feels_like_c: Optional[float] = Field(None, description="Apparent temperature (°C)")

    # Precipitation
    rainfall_mm: float = Field(0.0, description="Rainfall in the last hour (mm)")

    # Humidity
    humidity_percent: float = Field(..., description="Relative humidity (%)")

    # Wind
    wind_speed_kmh: float = Field(..., description="Wind speed at 10m (km/h)")
    wind_direction_deg: float = Field(..., description="Wind direction (0–360°)")
    wind_gusts_kmh: Optional[float] = Field(None, description="Wind gusts at 10m (km/h)")

    # Sky
    weather_code: int = Field(..., description="WMO weather interpretation code")
    weather_description: str = Field(..., description="Human-readable weather condition")
    is_day: bool = Field(..., description="True if daytime at location")

    # Risk flags (computed) — used by severity_agent.py
    flood_risk: bool = Field(False, description="True if rainfall ≥ 50mm/hr")
    cyclone_risk: bool = Field(False, description="True if wind ≥ 120km/h")

    # Metadata
    fetched_at: datetime = Field(..., description="UTC timestamp of data fetch")
    source: str = Field("Open-Meteo", description="Data source name")
    source_url: str = Field("https://open-meteo.com", description="API source URL")


class HourlyForecast(BaseModel):
    """Single hourly forecast data point."""

    time: str = Field(..., description="ISO 8601 datetime string (Asia/Kolkata TZ)")
    temperature_c: float
    rainfall_mm: float
    wind_speed_kmh: float
    wind_gusts_kmh: Optional[float] = None
    humidity_percent: float
    weather_code: int
    weather_description: str


class ForecastData(BaseModel):
    """Multi-day hourly weather forecast for a location."""

    latitude: float
    longitude: float
    days_requested: int
    total_hours: int
    hourly: list[HourlyForecast]
    max_rainfall_mm: float = Field(..., description="Peak hourly rainfall in forecast period")
    max_wind_kmh: float = Field(..., description="Peak wind speed in forecast period")
    flood_risk_hours: int = Field(..., description="Hours with rainfall ≥ 50mm in forecast")
    fetched_at: datetime
    source: str = "Open-Meteo"
    source_url: str = "https://open-meteo.com"


class DisasterWeatherReport(BaseModel):
    """Combined current + forecast report for disaster zone assessment."""

    location_label: Optional[str] = Field(None, description="Human label, e.g. 'Mumbai Flood Zone'")
    latitude: float
    longitude: float
    current: CurrentWeather
    forecast_7day: ForecastData
    risk_summary: str = Field(..., description="Computed risk narrative for agents")
    fetched_at: datetime


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================


def _get_with_retry(url: str, params: dict) -> dict:
    """
    HTTP GET with exponential backoff retry (up to MAX_RETRIES attempts).

    Args:
        url: API endpoint URL
        params: Query parameters dict

    Returns:
        Parsed JSON response dict

    Raises:
        RuntimeError: After all retries are exhausted
        requests.HTTPError: On 4xx/5xx HTTP errors (no retry)
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug(f"[WeatherTool] GET attempt {attempt}/{MAX_RETRIES} → {url}")
            response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            # 4xx/5xx — don't retry, fail immediately
            logger.error(f"[WeatherTool] HTTP {e.response.status_code} error: {e}")
            raise

        except requests.exceptions.Timeout:
            logger.warning(f"[WeatherTool] Request timeout on attempt {attempt}")

        except requests.exceptions.ConnectionError:
            logger.warning(f"[WeatherTool] Connection error on attempt {attempt}")

        except Exception as e:
            logger.error(f"[WeatherTool] Unexpected error: {e}")
            raise

        if attempt < MAX_RETRIES:
            wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))  # 2s → 4s → 8s
            logger.info(f"[WeatherTool] Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"[WeatherTool] All {MAX_RETRIES} attempts failed for {url}")


def _compute_risk_summary(current: CurrentWeather, forecast: ForecastData) -> str:
    """Generates a human-readable risk narrative for AI agents."""
    risks = []

    if current.flood_risk:
        risks.append(f"CRITICAL: Active flooding — {current.rainfall_mm}mm/hr rainfall")
    if current.cyclone_risk:
        risks.append(f"CRITICAL: Cyclone-level winds — {current.wind_speed_kmh}km/h")
    if forecast.flood_risk_hours > 0:
        risks.append(f"WARNING: {forecast.flood_risk_hours} high-risk rainfall hours in next 7 days")
    if forecast.max_wind_kmh >= CYCLONE_WIND_THRESHOLD:
        risks.append(f"WARNING: Peak winds of {forecast.max_wind_kmh}km/h forecast")

    if not risks:
        return "No immediate weather-based disaster risk detected."

    return " | ".join(risks)


# ===========================================================================
# PUBLIC FUNCTIONS
# ===========================================================================


def get_current_weather(
    latitude: float,
    longitude: float,
) -> CurrentWeather:
    """
    Fetches current weather conditions at a given location.

    Args:
        latitude:  WGS84 latitude  (e.g. 19.0760 for Mumbai)
        longitude: WGS84 longitude (e.g. 72.8777 for Mumbai)

    Returns:
        CurrentWeather: Normalized, validated weather data

    Raises:
        RuntimeError: If API call fails after all retries
        ValueError:   If API returns unexpected data format

    Example:
        >>> weather = get_current_weather(19.0760, 72.8777)
        >>> print(weather.temperature_c, weather.rainfall_mm)
    """
    logger.info(f"[WeatherTool] Fetching current weather for ({latitude:.4f}, {longitude:.4f})")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": [
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "rain",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "weather_code",
            "is_day",
        ],
        "timezone": "Asia/Kolkata",
    }

    try:
        data = _get_with_retry(BASE_URL, params)
        c = data["current"]

        rainfall_mm = c.get("rain", 0.0) or 0.0
        wind_kmh = c.get("wind_speed_10m", 0.0) or 0.0
        weather_code = c.get("weather_code", 0)

        result = CurrentWeather(
            latitude=data["latitude"],
            longitude=data["longitude"],
            temperature_c=c["temperature_2m"],
            feels_like_c=c.get("apparent_temperature"),
            rainfall_mm=rainfall_mm,
            humidity_percent=c["relative_humidity_2m"],
            wind_speed_kmh=wind_kmh,
            wind_direction_deg=c.get("wind_direction_10m", 0.0),
            wind_gusts_kmh=c.get("wind_gusts_10m"),
            weather_code=weather_code,
            weather_description=WMO_WEATHER_CODES.get(weather_code, "Unknown"),
            is_day=bool(c.get("is_day", 1)),
            flood_risk=rainfall_mm >= FLOOD_RISK_RAINFALL_MM,
            cyclone_risk=wind_kmh >= CYCLONE_WIND_THRESHOLD,
            fetched_at=datetime.now(timezone.utc),
        )

        logger.success(
            f"[WeatherTool] Current: {result.temperature_c}°C | "
            f"Rain={result.rainfall_mm}mm | Wind={result.wind_speed_kmh}km/h | "
            f"FloodRisk={result.flood_risk}"
        )
        return result

    except KeyError as e:
        msg = f"[WeatherTool] Missing field in Open-Meteo response: {e}"
        logger.error(msg)
        raise ValueError(msg)


def get_forecast(
    latitude: float,
    longitude: float,
    days: int = 7,
) -> ForecastData:
    """
    Fetches hourly weather forecast for the next N days.

    Args:
        latitude:  WGS84 latitude
        longitude: WGS84 longitude
        days:      Number of forecast days (1–16). Default: 7

    Returns:
        ForecastData: Full hourly forecast with risk computed fields

    Raises:
        ValueError:  If days is out of range
        RuntimeError: If API call fails
    """
    if not 1 <= days <= 16:
        raise ValueError(f"[WeatherTool] 'days' must be 1–16, got {days}")

    logger.info(f"[WeatherTool] Fetching {days}-day forecast for ({latitude:.4f}, {longitude:.4f})")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": [
            "temperature_2m",
            "rain",
            "wind_speed_10m",
            "wind_gusts_10m",
            "relative_humidity_2m",
            "weather_code",
        ],
        "forecast_days": days,
        "timezone": "Asia/Kolkata",
    }

    try:
        data = _get_with_retry(BASE_URL, params)
        hourly = data["hourly"]
        times = hourly["time"]

        hours: list[HourlyForecast] = []
        for i in range(len(times)):
            wc = hourly["weather_code"][i] if hourly.get("weather_code") else 0
            rainfall = hourly["rain"][i] or 0.0
            wind = hourly["wind_speed_10m"][i] or 0.0
            hours.append(HourlyForecast(
                time=times[i],
                temperature_c=hourly["temperature_2m"][i],
                rainfall_mm=rainfall,
                wind_speed_kmh=wind,
                wind_gusts_kmh=hourly["wind_gusts_10m"][i] if hourly.get("wind_gusts_10m") else None,
                humidity_percent=hourly["relative_humidity_2m"][i],
                weather_code=wc,
                weather_description=WMO_WEATHER_CODES.get(wc, "Unknown"),
            ))

        rainfalls = [h.rainfall_mm for h in hours]
        winds = [h.wind_speed_kmh for h in hours]
        flood_risk_hours = sum(1 for r in rainfalls if r >= FLOOD_RISK_RAINFALL_MM)

        result = ForecastData(
            latitude=data["latitude"],
            longitude=data["longitude"],
            days_requested=days,
            total_hours=len(hours),
            hourly=hours,
            max_rainfall_mm=max(rainfalls) if rainfalls else 0.0,
            max_wind_kmh=max(winds) if winds else 0.0,
            flood_risk_hours=flood_risk_hours,
            fetched_at=datetime.now(timezone.utc),
        )

        logger.success(
            f"[WeatherTool] Forecast: {result.total_hours} hours | "
            f"MaxRain={result.max_rainfall_mm}mm | MaxWind={result.max_wind_kmh}km/h | "
            f"FloodRiskHours={result.flood_risk_hours}"
        )
        return result

    except KeyError as e:
        msg = f"[WeatherTool] Missing field in Open-Meteo forecast response: {e}"
        logger.error(msg)
        raise ValueError(msg)


def get_disaster_weather(
    latitude: float,
    longitude: float,
    location_label: Optional[str] = None,
) -> DisasterWeatherReport:
    """
    Fetches combined current + 7-day forecast for a disaster zone.
    Designed as a single-call input for AI agents.

    Args:
        latitude:       Disaster zone latitude
        longitude:      Disaster zone longitude
        location_label: Optional human label (e.g. 'Mumbai Flood Zone')

    Returns:
        DisasterWeatherReport: Full report with risk_summary for agents

    Example:
        >>> report = get_disaster_weather(19.0760, 72.8777, "Mumbai Flood Zone")
        >>> print(report.risk_summary)
    """
    logger.info(f"[WeatherTool] Full disaster weather report for '{location_label or f'({latitude}, {longitude})'}' ")

    current = get_current_weather(latitude, longitude)
    forecast = get_forecast(latitude, longitude, days=7)
    risk_summary = _compute_risk_summary(current, forecast)

    report = DisasterWeatherReport(
        location_label=location_label,
        latitude=latitude,
        longitude=longitude,
        current=current,
        forecast_7day=forecast,
        risk_summary=risk_summary,
        fetched_at=datetime.now(timezone.utc),
    )

    logger.success(f"[WeatherTool] Report ready: {report.risk_summary}")
    return report
