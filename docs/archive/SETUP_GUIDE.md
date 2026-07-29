# Setup Guide - NFL Betting System

## Quick Setup (Recommended)

### Step 1: Create Virtual Environment with Python 3.12

```powershell
# Windows (PowerShell)
py -3.12 -m venv .venv
.venv\Scripts\activate
```

```bash
# Linux/Mac
python3.12 -m venv .venv
source .venv/bin/activate
```

**Why Python 3.12?**
- Python 3.13 has compatibility issues with some ML libraries
- Python 3.12 is stable and well-supported by all dependencies

### Step 2: Install Dependencies

```powershell
# Upgrade pip first
python -m pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt
```

### Step 3: Verify Installation

```powershell
# Check that nflreadpy is installed
python -c "import nflreadpy; print('✓ nflreadpy installed')"

# Check pandas
python -c "import pandas; print('✓ pandas installed')"

# Check xgboost
python -c "import xgboost; print('✓ xgboost installed')"
```

### Step 4: Run Tests

```powershell
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Step 5: Download Data

```powershell
# Download NFL data (2016-2024)
python scripts/download_data.py

# This will create:
#   data/raw/schedules_2016_2024.parquet
#   data/raw/pbp_2016_2024.parquet
#   data/raw/weekly_offense_2016_2024.parquet
#   data/raw/teams.parquet
#   data/raw/metadata.json
```

---

## Troubleshooting

### Issue: "No module named 'nflreadpy'"

**Solution:**
```powershell
pip install nflreadpy
```

### Issue: "numpy compilation error"

**Cause:** Python 3.13 requires C compiler for numpy 1.x

**Solution:** Use Python 3.12 or 3.11 (as shown in Step 1)

### Issue: "ModuleNotFoundError: No module named 'src'"

**Solution:** Run commands from the project root directory:
```powershell
cd C:\Scripts\nfl-betting-system
python scripts/download_data.py
```

### Issue: "pytest not found"

**Solution:**
```powershell
pip install pytest pytest-cov pytest-mock
```

### Issue: Download fails with HTTP 404

**Causes:**
- No internet connection
- nflverse API is down (rare)
- Invalid season year

**Solutions:**
```powershell
# Try without play-by-play (smaller download)
python scripts/download_data.py --no-pbp

# Try specific seasons
python scripts/download_data.py --seasons 2020-2024

# Check internet connection
ping google.com
```

---

## Verify Everything Works

Run this complete test:

```powershell
# 1. Check Python version
python --version  # Should be 3.10, 3.11, 3.12, or 3.13

# 2. Check imports
python -c "import nflreadpy, pandas, numpy, xgboost; print('✓ All imports successful')"

# 3. Run tests
pytest tests/ -v

# 4. Download sample data (just one season for testing)
python scripts/download_data.py --seasons 2023

# 5. Check downloaded files
ls data/raw/

# Should see:
#   schedules_2023_2023.parquet
#   pbp_2023_2023.parquet
#   weekly_offense_2023_2023.parquet
#   teams.parquet
#   metadata.json
```

---

## Development Workflow

1. **Activate virtual environment** (every time you start work):
   ```powershell
   .venv\Scripts\activate
   ```

2. **Make code changes** in `src/`

3. **Run tests** after changes:
   ```powershell
   pytest tests/ -v
   ```

4. **Format code** before committing:
   ```powershell
   black src/ tests/ scripts/
   ruff check src/ tests/ scripts/
   ```

5. **Type checking** (optional):
   ```powershell
   mypy src/
   ```

---

## Data Pipeline Usage

### Download Data

```powershell
# Default: 2016-2024 seasons
python scripts/download_data.py

# Custom range
python scripts/download_data.py --seasons 2018-2024

# Specific seasons
python scripts/download_data.py --seasons 2020,2021,2022,2023

# All available seasons (1999-present)
python scripts/download_data.py --all

# Force re-download (ignore cache)
python scripts/download_data.py --force

# Skip play-by-play (faster)
python scripts/download_data.py --no-pbp
```

### Programmatic Usage

```python
from src.data_pipeline import NFLDataPipeline

# Initialize pipeline
pipeline = NFLDataPipeline(data_dir="data")

# Download specific data
schedules = pipeline.get_schedules(seasons=[2023, 2024])
pbp = pipeline.get_play_by_play(seasons=[2023])
teams = pipeline.get_team_descriptions()

# Download everything
results = pipeline.download_all(
    seasons=list(range(2016, 2025)),
    include_pbp=True,
    force_download=False
)

print(f"Downloaded {len(results['schedules'])} games")
print(f"Downloaded {len(results['pbp'])} plays")
```

### Read Downloaded Data

```python
import pandas as pd

# Read schedules
df = pd.read_parquet("data/raw/schedules_2016_2024.parquet")
print(df.head())

# Read play-by-play
pbp = pd.read_parquet("data/raw/pbp_2016_2024.parquet")
print(pbp[['game_id', 'posteam', 'epa']].head())

# Read weekly stats
weekly = pd.read_parquet("data/raw/weekly_offense_2016_2024.parquet")
print(weekly.head())
```

---

## Next Steps After Setup

Once data pipeline is working:

1. **Day 3-4**: Feature engineering
   - EPA aggregation
   - Elo ratings
   - Rest days calculation
   - Recent form metrics

2. **Day 5-6**: Model training
   - XGBoost classifier
   - Probability calibration
   - Hyperparameter tuning

3. **Day 7**: Backtesting
   - Historical validation
   - ROI calculation
   - GO/NO-GO decision

---

## Resources

- **Project README**: `README.md`
- **Data Pipeline docs**: `src/data_pipeline.py` (detailed docstrings)
- **Test examples**: `tests/test_data_pipeline.py`
- **nflverse data**: https://nflreadr.nflverse.com/

---

**Last Updated**: 2025-01-27  
**Python Version**: 3.10-3.13 (recommend 3.12+)  
**Status**: Data Pipeline Ready ✓


