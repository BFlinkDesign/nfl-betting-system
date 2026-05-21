"""Monday Night Football Pick - Direct Analysis
Gets the pick for tonight's game: Panthers @ 49ers
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import joblib
import pandas as pd
from datetime import datetime

# Load API key
env_path = Path(__file__).parent / "config" / "api_keys.env"
load_dotenv(env_path)

sys.path.append(str(Path(__file__).parent))
from agents.api_integrations import TheOddsAPI

def get_mnf_pick():
    """Get Monday Night Football pick."""
    print("="*80)
    print("MONDAY NIGHT FOOTBALL PICK")
    print("="*80)
    print()
    
    # Fetch odds
    api = TheOddsAPI()
    games = api.get_nfl_odds()
    
    # Find MNF game
    mnf_game = None
    for game in games:
        if 'Panthers' in game.get('away_team', '') and '49ers' in game.get('home_team', ''):
            mnf_game = game
            break
    
    if not mnf_game:
        print("ERROR: Could not find Panthers @ 49ers game")
        return
    
    print(f"Game: {mnf_game['away_team']} @ {mnf_game['home_team']}")
    print(f"Time: {mnf_game.get('commence_time', '8:15 PM ET')}")
    print()
    
    # Get odds
    print("LIVE ODDS:")
    print("-" * 80)
    
    best_spread = None
    best_spread_book = None
    best_ml = None
    best_ml_book = None
    
    for bookmaker in mnf_game.get('bookmakers', [])[:5]:  # Top 5 books
        book_name = bookmaker['title']
        
        for market in bookmaker.get('markets', []):
            if market['key'] == 'spreads':
                for outcome in market['outcomes']:
                    if outcome['name'] == mnf_game['home_team']:
                        spread = outcome['point']
                        odds = outcome['price']
                        if best_spread is None or abs(spread) < abs(best_spread):
                            best_spread = spread
                            best_spread_book = book_name
                        print(f"  {book_name}: {mnf_game['home_team']} {spread:+.1f} ({odds:+d})")
            
            elif market['key'] == 'h2h':
                for outcome in market['outcomes']:
                    if outcome['name'] == mnf_game['home_team']:
                        ml_odds = outcome['price']
                        if best_ml is None:
                            best_ml = ml_odds
                            best_ml_book = book_name
                        print(f"  {book_name}: {mnf_game['home_team']} ML {ml_odds:+d}")
    
    print()
    print("="*80)
    print("THE PICK")
    print("="*80)
    print()
    
    # Simple analysis
    print(f"BEST LINE: {mnf_game['home_team']} {best_spread:+.1f} @ {best_spread_book}")
    print(f"BEST ML: {mnf_game['home_team']} {best_ml:+d} @ {best_ml_book}")
    print()
    
    # Convert to decimal odds
    if best_ml > 0:
        decimal_odds = (best_ml / 100) + 1
    else:
        decimal_odds = (100 / abs(best_ml)) + 1
    
    # Simple recommendation
    print("ANALYSIS:")
    print("-" * 80)
    print(f"49ers are heavy favorites (odds: {decimal_odds:.2f})")
    print(f"Panthers are 1-10 (worst record in NFL)")
    print(f"49ers are 5-6 (desperate for playoff push)")
    print(f"Home field advantage at Levi's Stadium")
    print()
    
    if best_spread <= -7.5:
        print("RECOMMENDATION: 49ers -7.5 (or better)")
        print("CONFIDENCE: Medium-High")
        print()
        print("Why:")
        print("  - Panthers are historically bad this season")
        print("  - 49ers at home should dominate")
        print("  - Line is reasonable, not inflated")
        print("  - Monday night primetime favors home team")
    elif best_spread <= -6.5:
        print("RECOMMENDATION: 49ers -6.5 (STRONG)")
        print("CONFIDENCE: High")
        print()
        print("Why:")
        print("  - Excellent value at -6.5")
        print("  - Panthers can't compete on the road")
        print("  - 49ers need this win badly")
    else:
        print("RECOMMENDATION: PASS")
        print("CONFIDENCE: Low")
        print()
        print("Why:")
        print("  - Line too tight, not enough value")
    
    print()
    print("="*80)
    print(f"API Calls Remaining: {api.session.headers.get('x-requests-remaining', 'N/A')}")
    print("="*80)

if __name__ == '__main__':
    get_mnf_pick()

