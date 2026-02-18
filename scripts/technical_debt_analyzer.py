#!/usr/bin/env python3
"""
Technical Debt Analyzer Script

Analyzes project code for technical debt patterns including code smells,
security concerns, deprecated dependencies, and fragile logic. Outputs
structured reports in JSON or Markdown format.

Usage:
    python technical_debt_analyzer.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: markdown)
    --exclude-dirs DIRS       Comma-separated directories to exclude
    --severity LEVEL          Minimum severity to report (low/medium/high/critical)
    --help                    Show usage information
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(Enum):
    SECURITY = "Security"
    PERFORMANCE = "Performance"
    MAINTAINABILITY = "Maintainability"
    RELIABILITY = "Reliability"


@dataclass
class DebtFinding:
    """Represents a single technical debt finding."""
    location: str
    line_number: int
    issue: str
    severity: Severity
    category: Category
    code_snippet: str = ""
    suggested_fix: str = ""
    notes: str = ""


@dataclass
class AnalysisResult:
    """Complete analysis result for a project."""
    project_path: str
    findings: list[DebtFinding] = field(default_factory=list)
    file_count: int = 0
    scanned_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # Summary counts
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0


# Detection patterns with severity and category mappings
DETECTION_PATTERNS = [
    # Critical Security Issues
    {
        "name": "hardcoded_secrets",
        "pattern": r"(?i)(api_key|apikey|secret|password|passwd|token|auth).*=.*['\"][^'\"]{8,}['\"]",
        "severity": Severity.CRITICAL,
        "category": Category.SECURITY,
        "message": "Potential hardcoded secret/credential",
        "suggestion": "Move to environment variable or secrets manager"
    },
    {
        "name": "sql_injection",
        "pattern": r"(execute|executemany|raw)\s*\(\s*[fr]?['\"].*\+|f['\"].*select.*\{.*\}",
        "severity": Severity.CRITICAL,
        "category": Category.SECURITY,
        "message": "Potential SQL injection via string concatenation",
        "suggestion": "Use parameterized queries"
    },

    # High Severity Issues
    {
        "name": "inner_html",
        "pattern": r"(innerHTML|dangerouslySetInnerHTML)",
        "severity": Severity.HIGH,
        "category": Category.SECURITY,
        "message": "Potential XSS vulnerability via innerHTML",
        "suggestion": "Use textContent or sanitize HTML"
    },
    {
        "name": "await_no_try",
        "pattern": r"^\s*await\s+",
        "severity": Severity.HIGH,
        "category": Category.RELIABILITY,
        "message": "Await without surrounding try/catch block",
        "suggestion": "Wrap in try/catch for proper error handling",
        "context_check": "try_catch"  # Special handling needed
    },
    {
        "name": "promise_no_catch",
        "pattern": r"\.then\s*\([^)]*\)\s*(?!\s*\.catch)",
        "severity": Severity.HIGH,
        "category": Category.RELIABILITY,
        "message": "Promise chain without .catch() handler",
        "suggestion": "Add .catch() for error handling"
    },
    {
        "name": "eval_usage",
        "pattern": r"\beval\s*\(",
        "severity": Severity.HIGH,
        "category": Category.SECURITY,
        "message": "Use of eval() is a security risk",
        "suggestion": "Use safer alternatives like JSON.parse or Function constructor"
    },

    # Medium Severity Issues
    {
        "name": "hardcoded_url",
        "pattern": r"(https?://|localhost:\d+)[^'\"]*['\"]",
        "severity": Severity.MEDIUM,
        "category": Category.MAINTAINABILITY,
        "message": "Hardcoded URL/endpoint",
        "suggestion": "Move to configuration or environment variable"
    },
    {
        "name": "console_log",
        "pattern": r"console\.(log|debug|info|warn)\s*\(",
        "severity": Severity.MEDIUM,
        "category": Category.RELIABILITY,
        "message": "Console logging in production code",
        "suggestion": "Use proper logging library or remove for production"
    },
    {
        "name": "print_debug",
        "pattern": r"print\s*\(\s*[fr]?['\"].*(debug|test|todo)",
        "severity": Severity.MEDIUM,
        "category": Category.RELIABILITY,
        "message": "Debug print statement",
        "suggestion": "Remove or replace with proper logging"
    },
    {
        "name": "magic_number",
        "pattern": r"(==|!=|>=|<=|>|<)\s*(\d{3,})\s*$",
        "severity": Severity.MEDIUM,
        "category": Category.MAINTAINABILITY,
        "message": "Magic number without context",
        "suggestion": "Define as named constant"
    },
    {
        "name": "deep_nesting",
        "pattern": r"^\s{16,}if\s*\(",  # 4+ levels of indentation
        "severity": Severity.MEDIUM,
        "category": Category.MAINTAINABILITY,
        "message": "Deeply nested conditional (4+ levels)",
        "suggestion": "Extract to separate function or use early returns"
    },

    # Low Severity Issues
    {
        "name": "todo_comment",
        "pattern": r"(TODO|FIXME|HACK|XXX|BUG)\s*:?\s*(.+)",
        "severity": Severity.LOW,
        "category": Category.MAINTAINABILITY,
        "message": "TODO/FIXME comment",
        "suggestion": "Create ticket or resolve the issue"
    },
    {
        "name": "commented_code",
        "pattern": r"^\s*//\s*(function|const|let|var|import|export|async|class|def )",
        "severity": Severity.LOW,
        "category": Category.MAINTAINABILITY,
        "message": "Commented out code",
        "suggestion": "Remove dead code or document why it's kept"
    },
    {
        "name": "var_usage",
        "pattern": r"\bvar\s+\w+\s*=",
        "severity": Severity.LOW,
        "category": Category.MAINTAINABILITY,
        "message": "Use of 'var' instead of 'let' or 'const'",
        "suggestion": "Use 'const' for constants, 'let' for variables"
    },
    {
        "name": "any_type",
        "pattern": r":\s*any\b",
        "severity": Severity.LOW,
        "category": Category.MAINTAINABILITY,
        "message": "Use of 'any' type defeats type checking",
        "suggestion": "Use specific type or 'unknown' with type guards"
    },
]

# File extensions to scan
SCAN_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".php",
    ".c", ".cpp", ".h", ".cs", ".swift", ".kt", ".rs", ".scala"
}

# Default directories to exclude
DEFAULT_EXCLUDE_DIRS = {
    "node_modules", "venv", ".venv", "__pycache__", ".git", "dist",
    "build", ".next", ".nuxt", "coverage", ".pytest_cache", "migrations",
    "alembic", "public", "static", "assets", ".idea", ".vscode"
}


def get_relative_path(file_path: Path, project_path: Path) -> str:
    """Get relative path from project root."""
    try:
        return str(file_path.relative_to(project_path))
    except ValueError:
        return str(file_path)


def check_try_catch_context(lines: list[str], line_num: int) -> bool:
    """Check if an await statement is inside a try block."""
    # Look backwards for try {
    for i in range(line_num - 1, max(0, line_num - 20), -1):
        line = lines[i].strip()
        if "try" in line and ("{" in line or ":" in line):
            return True
        # If we hit a function def or class, stop
        if re.match(r"^\s*(async\s+)?def\s+|^\s*function\s+", line):
            break
    return False


def analyze_file(file_path: Path, project_path: Path) -> list[DebtFinding]:
    """Analyze a single file for technical debt patterns."""
    findings = []
    relative_path = get_relative_path(file_path, project_path)

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        return []

    for line_num, line in enumerate(lines, 1):
        for pattern_info in DETECTION_PATTERNS:
            pattern = pattern_info["pattern"]
            matches = re.finditer(pattern, line, re.IGNORECASE if pattern_info["name"] in ["hardcoded_secrets", "todo_comment"] else 0)

            for match in matches:
                # Special handling for await without try/catch
                if pattern_info.get("context_check") == "try_catch":
                    if check_try_catch_context(lines, line_num):
                        continue

                # Skip false positives
                if pattern_info["name"] == "hardcoded_secrets":
                    # Skip if it's in a comment
                    stripped = line.strip()
                    if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                        continue
                    # Skip if it's a type annotation or example
                    if "type" in line.lower() or "example" in line.lower():
                        continue

                # Skip hardcoded URLs that are just in comments
                if pattern_info["name"] == "hardcoded_url":
                    stripped = line.strip()
                    if stripped.startswith("#") or stripped.startswith("//"):
                        continue

                # Get code snippet (trimmed)
                code_snippet = line.strip()[:100]
                if len(line.strip()) > 100:
                    code_snippet += "..."

                finding = DebtFinding(
                    location=relative_path,
                    line_number=line_num,
                    issue=f"{pattern_info['message']}: {match.group()[:50]}",
                    severity=pattern_info["severity"],
                    category=pattern_info["category"],
                    code_snippet=code_snippet,
                    suggested_fix=pattern_info["suggestion"],
                    notes=""
                )
                findings.append(finding)

    return findings


def scan_project(project_path: str, exclude_dirs: set[str], min_severity: Severity) -> AnalysisResult:
    """Scan entire project for technical debt."""
    path = Path(project_path)
    result = AnalysisResult(project_path=str(path.absolute()))

    if not path.exists():
        result.errors.append(f"Project path does not exist: {project_path}")
        return result

    # Collect all files to scan
    files_to_scan = []
    for root, dirs, files in os.walk(path):
        # Filter out excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]

        for file in files:
            file_path = Path(root) / file
            if file_path.suffix in SCAN_EXTENSIONS:
                files_to_scan.append(file_path)

    result.file_count = len(files_to_scan)

    # Analyze each file
    for file_path in files_to_scan:
        result.scanned_files.append(get_relative_path(file_path, path))
        findings = analyze_file(file_path, path)
        result.findings.extend(findings)

    # Filter by minimum severity
    severity_order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
    min_index = severity_order.index(min_severity)
    result.findings = [f for f in result.findings if severity_order.index(f.severity) >= min_index]

    # Calculate summary counts
    for finding in result.findings:
        if finding.severity == Severity.CRITICAL:
            result.critical_count += 1
        elif finding.severity == Severity.HIGH:
            result.high_count += 1
        elif finding.severity == Severity.MEDIUM:
            result.medium_count += 1
        else:
            result.low_count += 1

    # Sort findings by severity (critical first)
    result.findings.sort(key=lambda f: severity_order.index(f.severity), reverse=True)

    return result


def output_json(result: AnalysisResult) -> str:
    """Format results as JSON."""
    output = {
        "project_path": result.project_path,
        "summary": {
            "files_scanned": result.file_count,
            "total_findings": len(result.findings),
            "critical": result.critical_count,
            "high": result.high_count,
            "medium": result.medium_count,
            "low": result.low_count
        },
        "findings": [
            {
                "location": f.location,
                "line": f.line_number,
                "issue": f.issue,
                "severity": f.severity.value,
                "category": f.category.value,
                "code_snippet": f.code_snippet,
                "suggested_fix": f.suggested_fix,
                "notes": f.notes
            }
            for f in result.findings
        ],
        "errors": result.errors
    }
    return json.dumps(output, indent=2)


def output_markdown(result: AnalysisResult) -> str:
    """Format results as Markdown."""
    lines = ["# Technical Debt & Risk Register\n"]

    # Summary
    lines.append("## Summary\n")
    lines.append(f"- **Project:** `{result.project_path}`")
    lines.append(f"- **Files Scanned:** {result.file_count}")
    lines.append(f"- **Total Findings:** {len(result.findings)}")
    lines.append("")

    # Severity Summary Table
    lines.append("### Severity Distribution\n")
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    lines.append(f"| Critical | {result.critical_count} |")
    lines.append(f"| High | {result.high_count} |")
    lines.append(f"| Medium | {result.medium_count} |")
    lines.append(f"| Low | {result.low_count} |")
    lines.append("")

    # Category Summary
    category_counts = {}
    for f in result.findings:
        cat = f.category.value
        category_counts[cat] = category_counts.get(cat, 0) + 1

    lines.append("### Category Distribution\n")
    lines.append("| Category | Count |")
    lines.append("|----------|-------|")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {cat} | {count} |")
    lines.append("")

    # Detailed Findings by Severity
    if result.critical_count > 0:
        lines.append("## Critical Issues\n")
        lines.append("| # | Location | Issue | Category | Suggested Fix |")
        lines.append("|---|----------|-------|----------|---------------|")
        idx = 1
        for f in result.findings:
            if f.severity == Severity.CRITICAL:
                loc = f"`{f.location}:{f.line_number}`"
                lines.append(f"| {idx} | {loc} | {f.issue} | {f.category.value} | {f.suggested_fix} |")
                idx += 1
        lines.append("")

    if result.high_count > 0:
        lines.append("## High Priority\n")
        lines.append("| # | Location | Issue | Category | Suggested Fix |")
        lines.append("|---|----------|-------|----------|---------------|")
        idx = 1
        for f in result.findings:
            if f.severity == Severity.HIGH:
                loc = f"`{f.location}:{f.line_number}`"
                lines.append(f"| {idx} | {loc} | {f.issue} | {f.category.value} | {f.suggested_fix} |")
                idx += 1
        lines.append("")

    if result.medium_count > 0:
        lines.append("## Medium Priority\n")
        lines.append("| # | Location | Issue | Category | Suggested Fix |")
        lines.append("|---|----------|-------|----------|---------------|")
        idx = 1
        for f in result.findings:
            if f.severity == Severity.MEDIUM:
                loc = f"`{f.location}:{f.line_number}`"
                lines.append(f"| {idx} | {loc} | {f.issue} | {f.category.value} | {f.suggested_fix} |")
                idx += 1
        lines.append("")

    if result.low_count > 0:
        lines.append("## Low Priority\n")
        lines.append("| # | Location | Issue | Category | Suggested Fix |")
        lines.append("|---|----------|-------|----------|---------------|")
        idx = 1
        for f in result.findings:
            if f.severity == Severity.LOW:
                loc = f"`{f.location}:{f.line_number}`"
                lines.append(f"| {idx} | {loc} | {f.issue} | {f.category.value} | {f.suggested_fix} |")
                idx += 1
        lines.append("")

    # Recommended Actions
    lines.append("## Recommended Actions\n")

    if result.critical_count > 0:
        lines.append("**Immediate (Critical):**")
        lines.append("- Fix all critical security vulnerabilities before deployment")
        lines.append("")

    if result.high_count > 0:
        lines.append("**This Sprint (High):**")
        lines.append("- Address high-priority reliability and security issues")
        lines.append("")

    if result.medium_count > 0:
        lines.append("**Next Sprint (Medium):**")
        lines.append("- Refactor hardcoded configurations")
        lines.append("- Remove debug logging statements")
        lines.append("")

    if result.low_count > 0:
        lines.append("**Backlog (Low):**")
        lines.append("- Clean up TODO/FIXME comments")
        lines.append("- Remove commented code")
        lines.append("- Improve type coverage")
        lines.append("")

    if result.errors:
        lines.append("## Errors\n")
        for error in result.errors:
            lines.append(f"- {error}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze project for technical debt patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --format json
  %(prog)s /path/to/project --severity high --format markdown
  %(prog)s /path/to/project --exclude-dirs "dist,build,generated"
"""
    )

    parser.add_argument(
        "project_path",
        help="Path to the project directory"
    )

    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format (default: markdown)"
    )

    parser.add_argument(
        "--exclude-dirs",
        help="Comma-separated directories to exclude (in addition to defaults)"
    )

    parser.add_argument(
        "--severity",
        choices=["low", "medium", "high", "critical"],
        default="low",
        help="Minimum severity to report (default: low)"
    )

    args = parser.parse_args()

    # Build exclude directories set
    exclude_dirs = DEFAULT_EXCLUDE_DIRS.copy()
    if args.exclude_dirs:
        for d in args.exclude_dirs.split(","):
            exclude_dirs.add(d.strip())

    # Map severity string to enum
    severity_map = {
        "low": Severity.LOW,
        "medium": Severity.MEDIUM,
        "high": Severity.HIGH,
        "critical": Severity.CRITICAL
    }
    min_severity = severity_map[args.severity]

    # Run analysis
    result = scan_project(args.project_path, exclude_dirs, min_severity)

    # Output results
    if args.output_format == "json":
        print(output_json(result))
    else:
        print(output_markdown(result))

    # Return exit code based on findings
    if result.critical_count > 0:
        sys.exit(2)  # Critical issues found
    elif result.high_count > 0:
        sys.exit(1)  # High issues found
    sys.exit(0)  # No critical/high issues


if __name__ == "__main__":
    main()
