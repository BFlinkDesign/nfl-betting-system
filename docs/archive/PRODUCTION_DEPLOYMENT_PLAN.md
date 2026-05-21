# 🚀 PRODUCTION DEPLOYMENT PLAN - AUTOMATED BET ALERTS

**Date**: November 24, 2025  
**Status**: 📋 **PLANNING PHASE**  
**Goal**: Automated bet recommendations 1 hour before every NFL game

---

## 🎯 **SYSTEM REQUIREMENTS**

### **What You Need:**
1. ✅ **Automated data updates** - Fresh data before every game
2. ✅ **Live NFL schedule** - Know when games are (Thu/Sun/Mon + holidays)
3. ✅ **Model predictions** - Apply discovered edges to upcoming games
4. ✅ **Live odds** - Current betting lines from sportsbooks
5. ✅ **Parlay generation** - Smart parlay combinations
6. ✅ **Notifications** - Alerts 1 hour before kickoff
7. ✅ **Automation** - Runs without your intervention

---

## 🏗️ **COMPLETE WORKFLOW**

### **PHASE 1: PRE-GAME DATA PIPELINE** (Runs Daily)

```
┌─────────────────────────────────────────────────────────────┐
│  DAILY AT 6 AM (Every Day During NFL Season)                │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Download Latest NFL Data                           │
│  ─────────────────────────────────────────────────────────  │
│  Sources:                                                    │
│  - nflverse: Latest stats, injuries, rosters                │
│  - ESPN API: Updated schedules, team records                │
│  - Weather API: Game day forecasts                          │
│                                                              │
│  Output: Updated features for upcoming games                │
│  File: data/processed/upcoming_games.parquet                │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Get Today's NFL Schedule                           │
│  ─────────────────────────────────────────────────────────  │
│  - Check ESPN API for games TODAY                           │
│  - Extract: game_id, time, teams, location                  │
│  - Handle: Thursday Night, Sunday (1PM/4PM), SNF, MNF       │
│                                                              │
│  Output: Today's games with kickoff times                   │
│  File: data/schedules/today_schedule.json                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Calculate Alert Times                              │
│  ─────────────────────────────────────────────────────────  │
│  For each game:                                              │
│  - Kickoff time - 1 hour = Alert time                       │
│  - Schedule notification job                                 │
│                                                              │
│  Example:                                                    │
│  - Game: KC vs BUF at 4:25 PM ET                            │
│  - Alert: 3:25 PM ET                                         │
└─────────────────────────────────────────────────────────────┘
```

### **PHASE 2: PRE-GAME ANALYSIS** (1 Hour Before Each Game)

