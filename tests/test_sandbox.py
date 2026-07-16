"""Manual historical sandbox harness.

This file previously looked like a pytest suite but defined ``SandboxTester``,
which pytest does not collect under the repository's ``Test*`` class rule. It is
now explicitly classified as manual historical material so CI totals cannot be
mistaken for coverage of its old live-pick workflow.
"""

MANUAL_TEST_MODULE = True
__test__ = False


def main() -> int:
    print(
        "Historical sandbox harness disabled. "
        "Use deterministic pytest modules and paper-decision fixtures."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
