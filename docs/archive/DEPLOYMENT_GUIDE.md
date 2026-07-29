# 🚀 DEPLOYMENT GUIDE

**Date**: 2025-11-24  
**Status**: ✅ Production Ready  
**System**: NFL Betting System + Dashboard GUI

---

## 📋 QUICK START

### **Option 1: Deploy Everything (Recommended)**

**Windows**:
```bash
deploy.bat
```

**Linux/macOS**:
```bash
chmod +x deploy.sh
./deploy.sh
```

This will:
1. Check dependencies
2. Start autonomous system (background)
3. Start dashboard GUI (foreground)
4. Open browser automatically

---

### **Option 2: Deploy Separately**

#### **Terminal 1: Autonomous System**
```bash
python scripts/start_autonomous_system.py
```

**What it starts**:
- ✅ 11 agents (orchestrator + specialists + workers)
- ✅ 3 swarms (strategy generation, validation, consensus)
- ✅ Self-healing system (monitoring, anomaly detection)
- ✅ Request orchestrator (API management)
- ✅ Connectivity auditor
- ✅ AI backtest orchestrator

#### **Terminal 2: Dashboard GUI**
```bash
streamlit run dashboard/app.py
```

**What it provides**:
- ✅ Today's best bets with confidence scoring
- ✅ Live performance tracking
- ✅ Smart bankroll management
- ✅ Line shopping comparison
- ✅ Bet tracking & history
- ✅ Configurable risk profiles

**Access**: http://localhost:8501

---

## ✅ PRE-DEPLOYMENT CHECKLIST

### **1. Dependencies Installed** ✅

```bash
# Install all dependencies
pip install -r requirements.txt
pip install -r dashboard/requirements.txt

# Verify critical dependencies
python -c "import streamlit, psutil, nflreadpy; print('✅ All dependencies installed')"
```

### **2. API Keys Configured** ⚠️

```bash
# Copy template
cp config/api_keys.env.template config/api_keys.env

# Edit and add your key
notepad config/api_keys.env  # Windows
nano config/api_keys.env     # Linux/macOS
```

**Required**:
```env
ODDS_API_KEY="your_key_here"
```

**Optional**:
```env
XAI_API_KEY="your_xai_key_here"  # For AI insights
```

**Note**: ESPN and NOAA APIs are FREE - no keys needed!

### **3. System Verified** ✅

```bash
# Run test suite
python test_system_simple.py
```

**Expected**: All tests pass (7/7)

---

## 🔧 CONFIGURATION

### **Dashboard Port** (Default: 8501)

Change port:
```bash
streamlit run dashboard/app.py --server.port 8080
```

### **Autonomous System Logging**

Logs are output to console. To save logs:
```bash
python scripts/start_autonomous_system.py > logs/system.log 2>&1
```

---

## 🌐 NETWORK ACCESS

### **Local Access** (Default)
- Dashboard: http://localhost:8501
- System: Runs locally

### **Network Access** (Same Network)

**Dashboard**:
```bash
streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501
```

**Access from other devices**: http://YOUR_IP:8501

---

## 📊 MONITORING

### **System Health**

The autonomous system includes built-in monitoring:
- CPU usage
- Memory usage
- Disk usage
- API rate limits
- Agent status
- Error tracking

### **Dashboard Metrics**

The dashboard displays:
- Win rate
- ROI
- Total bets
- Performance charts
- Bankroll status

---

## 🛠️ TROUBLESHOOTING

### **Port Already in Use**

```bash
# Find process using port 8501
netstat -ano | findstr :8501  # Windows
lsof -i :8501                 # Linux/macOS

# Use different port
streamlit run dashboard/app.py --server.port 8502
```

### **Import Errors**

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### **API Errors**

- Check `config/api_keys.env` exists
- Verify ODDS_API_KEY is set (if using betting odds)
- ESPN/NOAA work without keys (FREE)

### **System Won't Start**

```bash
# Check Python version
python --version  # Should be 3.10+

# Check dependencies
python test_system_simple.py

# Check logs
# Look for error messages in console output
```

---

## 🔄 UPDATES & MAINTENANCE

### **Update Dependencies**

```bash
pip install -r requirements.txt --upgrade
pip install -r dashboard/requirements.txt --upgrade
```

### **Restart System**

1. Stop autonomous system (Ctrl+C)
2. Stop dashboard (Ctrl+C)
3. Restart both

### **Clear Cache**

```bash
# Clear Streamlit cache
streamlit cache clear

# Clear odds cache
python scripts/manage_cache.py --clear
```

---

## 📱 MOBILE ACCESS

The dashboard is mobile-responsive. Access from:
- Phone browser: http://YOUR_IP:8501
- Tablet browser: http://YOUR_IP:8501

**Note**: Use network access mode (0.0.0.0) to access from mobile devices on same network.

---

## 🔐 SECURITY NOTES

### **Production Deployment**

For production:
1. Use reverse proxy (nginx, Apache)
2. Enable HTTPS (SSL certificate)
3. Set up authentication (see `dashboard/app_auth.py`)
4. Restrict network access
5. Use environment variables for API keys

### **API Keys**

- Never commit `config/api_keys.env` to git
- Use environment variables in production
- Rotate keys regularly

---

## 📈 PERFORMANCE

### **System Resources**

**Minimum**:
- CPU: 2 cores
- RAM: 4GB
- Disk: 2GB free

**Recommended**:
- CPU: 4+ cores
- RAM: 8GB+
- Disk: 5GB+ free

### **Optimization**

- Cache aggressively (already implemented)
- Use rate limiting (already implemented)
- Monitor resource usage (built-in monitoring)

---

## ✅ DEPLOYMENT VERIFICATION

After deployment, verify:

1. **Autonomous System**:
   - ✅ All agents started
   - ✅ No error messages
   - ✅ Monitoring active

2. **Dashboard**:
   - ✅ Opens in browser
   - ✅ Shows today's picks
   - ✅ Metrics display correctly

3. **APIs**:
   - ✅ ESPN API working (FREE)
   - ✅ NOAA API working (FREE)
   - ✅ Odds API working (if key provided)

---

## 🎯 NEXT STEPS

1. ✅ **Deploy system** - Use deployment scripts
2. ✅ **Monitor performance** - Check dashboard metrics
3. ✅ **Review picks** - Daily picks generated automatically
4. ✅ **Adjust settings** - Configure risk profiles in dashboard

---

## 📚 RELATED DOCUMENTATION

- `README.md` - System overview
- `SYSTEM_STATUS.md` - Current status
- `CLAUDE_IMPLEMENTATION_SUMMARY.md` - Recent fixes
- `CODEBASE_REVIEW_COMPLETE.md` - Code review
- `dashboard/README.md` - Dashboard documentation

---

**Status**: ✅ **READY FOR DEPLOYMENT**

**Last Updated**: 2025-11-24