```
┌─────────────────────────────────────────────────────────────┐
│  TRIGGERED: 1 Hour Before Kickoff                           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Get Live Odds (The Odds API)                       │
│  ─────────────────────────────────────────────────────────  │
│  - Fetch current odds from multiple sportsbooks             │
│  - Get: Moneyline, Spread, Total, Alt lines                 │
│  - Line shopping: Find best odds                            │
│                                                              │
│  Output: Current betting lines                              │
│  File: data/odds/game_{game_id}_odds.json                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: Generate Features for This Game                    │
│  ─────────────────────────────────────────────────────────  │
│  - Calculate Elo ratings                                     │
│  - Get rest days, injuries, weather                         │
│  - EPA metrics, form, referee stats                         │
│  - All 46 features needed for model                         │
│                                                              │
│  Output: Feature vector for game                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 6: Run Model Prediction                               │
│  ─────────────────────────────────────────────────────────  │
│  - Load: models/xgboost_improved.pkl                        │
│  - Predict: Home win probability                            │
│  - Calculate: Expected value vs odds                        │
│                                                              │
│  Output: Prediction with confidence                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 7: Apply Edge Filters                                 │
│  ─────────────────────────────────────────────────────────  │
│  Check if game meets ANY discovered edge:                   │
│                                                              │
│  ✓ Edge #1: Home Favorite (Elo > 100)?                      │
│  ✓ Edge #2: Late Season Mismatch?                           │
│  ✓ Edge #3: Cold Weather Home?                              │
│  ✓ Edge #4: Early Season Favorite?                          │
│  ... (all discovered edges)                                  │
│                                                              │
│  If NO edges match → Skip this game                         │
│  If edges match → Proceed to Step 8                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 8: Generate Bet Recommendations                       │
│  ─────────────────────────────────────────────────────────  │
│  For each matching edge:                                     │
│  - Recommended bet (ML, spread, total)                      │
│  - Best odds (from line shopping)                           │
│  - Kelly sizing (bet amount)                                │
│  - Confidence tier (S/A/B/C)                                │
│  - Expected ROI                                              │
│                                                              │
│  Output: List of recommended bets                           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 9: Generate Parlay Combinations                       │
│  ─────────────────────────────────────────────────────────  │
│  Rules for parlays:                                          │
│  - Only combine Tier S bets (highest confidence)            │
│  - Max 3 legs (2-leg and 3-leg parlays)                     │
│  - Games must be uncorrelated                               │
│  - Calculate combined probability                           │
│                                                              │
│  Example:                                                    │
│  - Game 1: KC -7.5 (80% confidence)                         │
│  - Game 2: BUF -6 (75% confidence)                          │
│  - Parlay: 80% × 75% = 60% win probability                  │
│  - Parlay Odds: +264 (3.64x payout)                         │
│  - Expected ROI: 60% × 3.64 - 40% = 118% (POSITIVE)         │
│                                                              │
│  Output: Recommended parlays with EV calculation            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 10: Send Notification                                 │
│  ─────────────────────────────────────────────────────────  │
│  Methods:                                                    │
│  - Email (detailed analysis)                                 │
│  - SMS (quick alert)                                         │
│  - Desktop notification (Windows notification)              │
│                                                              │
│  Content:                                                    │
│  - Game info (teams, time, location)                        │
│  - Recommended bets (singles + parlays)                     │
│  - Odds, sizing, confidence                                 │
│  - Reasoning (which edge applies)                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 📅 **NFL SCHEDULE HANDLING**

### **Regular Season Game Schedule:**

```
THURSDAY:
- Thursday Night Football (8:15 PM ET)
- Alert: 7:15 PM ET

SUNDAY:
- Early games (1:00 PM ET)      → Alert: 12:00 PM ET
- Late games (4:05/4:25 PM ET)  → Alert: 3:05/3:25 PM ET
- Sunday Night Football (8:20 PM ET) → Alert: 7:20 PM ET

MONDAY:
- Monday Night Football (8:15 PM ET) → Alert: 7:15 PM ET

SATURDAY (Late Season):
- College ends → NFL Saturday games (varies)
- Alert: 1 hour before each

HOLIDAYS:
- Thanksgiving: 3 games (12:30 PM, 4:30 PM, 8:20 PM ET)
- Christmas: Special scheduling (check schedule)
- New Year's: Special scheduling
```

### **How We Handle This:**

```python
# Daily schedule check
def get_today_games():
    """Get games for today from ESPN API."""
    
    # ESPN API endpoint
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    
    response = requests.get(url)
    data = response.json()
    
    today_games = []
    for event in data['events']:
        game = {
            'game_id': event['id'],
            'home_team': event['competitions'][0]['competitors'][0]['team']['abbreviation'],
            'away_team': event['competitions'][0]['competitors'][1]['team']['abbreviation'],
            'kickoff': event['date'],  # ISO format
            'status': event['status']['type']['name']  # scheduled, in-progress, final
        }
        today_games.append(game)
    
    return today_games
```

---

## 🔔 **NOTIFICATION SYSTEM**

### **Option 1: Email (Detailed)**

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email_alert(game_info, bets, parlays):
    """Send detailed email with bet recommendations."""
    
    subject = f"🏈 NFL BETS: {game_info['away_team']} @ {game_info['home_team']}"
    
    body = f"""
    GAME: {game_info['away_team']} @ {game_info['home_team']}
    TIME: {game_info['kickoff']}
    LOCATION: {game_info['location']}
    
    RECOMMENDED BETS:
    {format_bets(bets)}
    
    RECOMMENDED PARLAYS:
    {format_parlays(parlays)}
    
    Bet responsibly. These are research insights, not guarantees.
    """
    
    # Send via Gmail SMTP
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = "nfl-bulldog@yourdomain.com"
    msg['To'] = "your-email@gmail.com"
    msg.attach(MIMEText(body, 'plain'))
    
    # Send
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login('your-email@gmail.com', 'your-app-password')
        smtp.send_message(msg)
```

### **Option 2: SMS (Quick Alert)**

