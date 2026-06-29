"""Startup validation — fail fast on broken config or missing critical deps."""

import importlib
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

REQUIRED_PACKAGES = [
    "pandas",
    "numpy",
    "xgboost",
    "sklearn",
    "yaml",
    "requests",
]

OPTIONAL_PACKAGES = {
    "streamlit": "Dashboard UI",
    "plotly": "Dashboard charts",
    "lightgbm": "LightGBM model",
    "pybreaker": "Circuit breakers",
    "tenacity": "Retry patterns",
}


def validate_dependencies(strict: bool = False) -> bool:
    """Check that required packages are importable."""
    ok = True
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except ImportError:
            logger.error("Required package missing: %s", pkg)
            ok = False

    for pkg, desc in OPTIONAL_PACKAGES.items():
        try:
            importlib.import_module(pkg)
        except ImportError:
            logger.warning("Optional package missing: %s (%s)", pkg, desc)
            if strict:
                ok = False

    return ok


def validate_config() -> bool:
    """Validate that critical config files exist and parse correctly."""
    ok = True

    config_yaml = Path("config/config.yaml")
    if config_yaml.exists():
        try:
            import yaml

            with open(config_yaml) as f:
                cfg = yaml.safe_load(f)
            if not isinstance(cfg, dict):
                logger.error("config/config.yaml did not parse as a dict")
                ok = False
            if "model" not in cfg:
                logger.warning("config/config.yaml missing 'model' section")
        except Exception as e:
            logger.error("config/config.yaml parse error: %s", e)
            ok = False
    else:
        logger.warning("config/config.yaml not found — using defaults")

    return ok


def validate_directories() -> bool:
    """Ensure expected directory structure exists."""
    dirs = ["data", "config"]
    ok = True
    for d in dirs:
        p = Path(d)
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            logger.info("Created missing directory: %s", d)
    return ok


def startup_check(strict: bool = False) -> bool:
    """Run all startup validations. Returns False if critical checks fail."""
    results = []
    results.append(("dependencies", validate_dependencies(strict)))
    results.append(("config", validate_config()))
    results.append(("directories", validate_directories()))

    all_ok = all(r[1] for r in results)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        logger.info("Startup check [%s]: %s", name, status)

    if not all_ok:
        logger.error("Startup validation failed — fix issues above before continuing")

    return all_ok


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ok = startup_check(strict="--strict" in sys.argv)
    sys.exit(0 if ok else 1)
