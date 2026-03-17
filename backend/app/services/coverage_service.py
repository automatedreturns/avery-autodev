"""Coverage Analysis Service for parsing and analyzing test coverage reports."""

import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CoverageParseError(Exception):
    """Custom exception for coverage parsing errors."""

    pass


def parse_coverage_report(
    repo_path: str,
    framework: str,
) -> dict[str, Any]:
    """
    Parse test coverage report based on test framework.

    Args:
        repo_path: Path to repository
        framework: Test framework name (pytest, jest, etc.)

    Returns:
        Dictionary with coverage data:
        {
            "coverage_percentage": 85.5,
            "lines_covered": 1234,
            "lines_total": 1445,
            "files": [
                {
                    "path": "src/auth.py",
                    "coverage": 92.3,
                    "lines_covered": 120,
                    "lines_total": 130,
                    "uncovered_lines": [15, 16, 23, 45, 67, 89, 102, 115, 120, 127]
                }
            ]
        }

    Raises:
        CoverageParseError: If parsing fails
    """
    framework_lower = framework.lower()

    try:
        if framework_lower == "pytest":
            return _parse_pytest_coverage(repo_path)
        elif framework_lower == "jest":
            return _parse_jest_coverage(repo_path)
        elif framework_lower == "mocha":
            return _parse_istanbul_coverage(repo_path)
        else:
            logger.warning(f"Coverage parsing not supported for {framework}")
            return {
                "coverage_percentage": None,
                "lines_covered": 0,
                "lines_total": 0,
                "files": [],
            }
    except Exception as e:
        logger.error(f"Failed to parse coverage report: {e}")
        raise CoverageParseError(f"Coverage parsing failed: {str(e)}")


def _parse_pytest_coverage(repo_path: str) -> dict[str, Any]:
    """
    Parse pytest coverage report from coverage.xml.

    Args:
        repo_path: Path to repository

    Returns:
        Dictionary with coverage data
    """
    coverage_xml_path = os.path.join(repo_path, "coverage.xml")

    if not os.path.exists(coverage_xml_path):
        logger.warning("coverage.xml not found")
        return {
            "coverage_percentage": None,
            "lines_covered": 0,
            "lines_total": 0,
            "files": [],
        }

    try:
        tree = ET.parse(coverage_xml_path)
        root = tree.getroot()

        # Get overall coverage
        line_rate = float(root.attrib.get("line-rate", 0))
        coverage_percentage = line_rate * 100

        # Parse file-level coverage
        files = []
        total_lines = 0
        covered_lines = 0

        for package in root.findall(".//package"):
            for cls in package.findall("classes/class"):
                filename = cls.attrib.get("filename", "")
                lines = cls.findall("lines/line")

                if not lines:
                    continue

                file_total = len(lines)
                file_covered = sum(1 for line in lines if int(line.attrib.get("hits", 0)) > 0)
                file_coverage = (file_covered / file_total * 100) if file_total > 0 else 0

                # Get uncovered line numbers
                uncovered_lines = [
                    int(line.attrib.get("number", 0))
                    for line in lines
                    if int(line.attrib.get("hits", 0)) == 0
                ]

                files.append({
                    "path": filename,
                    "coverage": round(file_coverage, 2),
                    "lines_covered": file_covered,
                    "lines_total": file_total,
                    "uncovered_lines": uncovered_lines,
                })

                total_lines += file_total
                covered_lines += file_covered

        return {
            "coverage_percentage": round(coverage_percentage, 2),
            "lines_covered": covered_lines,
            "lines_total": total_lines,
            "files": files,
        }

    except ET.ParseError as e:
        logger.error(f"Failed to parse coverage.xml: {e}")
        raise CoverageParseError(f"Invalid coverage.xml: {str(e)}")