```python
from twilio.rest import Client

def send_sms_alert(game_info, top_bet):
    """Send quick SMS alert."""
    
    client = Client(account_sid, auth_token)
    
    message = client.messages.create(
        body=f"🏈 NFL BET: {game_info['away_team']} @ {game_info['home_team']} "
             f"at {game_info['time']}\n"
             f"BET: {top_bet['type']} {top_bet['pick']} @ {top_bet['odds']}\n"
             f"Confidence: {top_bet['tier']}",
        from_='+1234567890',
        to='+1YOUR_PHONE'
    )
```

### **Option 3: Desktop Notification (Windows)**

```python
from plyer import notification

def send_desktop_alert(game_info, bet_count, parlay_count):
    """Send Windows desktop notification."""
    
    notification.notify(
        title=f"🏈 NFL BETS AVAILABLE",
        message=f"{game_info['away_team']} @ {game_info['home_team']}\n"
                f"{bet_count} bets, {parlay_count} parlays",
        app_name="NFL Bulldog",
        timeout=10
    )
```

---

## 🎲 **PARLAY GENERATION LOGIC**

### **Smart Parlay Rules:**

```python
def generate_parlays(tier_s_bets):
    """
    Generate parlays from Tier S bets only.
    
    Rules:
    1. Only use Tier S bets (highest confidence)
    2. Max 3 legs (2-leg and 3-leg only)
    3. No correlated games (same game, division rivals)
    4. Combined probability > 55% (better than break-even)
    5. Expected ROI > 0
    """
    
    parlays = []
    
    # 2-leg parlays
    for bet1, bet2 in combinations(tier_s_bets, 2):
        if not is_correlated(bet1, bet2):
            parlay = {
                'legs': [bet1, bet2],
                'combined_prob': bet1['prob'] * bet2['prob'],
                'odds': calculate_parlay_odds([bet1['odds'], bet2['odds']]),
            }
            
            # Calculate expected value
            parlay['expected_roi'] = (
                parlay['combined_prob'] * (parlay['odds'] - 1) - 
                (1 - parlay['combined_prob'])
            )
            
            # Only recommend if positive EV
            if parlay['expected_roi'] > 0 and parlay['combined_prob'] > 0.55:
                parlays.append(parlay)
    
    # 3-leg parlays (more aggressive)
    for bet1, bet2, bet3 in combinations(tier_s_bets, 3):
        if not is_correlated_triple(bet1, bet2, bet3):
            parlay = {
                'legs': [bet1, bet2, bet3],
                'combined_prob': bet1['prob'] * bet2['prob'] * bet3['prob'],
                'odds': calculate_parlay_odds([bet1['odds'], bet2['odds'], bet3['odds']]),
            }
            
            parlay['expected_roi'] = (
                parlay['combined_prob'] * (parlay['odds'] - 1) - 
                (1 - parlay['combined_prob'])
            )
            
            # Only recommend if positive EV
            if parlay['expected_roi'] > 0 and parlay['combined_prob'] > 0.50:
                parlays.append(parlay)
    
    # Sort by expected ROI
    parlays = sorted(parlays, key=lambda x: x['expected_roi'], reverse=True)
    
    return parlays[:5]  # Top 5 parlays only


def is_correlated(bet1, bet2):
    """Check if two bets are correlated."""
    
    # Same game
    if bet1['game_id'] == bet2['game_id']:
        return True
    
    # Division rivals (same day)
    if bet1['division'] == bet2['division'] and bet1['date'] == bet2['date']:
        return True
    
    return False
```

### **Example Parlay Output:**

```
RECOMMENDED PARLAY #1 (2-LEG):
├─ Leg 1: KC Chiefs ML (-320) vs DEN
│  ├─ Confidence: 80% (Tier S)
│  └─ Edge: Home Favorite (Elo > 100)
│
├─ Leg 2: BUF Bills -6.5 (-110) vs NYJ
│  ├─ Confidence: 75% (Tier S)
│  └─ Edge: Divisional Domination
│
├─ Combined Probability: 60% (80% × 75%)
├─ Parlay Odds: +120 (2.20x payout)
├─ Expected ROI: +32%
│
└─ RECOMMENDATION: BET $100 → Potential Win $220
```

---

## 🤖 **AUTOMATION OPTIONS**

### **Option 1: Windows Task Scheduler** (Simple)

