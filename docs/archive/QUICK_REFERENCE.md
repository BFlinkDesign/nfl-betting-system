# Quick Reference - NFL Betting System Data Pipeline

## 🚀 Essential Commands

### Setup (First Time Only)
```powershell
# 1. Create virtual environment (Python 3.10-3.13)
py -3.12 -m venv .venv

# 2. Activate
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Validate setup
python validate_setup.py
```

### Download Data
```powershell
# Default (2016-2024)
python scripts/download_data.py

# Custom seasons
python scripts/download_data.py --seasons 2020-2024

# Force re-download
python scripts/download_data.py --force

# Skip play-by-play (faster)
python scripts/download_data.py --no-pbp
```

### Run Tests
```powershell
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src

# Specific test
pytest tests/test_data_pipeline.py::TestNFLDataPipeline::test_get_schedules_download -v
```

### Explore Data
```python
import pandas as pd

# Schedules
df = pd.read_parquet("data/raw/schedules_2016_2024.parquet")
print(df[['game_date', 'home_team', 'away_team', 'home_score', 'away_score']].head())

# Play-by-play
pbp = pd.read_parquet("data/raw/pbp_2016_2024.parquet")
print(pbp[['game_id', 'posteam', 'epa']].head())

# Teams
teams = pd.read_parquet("data/raw/teams.parquet")
print(teams[['team_abbr', 'team_name', 'team_division']])
```

---

## 📁 File Structure

```
nfl-betting-system/
├── src/
│   └── data_pipeline.py       # Main pipeline class
├── scripts/
│   └── download_data.py       # CLI download script
├── tests/
│   └── test_data_pipeline.py  # Unit tests
├── data/
│   └── raw/                   # Downloaded data (parquet)
├── requirements.txt           # Dependencies
├── README.md                  # Project docs
├── SETUP_GUIDE.md            # Setup instructions
└── validate_setup.py         # Setup validation
```

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| `No module named 'nflreadpy'` | `pip install -r requirements.txt` |
| `numpy compilation error` | Use Python 3.12: `py -3.12 -m venv .venv` |
| `Download failed` | Try `--no-pbp` or `--seasons 2023` |
| `Tests fail` | Run from project root: `cd C:\Scripts\nfl-betting-system` |
| `Parquet not found` | Download data first: `python scripts/download_data.py` |

---

## 📊 Expected Data Sizes

| File | Rows | Size |
|------|------|------|
| `schedules_2016_2024.parquet` | ~2,500 | 1.5 MB |
| `pbp_2016_2024.parquet` | ~450K | 150 MB |
| `weekly_offense_2016_2024.parquet` | ~15K | 5 MB |
| `teams.parquet` | 32 | 50 KB |
| **TOTAL** | **~507K** | **~157 MB** |

---

## 🐍 Python API

### Basic Usage
```python
from src.data_pipeline import NFLDataPipeline

# Initialize
pipeline = NFLDataPipeline(data_dir="data", cache_days=7)

# Download all data
results = pipeline.download_all(
    seasons=list(range(2016, 2025)),
    include_pbp=True,
    force_download=False
)

# Access data
schedules = results['schedules']
pbp = results['pbp']
```

### Individual Downloads
```python
# Schedules only
schedules = pipeline.get_schedules([2023, 2024])

# Play-by-play only
pbp = pipeline.get_play_by_play([2023])

# Weekly stats
weekly = pipeline.get_weekly_stats([2023], stat_type='offense')

# Teams
teams = pipeline.get_team_descriptions()
```

### Force Fresh Download
```python
# Ignore cache
schedules = pipeline.get_schedules([2024], force_download=True)
```

---

## ✅ Validation Checklist

Before moving to Day 3-4:

- [ ] Python 3.12 installed
- [ ] Virtual environment activated
- [ ] Dependencies installed (`pip list | findstr nflreadpy`)
- [ ] `python validate_setup.py` passes
- [ ] Data downloaded (check `data/raw/`)
- [ ] Tests pass (`pytest tests/ -v`)

---

## 📚 Documentation

- **README.md**: Project overview
- **SETUP_GUIDE.md**: Detailed setup instructions
- **DAY_1-2_IMPLEMENTATION_SUMMARY.md**: Complete implementation details
- **QUICK_REFERENCE.md**: This file (quick commands)

---

## 🎯 Next Steps

**Day 3-4: Feature Engineering**
- EPA (Expected Points Added)
- Elo ratings
- Rest days
- Recent form
- Situational features

**Command**: `python src/feature_engineering.py` (to be implemented)

---

## 💡 Tips

1. **Always activate venv**: `.venv\Scripts\activate`
2. **Use cache**: Don't use `--force` unless needed
3. **Start small**: Test with `--seasons 2023` first
4. **Read parquet**: Use `pd.read_parquet()` not `pd.read_csv()`
5. **Check metadata**: `data/raw/metadata.json` has download info

---

**Quick Start**: `python validate_setup.py` → `python scripts/download_data.py` → Start coding!

