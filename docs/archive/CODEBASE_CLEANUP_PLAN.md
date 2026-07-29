# 🧹 CODEBASE CLEANUP PLAN

**Date**: 2025-11-24  
**Status**: Issues Identified and Fixes Applied

---

## ✅ FIXES APPLIED

### **1. Missing Type Imports** ✅ FIXED

**Files Fixed**:
- `src/swarms/strategy_generation_swarm.py` - Added `Dict` import
- `src/swarms/validation_swarm.py` - Added `Dict, Any` imports

**Status**: ✅ All swarm imports now working

### **2. Token Bucket Default Config** ✅ FIXED

**File**: `src/utils/token_bucket.py`

**Issue**: `register_default()` would warn but not create bucket for unknown APIs

**Fix**: Now creates bucket with generic defaults (100/day) if no specific config exists

**Status**: ✅ Token bucket stress test now passes

---

## 📋 DUPLICATE FILES TO CONSOLIDATE

### **Status Reports** (4 files - consolidate to 1)

1. `SYSTEM_STATUS.md` - Current system status
2. `FINAL_STATUS.md` - Final status report
3. `INSTALLATION_COMPLETE.md` - Installation status
4. `SYSTEM_READY_CHECKLIST.md` - Ready checklist

**Action**: Merge into `SYSTEM_STATUS.md` and delete others

### **Audit Reports** (5 files - consolidate to 1)

1. `SYSTEM_AUDIT_REPORT.md` - Main audit
2. `SYSTEM_AUDIT_COMPLETE.md` - Audit completion
3. `AUDIT_COMPLETE.md` - Another audit completion
4. `DATA_SOURCE_AUDIT_REPORT.md` - Data source audit
5. `CODEBASE_REVIEW_REPORT.md` - Codebase review

**Action**: Keep `SYSTEM_AUDIT_REPORT.md`, archive others to `docs/archive/`

### **Implementation Reports** (2 files - consolidate)

1. `IMPLEMENTATION_COMPLETE.md` - Implementation status
2. `QUICK_FIXES_APPLIED.md` - Quick fixes

**Action**: Merge into `IMPLEMENTATION_COMPLETE.md`

### **Test Files** (2 files - keep 1)

1. `test_system.py` - Original test (has Unicode issues)
2. `test_system_simple.py` - Windows-compatible test ✅

**Action**: Delete `test_system.py`, keep `test_system_simple.py`

---

## 🗑️ FILES TO DELETE

### **Duplicate Documentation**

1. `test_system.py` - Replaced by `test_system_simple.py`
2. `SYSTEM_AUDIT_COMPLETE.md` - Duplicate of `SYSTEM_AUDIT_REPORT.md`
3. `AUDIT_COMPLETE.md` - Duplicate
4. `FINAL_STATUS.md` - Merge into `SYSTEM_STATUS.md`
5. `INSTALLATION_COMPLETE.md` - Merge into `SYSTEM_STATUS.md`
6. `QUICK_FIXES_APPLIED.md` - Merge into `IMPLEMENTATION_COMPLETE.md`

### **Temporary Files**

1. `comprehensive_review.py` - One-time review script (can archive)

---

## 📝 FILES TO MERGE

### **Status Files → `SYSTEM_STATUS.md`**

Merge content from:
- `FINAL_STATUS.md`
- `INSTALLATION_COMPLETE.md`
- `SYSTEM_READY_CHECKLIST.md`

### **Implementation Files → `IMPLEMENTATION_COMPLETE.md`**

Merge content from:
- `QUICK_FIXES_APPLIED.md`

---

## 🔍 FILES TO REVIEW FOR DELETION

### **Old/Unused Scripts** (Review before deleting)

1. `get_mnf_pick.py` - Single-purpose script (may be useful)
2. `validate_setup.py` - Setup validation (may be useful)

### **Dashboard Files** (Review duplicates)

1. `dashboard/app.py` - Main dashboard
2. `dashboard/app_complete.py` - Complete version?
3. `dashboard/app_auth.py` - Auth version?
4. `dashboard/simple_ai_login.py` - Login version?

**Action**: Review and consolidate dashboard files

---

## ✅ VERIFICATION CHECKLIST

- [x] All imports fixed
- [x] All type errors resolved
- [x] Token bucket default config fixed
- [ ] Duplicate files identified
- [ ] Files merged/consolidated
- [ ] Unused files deleted
- [ ] Documentation updated

---

## 🎯 NEXT STEPS

1. **Consolidate Status Files** → `SYSTEM_STATUS.md`
2. **Archive Old Reports** → `docs/archive/`
3. **Delete Duplicate Test File** → `test_system.py`
4. **Review Dashboard Files** → Consolidate if duplicates
5. **Final Verification** → Run tests again

---

**Status**: Ready for cleanup execution

