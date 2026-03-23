"""Tests for the smoke test build script framework."""
from __future__ import annotations

import tempfile
from pathlib import Path

from tests.smoke_test_build import SmokeTest, SmokeTestSuite, build_checklist


class TestSmokeTest:
    def test_dataclass_defaults(self) -> None:
        t = SmokeTest("name", "desc", "ac")
        assert t.result == "pending"
        assert t.notes == ""

    def test_dataclass_fields(self) -> None:
        t = SmokeTest("x", "y", "z", result="pass", notes="ok")
        assert t.name == "x"
        assert t.description == "y"
        assert t.acceptance_criteria == "z"
        assert t.result == "pass"
        assert t.notes == "ok"


class TestSmokeTestSuite:
    def test_add_test(self) -> None:
        suite = SmokeTestSuite()
        suite.add("test1", "desc1", "ac1")
        assert len(suite.tests) == 1
        assert suite.tests[0].name == "test1"

    def test_counts_empty(self) -> None:
        suite = SmokeTestSuite()
        assert suite.pass_count == 0
        assert suite.fail_count == 0
        assert suite.skip_count == 0

    def test_counts_mixed(self) -> None:
        suite = SmokeTestSuite()
        suite.add("a", "d", "ac")
        suite.add("b", "d", "ac")
        suite.add("c", "d", "ac")
        suite.tests[0].result = "pass"
        suite.tests[1].result = "fail"
        suite.tests[2].result = "skip"
        assert suite.pass_count == 1
        assert suite.fail_count == 1
        assert suite.skip_count == 1

    def test_summary_text_contains_results(self) -> None:
        suite = SmokeTestSuite()
        suite.add("test1", "description1", "ac1")
        suite.tests[0].result = "pass"
        suite.end_time = suite.start_time
        text = suite.summary_text()
        assert "PASS" in text
        assert "test1" in text
        assert "ALL PASSED" in text

    def test_summary_text_with_failures(self) -> None:
        suite = SmokeTestSuite()
        suite.add("broken", "it broke", "ac1")
        suite.tests[0].result = "fail"
        suite.tests[0].notes = "crash on startup"
        suite.end_time = suite.start_time
        text = suite.summary_text()
        assert "FAIL" in text
        assert "HAS FAILURES" in text
        assert "FAILURES:" in text
        assert "crash on startup" in text

    def test_save_results(self) -> None:
        suite = SmokeTestSuite()
        suite.add("t", "d", "ac")
        suite.tests[0].result = "pass"
        suite.end_time = suite.start_time

        with tempfile.TemporaryDirectory() as tmpdir:
            path = suite.save_results(Path(tmpdir))
            assert path.exists()
            assert path.name.startswith("smoke-test-results-")
            assert path.suffix == ".txt"
            content = path.read_text(encoding="utf-8")
            assert "PASS" in content

    def test_save_results_creates_directory(self) -> None:
        suite = SmokeTestSuite()
        suite.end_time = suite.start_time

        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "sub" / "dir"
            path = suite.save_results(nested)
            assert path.exists()


class TestBuildChecklist:
    def test_checklist_has_22_tests(self) -> None:
        suite = build_checklist()
        assert len(suite.tests) == 22

    def test_all_tests_start_pending(self) -> None:
        suite = build_checklist()
        for test in suite.tests:
            assert test.result == "pending"

    def test_all_tests_have_required_fields(self) -> None:
        suite = build_checklist()
        for test in suite.tests:
            assert test.name, f"Test missing name: {test}"
            assert test.description, f"Test missing description: {test}"
            assert test.acceptance_criteria, f"Test missing AC: {test}"

    def test_unique_test_names(self) -> None:
        suite = build_checklist()
        names = [t.name for t in suite.tests]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_covers_all_acceptance_criteria(self) -> None:
        """Verify the checklist references all ACs from the story."""
        suite = build_checklist()
        all_acs = " ".join(t.acceptance_criteria for t in suite.tests)
        for ac_num in range(1, 9):
            assert f"AC #{ac_num}" in all_acs, f"AC #{ac_num} not covered"
