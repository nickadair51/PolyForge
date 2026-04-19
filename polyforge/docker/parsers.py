"""Generic test output parser.

Scans stdout/stderr for common test-result patterns (e.g. "3 passed",
"1 failed", "2 errors") regardless of which test framework produced them.
"""

import re
from dataclasses import dataclass


@dataclass
class TestCounts:
    passed: int
    failed: int
    errored: int


# Patterns that match "<number> passed/failed/error(s/ed)" in any order.
# Case-insensitive so it catches "PASSED", "Failed", "Errors", etc.
_PASSED_PATTERN = re.compile(r"(\d+)\s+passed", re.IGNORECASE)
_FAILED_PATTERN = re.compile(r"(\d+)\s+failed", re.IGNORECASE)
_ERROR_PATTERN = re.compile(r"(\d+)\s+errors?(?:ed)?", re.IGNORECASE)


def parse_test_output(stdout: str, stderr: str) -> TestCounts:
    """Extract test pass/fail/error counts from combined container output."""
    combined = stdout + "\n" + stderr

    passed = _sum_matches(_PASSED_PATTERN, combined)
    failed = _sum_matches(_FAILED_PATTERN, combined)
    errored = _sum_matches(_ERROR_PATTERN, combined)

    return TestCounts(passed=passed, failed=failed, errored=errored)


def _sum_matches(pattern: re.Pattern, text: str) -> int:
    """Return the largest match for a pattern.

    Uses max instead of sum because most runners print cumulative totals
    at the end — summing would double-count when subtotals appear earlier.
    """
    matches = [int(m.group(1)) for m in pattern.finditer(text)]
    return max(matches) if matches else 0