def _parse_jest_coverage(repo_path: str) -> dict[str, Any]:
    """
    Parse Jest coverage report from coverage-summary.json.

    Args:
        repo_path: Path to repository

    Returns:
        Dictionary with coverage data
    """
    coverage_json_path = os.path.join(repo_path, "coverage", "coverage-summary.json")

    if not os.path.exists(coverage_json_path):
        logger.warning("coverage-summary.json not found")
        return {
            "coverage_percentage": None,
            "lines_covered": 0,
            "lines_total": 0,
            "files": [],
        }

    try:
        with open(coverage_json_path, "r") as f:
            coverage_data = json.load(f)

        # Get total coverage
        total_data = coverage_data.get("total", {})
        lines_data = total_data.get("lines", {})
        coverage_percentage = lines_data.get("pct", 0)
        total_lines = lines_data.get("total", 0)
        covered_lines = lines_data.get("covered", 0)

        # Parse file-level coverage
        files = []
        for file_path, file_data in coverage_data.items():
            if file_path == "total":
                continue

            file_lines = file_data.get("lines", {})
            file_coverage = file_lines.get("pct", 0)
            file_total = file_lines.get("total", 0)
            file_covered = file_lines.get("covered", 0)

            # Try to get uncovered lines from line data
            uncovered_lines = []
            line_data = file_data.get("lines", {}).get("data", {})
            if isinstance(line_data, dict):
                uncovered_lines = [
                    int(line_num)
                    for line_num, hits in line_data.items()
                    if hits == 0
                ]

            files.append({
                "path": file_path,
                "coverage": round(file_coverage, 2),
                "lines_covered": file_covered,
                "lines_total": file_total,
                "uncovered_lines": sorted(uncovered_lines)[:50],  # Limit to 50 lines
            })

        return {
            "coverage_percentage": round(coverage_percentage, 2),
            "lines_covered": covered_lines,
            "lines_total": total_lines,
            "files": files,
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse coverage-summary.json: {e}")
        raise CoverageParseError(f"Invalid JSON in coverage report: {str(e)}")


def _parse_istanbul_coverage(repo_path: str) -> dict[str, Any]:
    """
    Parse Istanbul/NYC coverage report (used by Mocha).

    Args:
        repo_path: Path to repository

    Returns:
        Dictionary with coverage data
    """
    # Istanbul also creates coverage-summary.json
    return _parse_jest_coverage(repo_path)


def get_coverage_summary(coverage_data: dict[str, Any]) -> dict[str, Any]:
    """
    Generate a summary of coverage data.

    Args:
        coverage_data: Parsed coverage data

    Returns:
        Summary dictionary with key metrics
    """
    total_files = len(coverage_data.get("files", []))
    coverage_percentage = coverage_data.get("coverage_percentage", 0)

    # Calculate files by coverage level
    files = coverage_data.get("files", [])
    high_coverage = sum(1 for f in files if f.get("coverage", 0) >= 80)
    medium_coverage = sum(1 for f in files if 50 <= f.get("coverage", 0) < 80)
    low_coverage = sum(1 for f in files if f.get("coverage", 0) < 50)

    # Find files with lowest coverage
    sorted_files = sorted(files, key=lambda f: f.get("coverage", 0))
    lowest_coverage_files = [
        {"path": f["path"], "coverage": f["coverage"]}
        for f in sorted_files[:10]  # Top 10 lowest
    ]

    return {
        "total_files": total_files,
        "coverage_percentage": coverage_percentage,
        "lines_covered": coverage_data.get("lines_covered", 0),
        "lines_total": coverage_data.get("lines_total", 0),
        "files_high_coverage": high_coverage,
        "files_medium_coverage": medium_coverage,
        "files_low_coverage": low_coverage,
        "lowest_coverage_files": lowest_coverage_files,
    }


def get_coverage_diff(
    current_coverage: dict[str, Any],
    previous_coverage: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate coverage difference between two runs.

    Args:
        current_coverage: Current coverage data
        previous_coverage: Previous coverage data

    Returns:
        Dictionary with coverage changes
    """
    current_pct = current_coverage.get("coverage_percentage", 0) or 0
    previous_pct = previous_coverage.get("coverage_percentage", 0) or 0
    diff = current_pct - previous_pct

    # Find files with coverage changes
    current_files = {f["path"]: f for f in current_coverage.get("files", [])}
    previous_files = {f["path"]: f for f in previous_coverage.get("files", [])}

    improved_files = []
    regressed_files = []

    for path, current_file in current_files.items():
        if path in previous_files:
            current_file_pct = current_file.get("coverage", 0)
            previous_file_pct = previous_files[path].get("coverage", 0)
            file_diff = current_file_pct - previous_file_pct

            if file_diff > 0:
                improved_files.append({
                    "path": path,
                    "diff": round(file_diff, 2),
                    "current": round(current_file_pct, 2),
                })
            elif file_diff < 0:
                regressed_files.append({
                    "path": path,
                    "diff": round(file_diff, 2),
                    "current": round(current_file_pct, 2),
                })

    # Sort by absolute diff
    improved_files.sort(key=lambda f: abs(f["diff"]), reverse=True)
    regressed_files.sort(key=lambda f: abs(f["diff"]), reverse=True)

    return {
        "coverage_diff": round(diff, 2),
        "current_coverage": round(current_pct, 2),
        "previous_coverage": round(previous_pct, 2),
        "improved_files": improved_files[:10],  # Top 10
        "regressed_files": regressed_files[:10],  # Top 10
        "status": "improved" if diff > 0 else "regressed" if diff < 0 else "unchanged",
    }


def get_uncovered_code_summary(coverage_data: dict[str, Any]) -> dict[str, Any]:
    """
    Generate summary of uncovered code.

    Args:
        coverage_data: Parsed coverage data

    Returns:
        Summary of files and lines needing coverage
    """
    files = coverage_data.get("files", [])

    # Files with most uncovered lines
    files_with_uncovered = [
        {
            "path": f["path"],
            "uncovered_count": len(f.get("uncovered_lines", [])),
            "uncovered_lines": f.get("uncovered_lines", [])[:20],  # First 20 lines
            "coverage": f.get("coverage", 0),
        }
        for f in files
        if f.get("uncovered_lines")
    ]

    # Sort by uncovered count
    files_with_uncovered.sort(key=lambda f: f["uncovered_count"], reverse=True)

    total_uncovered_lines = sum(f["uncovered_count"] for f in files_with_uncovered)

    return {
        "total_uncovered_lines": total_uncovered_lines,
        "files_with_gaps": len(files_with_uncovered),
        "priority_files": files_with_uncovered[:10],  # Top 10
    }
