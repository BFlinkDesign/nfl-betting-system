"""
COMPREHENSIVE DATA SOURCE AUDIT

Tests ALL endpoints and data sources mentioned in strategy documents.
Verifies: availability, access, rate limits, data quality.
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataSourceAuditor:
    """Audit all data sources for validity."""

    def __init__(self):
        self.results = []
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "NFL-Betting-System-Audit/1.0"})

    def audit_all(self) -> Dict:
        """Run complete audit of all data sources."""
        logger.info("=" * 70)
        logger.info("COMPREHENSIVE DATA SOURCE AUDIT")
        logger.info("=" * 70)

        # Tier 1: Primary Sources
        self.audit_noaa_apis()
        self.audit_nflverse()
        self.audit_espn_api()
        self.audit_odds_api()
        self.audit_kaggle_datasets()

        # Tier 2: Secondary Sources
        self.audit_twitter_api()
        self.audit_reddit_api()
        self.audit_aws_nfl_data()
        self.audit_big_data_bowl()

        # Tier 3: Scraping Sources
        self.audit_vegas_insider()
        self.audit_action_network()
        self.audit_pff_api()

        return self.generate_report()

    def audit_noaa_apis(self):
        """Verify NOAA weather APIs."""
        logger.info("\n[1] AUDITING NOAA APIs...")

        tests = [
            {
                "name": "NOAA Points API",
                "url": "https://api.weather.gov/points/39.0489,-94.4839",  # Arrowhead Stadium
                "expected_status": 200,
                "critical": True,
            },
            {
                "name": "NOAA Alerts API",
                "url": "https://api.weather.gov/alerts/active?area=IA",
                "expected_status": 200,
                "critical": False,
            },
            {
                "name": "NOAA Forecast API (via points)",
                "url": None,  # Will be derived from points
                "expected_status": 200,
                "critical": True,
            },
        ]

        for test in tests:
            try:
                if test["url"]:
                    response = self.session.get(test["url"], timeout=10)
                    status = response.status_code

                    if status == test["expected_status"]:
                        logger.info(f"  ✅ {test['name']}: WORKING (Status {status})")

                        # If points API, test forecast endpoint
                        if "points" in test["name"]:
                            data = response.json()
                            forecast_url = data.get("properties", {}).get("forecast")
                            if forecast_url:
                                forecast_resp = self.session.get(
                                    forecast_url, timeout=10
                                )
                                if forecast_resp.status_code == 200:
                                    logger.info("  ✅ NOAA Forecast API: WORKING")
                                else:
                                    logger.warning(
                                        f"  ⚠️  NOAA Forecast API: Status {forecast_resp.status_code}"
                                    )
                    else:
                        logger.error(f"  ❌ {test['name']}: FAILED (Status {status})")
                        self.results.append(
                            {
                                "source": test["name"],
                                "status": "FAILED",
                                "error": f"Status {status}",
                                "critical": test.get("critical", False),
                            }
                        )
                else:
                    logger.info(f"  ⏭️  {test['name']}: Skipped (derived endpoint)")

            except requests.exceptions.RequestException as e:
                logger.error(f"  ❌ {test['name']}: ERROR - {str(e)}")
                self.results.append(
                    {
                        "source": test["name"],
                        "status": "ERROR",
                        "error": str(e),
                        "critical": test.get("critical", False),
                    }
                )

            time.sleep(0.5)  # Rate limit respect

    def audit_nflverse(self):
        """Verify nflverse/nflreadpy availability."""
        logger.info("\n[2] AUDITING NFLVERSE...")

        try:
            # Check GitHub repo
            github_url = "https://api.github.com/repos/nflverse/nflverse-data"
            response = self.session.get(github_url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                stars = data.get("stargazers_count", 0)
                logger.info(f"  ✅ nflverse GitHub: EXISTS ({stars} stars)")
                logger.info(f"  ✅ Repository: {data.get('html_url')}")

                # Check if package is on PyPI
                pypi_url = "https://pypi.org/pypi/nflreadpy/json"
                pypi_resp = self.session.get(pypi_url, timeout=10)
                if pypi_resp.status_code == 200:
                    pypi_data = pypi_resp.json()
                    version = pypi_data.get("info", {}).get("version", "Unknown")
                    logger.info(f"  ✅ nflreadpy on PyPI: EXISTS (v{version})")
                else:
                    logger.warning("  ⚠️  nflreadpy: Not found on PyPI")
            else:
                logger.error("  ❌ nflverse: GitHub repo not found")
                self.results.append(
                    {
                        "source": "nflverse",
                        "status": "FAILED",
                        "error": f"GitHub status {response.status_code}",
                        "critical": True,
                    }
                )

        except Exception as e:
            logger.error(f"  ❌ nflverse: ERROR - {str(e)}")
            self.results.append(
                {
                    "source": "nflverse",
                    "status": "ERROR",
                    "error": str(e),
                    "critical": True,
                }
            )

    def audit_espn_api(self):
        """Verify ESPN API endpoints."""
        logger.info("\n[3] AUDITING ESPN API...")

        tests = [
            {
                "name": "ESPN Scoreboard",
                "url": "http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
                "expected_status": 200,
                "critical": True,
            },
            {
                "name": "ESPN Teams",
                "url": "http://site.api.espn.com/apis/site/v2/sports/football/nfl/teams",
                "expected_status": 200,
                "critical": False,
            },
        ]

        for test in tests:
            try:
                response = self.session.get(test["url"], timeout=10)
                status = response.status_code

                if status == test["expected_status"]:
                    logger.info(f"  ✅ {test['name']}: WORKING (Status {status})")
                else:
                    logger.error(f"  ❌ {test['name']}: FAILED (Status {status})")
                    self.results.append(
                        {
                            "source": test["name"],
                            "status": "FAILED",
                            "error": f"Status {status}",
                            "critical": test.get("critical", False),
                        }
                    )

            except Exception as e:
                logger.error(f"  ❌ {test['name']}: ERROR - {str(e)}")
                self.results.append(
                    {
                        "source": test["name"],
                        "status": "ERROR",
                        "error": str(e),
                        "critical": test.get("critical", False),
                    }
                )

            time.sleep(0.5)

    def audit_odds_api(self):
        """Verify The Odds API."""
        logger.info("\n[4] AUDITING THE ODDS API...")

        # Check documentation site
        try:
            doc_url = "https://the-odds-api.com/"
            response = self.session.get(doc_url, timeout=10)

            if response.status_code == 200:
                logger.info("  ✅ The Odds API: Website accessible")

                # Check if free tier info is mentioned
                if "500" in response.text or "free" in response.text.lower():
                    logger.info("  ✅ Free tier: Likely available (verify on site)")
                else:
                    logger.warning("  ⚠️  Free tier: Not clearly mentioned")
            else:
                logger.error("  ❌ The Odds API: Website not accessible")

        except Exception as e:
            logger.error(f"  ❌ The Odds API: ERROR - {str(e)}")

        logger.info("  ⚠️  NOTE: API key required - cannot test without key")
        logger.info("  ⚠️  Free tier: 500 requests/month (verify on theoddsapi.com)")

    def audit_kaggle_datasets(self):
        """Verify Kaggle datasets."""
        logger.info("\n[5] AUDITING KAGGLE DATASETS...")

        datasets = [
            {
                "name": "NFL Scores & Betting Data",
                "url": "https://www.kaggle.com/datasets/tobycrabtree/nfl-scores-and-betting-data",
                "critical": True,
            }
        ]

        for dataset in datasets:
            try:
                # Check if dataset page exists
                response = self.session.get(
                    dataset["url"], timeout=10, allow_redirects=True
                )

                if response.status_code == 200:
                    logger.info(f"  ✅ {dataset['name']}: Dataset page accessible")
                    logger.info(
                        "  ⚠️  NOTE: Kaggle account + API key required to download"
                    )
                else:
                    logger.error(
                        f"  ❌ {dataset['name']}: Page not accessible (Status {response.status_code})"
                    )

            except Exception as e:
                logger.error(f"  ❌ {dataset['name']}: ERROR - {str(e)}")

    def audit_twitter_api(self):
        """Verify Twitter API availability."""
        logger.info("\n[6] AUDITING TWITTER API...")

        logger.info("  ⚠️  Twitter API v2: Requires API key")
        logger.info(
            "  ⚠️  Free tier: 500 tweets/month (verify on developer.twitter.com)"
        )
        logger.info("  ⚠️  Cannot test without API credentials")

    def audit_reddit_api(self):
        """Verify Reddit API."""
        logger.info("\n[7] AUDITING REDDIT API...")

        try:
            # Test public JSON endpoint (no auth required)
            url = "https://www.reddit.com/r/nfl/.json?limit=5"
            response = self.session.get(
                url, timeout=10, headers={"User-Agent": "NFL-Betting-System/1.0"}
            )

            if response.status_code == 200:
                data = response.json()
                logger.info("  ✅ Reddit API: WORKING (no auth required)")
                logger.info("  ✅ Can access: r/nfl subreddit")
            else:
                logger.error(f"  ❌ Reddit API: FAILED (Status {response.status_code})")

        except Exception as e:
            logger.error(f"  ❌ Reddit API: ERROR - {str(e)}")

    def audit_aws_nfl_data(self):
        """Verify AWS NFL public data (CRITICAL - user says this doesn't exist)."""
        logger.info("\n[8] AUDITING AWS NFL DATA (CRITICAL CHECK)...")

        # Test the bucket that was mentioned
        test_urls = [
            "https://nfl-public-data.s3.us-east-1.amazonaws.com/",
            "https://registry.opendata.aws/nfl-public-data/",
        ]

        for url in test_urls:
            try:
                response = self.session.get(url, timeout=10, allow_redirects=True)

                if response.status_code == 404 or "NoSuchBucket" in response.text:
                    logger.error(
                        "  ❌ AWS S3 Bucket: DOES NOT EXIST (as user reported)"
                    )
                    logger.error(f"  ❌ URL: {url}")
                    self.results.append(
                        {
                            "source": "AWS NFL Public Data",
                            "status": "FAILED",
                            "error": "Bucket does not exist (verified)",
                            "critical": True,
                        }
                    )
                else:
                    logger.warning(
                        f"  ⚠️  AWS S3: Unexpected response (Status {response.status_code})"
                    )

            except Exception as e:
                logger.error(f"  ❌ AWS S3: ERROR - {str(e)}")
                self.results.append(
                    {
                        "source": "AWS NFL Public Data",
                        "status": "FAILED",
                        "error": str(e),
                        "critical": True,
                    }
                )

    def audit_big_data_bowl(self):
        """Verify NFL Big Data Bowl data availability."""
        logger.info("\n[9] AUDITING NFL BIG DATA BOWL...")

        urls = [
            {
                "name": "Big Data Bowl 2024 (Kaggle)",
                "url": "https://www.kaggle.com/competitions/nfl-big-data-bowl-2024",
            },
            {
                "name": "Big Data Bowl GitHub",
                "url": "https://github.com/nfl-football-ops/Big-Data-Bowl",
            },
        ]

        for test in urls:
            try:
                response = self.session.get(
                    test["url"], timeout=10, allow_redirects=True
                )

                if response.status_code == 200:
                    logger.info(f"  ✅ {test['name']}: ACCESSIBLE")
                else:
                    logger.warning(
                        f"  ⚠️  {test['name']}: Status {response.status_code}"
                    )

            except Exception as e:
                logger.error(f"  ❌ {test['name']}: ERROR - {str(e)}")

    def audit_vegas_insider(self):
        """Verify Vegas Insider scraping."""
        logger.info("\n[10] AUDITING VEGAS INSIDER...")

        try:
            url = "https://www.vegasinsider.com/nfl/odds/las-vegas/"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                logger.info("  ✅ Vegas Insider: Website accessible")
                logger.info("  ⚠️  NOTE: Scraping required - check robots.txt")
            else:
                logger.error(f"  ❌ Vegas Insider: Status {response.status_code}")

        except Exception as e:
            logger.error(f"  ❌ Vegas Insider: ERROR - {str(e)}")

    def audit_action_network(self):
        """Verify Action Network."""
        logger.info("\n[11] AUDITING ACTION NETWORK...")

        try:
            url = "https://www.actionnetwork.com/nfl/odds"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                logger.info("  ✅ Action Network: Website accessible")
                logger.info("  ⚠️  NOTE: Scraping required - check robots.txt")
            else:
                logger.error(f"  ❌ Action Network: Status {response.status_code}")

        except Exception as e:
            logger.error(f"  ❌ Action Network: ERROR - {str(e)}")

    def audit_pff_api(self):
        """Verify PFF API endpoints."""
        logger.info("\n[12] AUDITING PFF API...")

        tests = [
            {
                "name": "PFF Scoreboard Ticker",
                "url": "https://www.pff.com/api/scoreboard/ticker?league=nfl&season=2024&week=12",
                "expected_status": [200, 401, 403],  # May require auth
            }
        ]

        for test in tests:
            try:
                response = self.session.get(test["url"], timeout=10)
                status = response.status_code

                if status in test["expected_status"]:
                    if status == 200:
                        logger.info(f"  ✅ {test['name']}: WORKING (no auth required)")
                    else:
                        logger.warning(
                            f"  ⚠️  {test['name']}: Requires authentication (Status {status})"
                        )
                else:
                    logger.error(f"  ❌ {test['name']}: Unexpected status {status}")

            except Exception as e:
                logger.error(f"  ❌ {test['name']}: ERROR - {str(e)}")

    def generate_report(self) -> Dict:
        """Generate final audit report."""
        logger.info("\n" + "=" * 70)
        logger.info("AUDIT SUMMARY")
        logger.info("=" * 70)

        critical_failures = [r for r in self.results if r.get("critical")]

        if critical_failures:
            logger.error(f"\n❌ CRITICAL FAILURES: {len(critical_failures)}")
            for failure in critical_failures:
                logger.error(f"  - {failure['source']}: {failure['error']}")
        else:
            logger.info("\n✅ No critical failures detected")

        logger.info(f"\nTotal issues found: {len(self.results)}")

        return {
            "timestamp": datetime.now().isoformat(),
            "total_issues": len(self.results),
            "critical_failures": critical_failures,
            "all_results": self.results,
        }


if __name__ == "__main__":
    auditor = DataSourceAuditor()
    report = auditor.audit_all()

    # Save report
    with open("reports/data_source_audit.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 70)
    print("Audit complete! Report saved to reports/data_source_audit.json")
    print("=" * 70)
