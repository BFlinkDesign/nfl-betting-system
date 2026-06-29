# Quick API Reference - NFL Betting System

**TL;DR**: All APIs verified working. Copy-paste code examples below.

---

## 1-Minute Setup

```bash
# Install packages
pip install requests pandas nfl_data_py

# Test all APIs
python agents/api_integrations.py
```

---

## Weather (NOAA) - FREE ✅

```python
from agents.api_integrations import NOAAWeatherAPI

api = NOAAWeatherAPI()
forecast = api.get_forecast_for_stadium(39.0489, -94.4839)  # Arrowhead
print(f"{forecast['temperature']}°F, Wind: {forecast['wind_speed']}")
```

---

## Scores (ESPN) - FREE ✅

```python
from agents.api_integrations import ESPNAPI

api = ESPNAPI()
scoreboard = api.get_scoreboard(2024, week=12)
for game in scoreboard['events']:
    print(game['name'])  # "Team A at Team B"
```

---

## Data (nflverse) - FREE ✅

```python
from agents.api_integrations import NFLVerseAPI

api = NFLVerseAPI()
pbp = api.get_play_by_play([2024])  # Play-by-play with EPA
schedules = api.get_schedules([2024])
injuries = api.get_injuries([2024])
```

---

## Sentiment (Reddit) - FREE ✅

```python
from agents.api_integrations import RedditAPI

api = RedditAPI()
posts = api.get_subreddit_posts('nfl', limit=25)
for post in posts:
    print(post['data']['title'])
```

---

## Odds (The Odds API) - NEEDS KEY ⚠️

**Setup**: Sign up at https://the-odds-api.com/ (500 free requests/month)

```python
from agents.api_integrations import TheOddsAPI

api = TheOddsAPI(api_key='your_key_here')
odds = api.get_nfl_odds()
for game in odds:
    print(f"{game['home_team']} vs {game['away_team']}")
    for bookmaker in game['bookmakers']:
        print(f"  {bookmaker['title']}")
```

---

## Complete Example

```python
from agents.api_integrations import NOAAWeatherAPI, ESPNAPI, NFLVerseAPI

# Get games
espn = ESPNAPI()
games = espn.get_scoreboard(2024)['events']

# Get weather for game
noaa = NOAAWeatherAPI()
forecast = noaa.get_forecast_for_stadium(39.0489, -94.4839)

# Get historical data
nflverse = NFLVerseAPI()
pbp = nflverse.get_play_by_play([2024])

print(f"Games: {len(games)}")
print(f"Weather: {forecast['temperature']}°F")
print(f"Plays: {len(pbp)}")
```

---

**Full Documentation**: See `API_COMPLETE_GUIDE.md`  
**Code File**: `agents/api_integrations.py`