```powershell
# Create scheduled task
$trigger = New-ScheduledTaskTrigger -Daily -At 6AM
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\Scripts\nfl-betting-system\scripts\daily_pipeline.py"

Register-ScheduledTask -TaskName "NFL Daily Pipeline" -Trigger $trigger -Action $action

# Create multiple triggers for game times
# (Would need separate tasks for each game time)
```

### **Option 2: Python Scheduler** (Flexible)

```python
import schedule
import time

def daily_pipeline():
    """Run daily data update."""
    download_latest_data()
    update_features()
    schedule_today_games()

def pre_game_alert(game_id):
    """Run 1 hour before game."""
    get_live_odds(game_id)
    generate_predictions(game_id)
    apply_edge_filters(game_id)
    generate_parlays(game_id)
    send_notifications(game_id)

# Schedule daily pipeline
schedule.every().day.at("06:00").do(daily_pipeline)

# Schedule game alerts dynamically
def schedule_today_games():
    games = get_today_games()
    for game in games:
        alert_time = game['kickoff'] - timedelta(hours=1)
        schedule.every().day.at(alert_time.strftime("%H:%M")).do(
            pre_game_alert, game['game_id']
        )

# Run forever
while True:
    schedule.run_pending()
    time.sleep(60)  # Check every minute
```

### **Option 3: Cloud Functions** (Production-Grade)

```
Google Cloud Functions / AWS Lambda:
- Trigger 1: Daily at 6 AM (data update)
- Trigger 2: PubSub from schedule check (game alerts)
- Trigger 3: Weekly (edge discovery)

Benefits:
- Always running
- No local machine needed
- Email/SMS integration
- Scalable

Cost: $5-20/month
```

---

## 📋 **IMPLEMENTATION CHECKLIST**

### **Phase 1: Core Pipeline (Week 1)**
- [ ] Build daily data download script
- [ ] Integrate ESPN API for schedules
- [ ] Build feature generation for upcoming games
- [ ] Test with upcoming weekend games

### **Phase 2: Prediction System (Week 2)**
- [ ] Build prediction script for single game
- [ ] Integrate The Odds API for live odds
- [ ] Implement edge filtering logic
- [ ] Test predictions vs discovered edges

### **Phase 3: Parlay Generator (Week 2-3)**
- [ ] Build parlay combination logic
- [ ] Implement correlation detection
- [ ] Calculate expected value
- [ ] Test on historical data

### **Phase 4: Notifications (Week 3)**
- [ ] Set up email system (Gmail SMTP)
- [ ] Optional: Set up SMS (Twilio)
- [ ] Build notification templates
- [ ] Test notifications

### **Phase 5: Automation (Week 4)**
- [ ] Build daily scheduler
- [ ] Build game-time scheduler
- [ ] Test full workflow end-to-end
- [ ] Deploy and monitor

### **Phase 6: Monitoring (Ongoing)**
- [ ] Track bet recommendations
- [ ] Track actual results
- [ ] Calculate ROI
- [ ] Refine edges based on results

---

## 💰 **ESTIMATED COSTS**

```
ONE-TIME:
- Development: $0 (you're doing it)

MONTHLY:
- The Odds API: $0-50 (500-10,000 requests)
- Twilio SMS: $0-10 (optional, ~$0.0075/SMS)
- Email: $0 (Gmail free tier)
- Grok API: $25-50 (weekly edge discovery)
- Server/Cloud: $0-20 (optional, for 24/7 uptime)

TOTAL: $25-130/month
```

**ROI**: If system generates just **ONE profitable bet per week**, it pays for itself.

---

## 🎯 **EXPECTED OUTCOMES**

### **Notifications Per Week:**
```
Thursday: 1 game → 1 notification
Sunday: 12-14 games → 3-5 notifications (only edges)
Monday: 1 game → 1 notification

Total: 5-7 notifications per week
Parlays: 2-3 per week (weekends mostly)
```

### **Bet Quality:**
```
Only notify on discovered edges (76%+ win rate)
Only generate parlays with positive EV
Only recommend when conditions are met

Quality > Quantity
```

---

## 🚀 **NEXT STEPS**

**I'll build the complete system in phases:**

1. **First**: Daily pipeline + prediction script
2. **Second**: Notification system
3. **Third**: Parlay generator
4. **Fourth**: Full automation

**Want me to start building now?**

---

**Status**: 📋 Plan complete  
**Timeline**: 4 weeks to full deployment  
**Risk**: Low (paper trade first)  
**Reward**: Automated profitable betting system  

**LET'S BUILD IT.** 🏈💰

