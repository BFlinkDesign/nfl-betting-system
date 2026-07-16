"""Manual historical end-to-end harness.

The former ``E2ETester`` class was not collected by pytest because its name did
not start with ``Test``. It also used simulated odds and asserted that wagers
were generated, which is not a valid real-world acceptance test. This file is
kept only as an explicit manual-history marker.
"""

MANUAL_TEST_MODULE = True
__test__ = False


def main() -> int:
    print(
        "Historical simulated-wager E2E harness disabled. "
        "Use immutable market snapshots and paper-decision receipts."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
