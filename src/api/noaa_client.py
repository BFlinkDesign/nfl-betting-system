"""
NOAA Weather API Client - Free, No Authentication

NOAA provides free weather data without authentication.
Includes retry with exponential backoff on transient failures.
"""

import logging
from datetime import datetime
from typing import Dict, Tuple

import requests

logger = logging.getLogger(__name__)

try:
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    _noaa_retry = retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
        ),
        reraise=True,
    )
except ImportError:

    def _noaa_retry(fn):
        return fn


class NOAAClient:
    """
    NOAA Weather API Client (Free, No Auth)

    Rate Limits: None specified (be respectful, cache aggressively)
    """

    BASE_URL = "https://api.weather.gov"

    def __init__(self, cache=None):
        self.cache = cache
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "(NFLBettingSystem, contact@example.com)",  # NOAA requires User-Agent
                "Accept": "application/json",
            }
        )

    @_noaa_retry
    def get_forecast_for_location(self, latitude: float, longitude: float) -> Dict:
        """
        Get weather forecast for stadium location.

        Args:
            latitude: Stadium latitude
            longitude: Stadium longitude

        Returns:
            Forecast data
        """
        # Step 1: Get forecast URL from lat/lon
        points_url = f"{self.BASE_URL}/points/{latitude},{longitude}"

        try:
            response = self.session.get(points_url, timeout=10)
            response.raise_for_status()
            points_data = response.json()

            # Extract forecast URL
            forecast_url = points_data["properties"]["forecast"]

            # Step 2: Get actual forecast
            forecast_response = self.session.get(forecast_url, timeout=10)
            forecast_response.raise_for_status()
            return forecast_response.json()

        except Exception as e:
            logger.error(f"NOAA forecast error: {e}")
            return {}

    @_noaa_retry
    def get_hourly_forecast(self, latitude: float, longitude: float) -> Dict:
        """
        Get hourly forecast for stadium location.

        More granular than daily forecast.
        """
        points_url = f"{self.BASE_URL}/points/{latitude},{longitude}"

        try:
            response = self.session.get(points_url, timeout=10)
            response.raise_for_status()
            points_data = response.json()

            # Extract hourly forecast URL
            hourly_url = points_data["properties"]["forecastHourly"]

            # Get hourly forecast
            hourly_response = self.session.get(hourly_url, timeout=10)
            hourly_response.raise_for_status()
            return hourly_response.json()

        except Exception as e:
            logger.error(f"NOAA hourly forecast error: {e}")
            return {}

    @_noaa_retry
    def get_current_conditions(self, latitude: float, longitude: float) -> Dict:
        """
        Get current weather conditions from nearest station.

        Args:
            latitude: Stadium latitude
            longitude: Stadium longitude

        Returns:
            Current conditions
        """
        # Step 1: Get nearest stations
        stations_url = f"{self.BASE_URL}/points/{latitude},{longitude}/stations"

        try:
            response = self.session.get(stations_url, timeout=10)
            response.raise_for_status()
            stations_data = response.json()

            # Get first station
            if "observationStations" in stations_data:
                stations = stations_data["observationStations"]
                if stations:
                    station_url = stations[0]

                    # Get latest observation
                    obs_url = f"{station_url}/observations/latest"
                    obs_response = self.session.get(obs_url, timeout=10)
                    obs_response.raise_for_status()
                    return obs_response.json()

            return {}

        except Exception as e:
            logger.error(f"NOAA current conditions error: {e}")
            return {}

    def get_game_day_forecast(
        self,
        stadium_name: str,
        stadium_coords: Tuple[float, float],
        game_time: datetime,
    ) -> Dict:
        """
        Get weather forecast for specific game.

        Args:
            stadium_name: Stadium name
            stadium_coords: (latitude, longitude)
            game_time: Game kickoff time

        Returns:
            Relevant weather data for game time
        """
        latitude, longitude = stadium_coords

        # Get hourly forecast
        hourly = self.get_hourly_forecast(latitude, longitude)

        if not hourly:
            return {}

        # Find forecast closest to game time
        periods = hourly.get("properties", {}).get("periods", [])

        game_forecast = None
        min_time_diff = float("inf")

        for period in periods:
            try:
                period_time = datetime.fromisoformat(
                    period["startTime"].replace("Z", "+00:00")
                )
                time_diff = abs((period_time - game_time).total_seconds())

                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    game_forecast = period
            except Exception:
                continue

        if game_forecast:
            return {
                "stadium": stadium_name,
                "game_time": game_time.isoformat(),
                "temperature": game_forecast.get("temperature"),
                "temperature_unit": game_forecast.get("temperatureUnit"),
                "wind_speed": game_forecast.get("windSpeed"),
                "wind_direction": game_forecast.get("windDirection"),
                "conditions": game_forecast.get("shortForecast"),
                "details": game_forecast.get("detailedForecast"),
                "precipitation_probability": game_forecast.get(
                    "probabilityOfPrecipitation", {}
                ).get("value"),
            }

        return {}
