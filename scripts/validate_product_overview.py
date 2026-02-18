#!/usr/bin/env python3
"""
Product Overview Validator

Validates generated product overview documents for completeness,
accessibility, business focus, and quality.

Usage:
    python scripts/validate_product_overview.py <product_overview_path> [options]

Options:
    --strict       Fail on warnings
    --format       Output format (json|markdown)
    --help         Show usage information

Exit Codes:
    0 - Document passed validation with no errors
    1 - Document passed but has warnings
    2 - Document failed validation (errors present)
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    category: str
    check: str
    passed: bool
    message: str
    severity: str  # error, warning, info


@dataclass
class ValidationSummary:
    """Summary of all validation results."""
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    is_valid: bool = True

    def add_result(self, result: ValidationResult):
        self.total_checks += 1
        if result.passed:
            self.passed += 1
        else:
            self.failed += 1

        if result.severity == "error" and not result.passed:
            self.errors += 1
            self.is_valid = False
        elif result.severity == "warning" and not result.passed:
            self.warnings += 1
        elif result.severity == "info":
            self.infos += 1


class ProductOverviewValidator:
    """Validates product overview documents."""

    REQUIRED_SECTIONS = [
        "What is",
        "Who is",
        "Key Features Summary",
        "Detailed Feature Descriptions",
        "Supported Integrations",
        "System Capabilities",
        "Use Cases",
        "Getting Started"
    ]

    TECHNICAL_JARGON_PATTERNS = [
        r'\bSQLAlchemy\b',
        r'\bORM\b',
        r'\bGraphQL query\b',
        r'\bAPI endpoint\b',
        r'\.py\b',
        r'\.js\b',
        r'\.ts\b',
        r'\bdef\s+\w+\s*\(',
        r'\bfunction\s+\w+\s*\(',
        r'\bclass\s+\w+',
        r'\bimport\s+\w+',
        r'\bfrom\s+\w+\s+import',
        r'\basync\s+def\b',
        r'\bawait\s+',
        r'\bSELECT\s+.*\s+FROM\b',
        r'\bINSERT\s+INTO\b',
        r'\bUPDATE\s+.*\s+SET\b',
    ]

    BENEFIT_KEYWORDS = [
        'benefit', 'value', 'save', 'reduce', 'increase',
        'improve', 'faster', 'better', 'efficiency', 'roi',
        'cost', 'revenue', 'profit', 'growth', 'productivity'
    ]

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.content = file_path.read_text(encoding='utf-8') if file_path.exists() else ""
        self.lines = self.content.split('\n') if self.content else []
        self.results: List[ValidationResult] = []
        self.summary = ValidationSummary()

    def validate_all(self) -> List[ValidationResult]:
        """Run all validation checks."""
        self.check_content_completeness()
        self.check_accessibility()
        self.check_business_focus()
        self.check_quality()
        self.check_integration()

        # Update summary
        for result in self.results:
            self.summary.add_result(result)

        return self.results

    def check_content_completeness(self):
        """Check all required sections present."""
        # Check each required section
        for section in self.REQUIRED_SECTIONS:
            if section in self.content:
                self._add_result(
                    category="Content Completeness",
                    check=f"Section '{section}' present",
                    passed=True,
                    message=f"Section found",
                    severity="info"
                )
            else:
                self._add_result(
                    category="Content Completeness",
                    check=f"Section '{section}' present",
                    passed=False,
                    message=f"Section NOT found",
                    severity="error"
                )

        # Check for subsection structure
        subsection_patterns = [
            (r'### The Challenge', "The Challenge subsection"),
            (r'### The Solution', "The Solution subsection"),
            (r'### The Value', "The Value subsection"),
            (r'\*\*What It Does\*\*', "What It Does in features"),
            (r'\*\*Why It Matters\*\*', "Why It Matters in features"),
            (r'\*\*How It Works\*\*', "How It Works in features"),
            (r'\*\*Business Benefits\*\*', "Business Benefits in features"),
        ]

        for pattern, name in subsection_patterns:
            if re.search(pattern, self.content, re.IGNORECASE):
                self._add_result(
                    category="Content Completeness",
                    check=f"{name} present",
                    passed=True,
                    message=f"Found",
                    severity="info"
                )
            else:
                self._add_result(
                    category="Content Completeness",
                    check=f"{name} present",
                    passed=False,
                    message=f"Not found",
                    severity="warning"
                )

    def check_accessibility(self):
        """Check for technical content that should be avoided."""
        # Check for code blocks (but allow inline code)
        code_blocks = re.findall(r'```\w*\n.*?```', self.content, re.DOTALL)
        if code_blocks:
            self._add_result(
                category="Accessibility",
                check="No code blocks",
                passed=False,
                message=f"Found {len(code_blocks)} code block(s) - should be removed",
                severity="error"
            )
        else:
            self._add_result(
                category="Accessibility",
                check="No code blocks",
                passed=True,
                message="No code blocks found",
                severity="info"
            )

        # Check for Mermaid diagrams
        if '```mermaid' in self.content.lower():
            self._add_result(
                category="Accessibility",
                check="No Mermaid diagrams",
                passed=False,
                message="Mermaid diagrams found (too technical for product overview)",
                severity="error"
            )
        else:
            self._add_result(
                category="Accessibility",
                check="No Mermaid diagrams",
                passed=True,
                message="No Mermaid diagrams",
                severity="info"
            )

        # Check for ERD diagrams
        if '```mermaid' in self.content.lower() and 'erDiagram' in self.content.lower():
            self._add_result(
                category="Accessibility",
                check="No ER diagrams",
                passed=False,
                message="ER diagrams found (too technical)",
                severity="error"
            )

        # Check for technical jargon
        jargon_found = []
        for pattern in self.TECHNICAL_JARGON_PATTERNS:
            matches = re.findall(pattern, self.content, re.IGNORECASE)
            if matches:
                jargon_found.extend(matches[:2])  # Limit to first 2 matches per pattern

        if jargon_found:
            self._add_result(
                category="Accessibility",
                check="No technical jargon",
                passed=False,
                message=f"Found technical terms: {', '.join(set(str(j)[:30] for j in jargon_found[:5]))}",
                severity="warning"
            )
        else:
            self._add_result(
                category="Accessibility",
                check="No technical jargon",
                passed=True,
                message="No technical jargon detected",
                severity="info"
            )

        # Check for API endpoint patterns
        api_patterns = re.findall(r'["\']/(api|v\d)/[^"\']*["\']', self.content)
        if api_patterns:
            self._add_result(
                category="Accessibility",
                check="No API paths visible",
                passed=False,
                message=f"Found {len(api_patterns)} API path(s)",
                severity="warning"
            )
        else:
            self._add_result(
                category="Accessibility",
                check="No API paths visible",
                passed=True,
                message="No API paths found",
                severity="info"
            )

    def check_business_focus(self):
        """Check business focus and value orientation."""
        # Count benefit-related keywords
        content_lower = self.content.lower()
        keyword_count = sum(
            content_lower.count(keyword)
            for keyword in self.BENEFIT_KEYWORDS
        )

        if keyword_count >= 20:
            self._add_result(
                category="Business Focus",
                check="Business value language",
                passed=True,
                message=f"Good use of value-oriented language ({keyword_count} instances)",
                severity="info"
            )
        elif keyword_count >= 10:
            self._add_result(
                category="Business Focus",
                check="Business value language",
                passed=True,
                message=f"Acceptable value language ({keyword_count} instances, recommend 20+)",
                severity="warning"
            )
        else:
            self._add_result(
                category="Business Focus",
                check="Business value language",
                passed=False,
                message=f"Insufficient value-oriented language ({keyword_count} instances, need 20+)",
                severity="error"
            )

        # Check for metrics/outcomes in Results sections
        metric_patterns = [
            r'\d+%',  # Percentages
            r'\d+\s*(hours?|days?|weeks?|months?)\s+(per|each|a)\s+\w+',  # Time savings
            r'\$\d+',  # Dollar amounts
            r'(saved|reduced|increased|improved)\s+(by\s+)?\d+',  # Improvements
        ]

        metric_count = 0
        for pattern in metric_patterns:
            metric_count += len(re.findall(pattern, self.content, re.IGNORECASE))

        if metric_count >= 10:
            self._add_result(
                category="Business Focus",
                check="Metrics and outcomes",
                passed=True,
                message=f"Good use of measurable outcomes ({metric_count} metrics)",
                severity="info"
            )
        elif metric_count >= 5:
            self._add_result(
                category="Business Focus",
                check="Metrics and outcomes",
                passed=True,
                message=f"Acceptable metrics ({metric_count}, recommend 10+)",
                severity="warning"
            )
        else:
            self._add_result(
                category="Business Focus",
                check="Metrics and outcomes",
                passed=False,
                message=f"Few measurable outcomes ({metric_count}, need 10+)",
                severity="warning"
            )

        # Check for Problem/Solution/Value structure
        problem_solution_pattern = re.search(
            r'(The Challenge|The Problem).*(The Solution|Solution).*(The Value|Value|Benefits)',
            self.content, re.DOTALL | re.IGNORECASE
        )

        if problem_solution_pattern:
            self._add_result(
                category="Business Focus",
                check="Problem-Solution-Value structure",
                passed=True,
                message="Document follows Problem-Solution-Value structure",
                severity="info"
            )
        else:
            self._add_result(
                category="Business Focus",
                check="Problem-Solution-Value structure",
                passed=False,
                message="Document may not follow recommended structure",
                severity="warning"
            )

    def check_quality(self):
        """Check document quality metrics."""
        line_count = len(self.lines)

        # Check length
        if 1500 <= line_count <= 2500:
            self._add_result(
                category="Quality",
                check="Document length",
                passed=True,
                message=f"Length is {line_count} lines (target: 1,500-2,500)",
                severity="info"
            )
        elif 1000 <= line_count < 1500:
            self._add_result(
                category="Quality",
                check="Document length",
                passed=True,
                message=f"Length is {line_count} lines (acceptable, below target)",
                severity="warning"
            )
        elif 2500 < line_count <= 3000:
            self._add_result(
                category="Quality",
                check="Document length",
                passed=True,
                message=f"Length is {line_count} lines (acceptable, above target)",
                severity="warning"
            )
        elif line_count < 1000:
            self._add_result(
                category="Quality",
                check="Document length",
                passed=False,
                message=f"Too short: {line_count} lines (minimum: 1,000)",
                severity="error"
            )
        else:
            self._add_result(
                category="Quality",
                check="Document length",
                passed=False,
                message=f"Too long: {line_count} lines (maximum: 3,000)",
                severity="warning"
            )

        # Check for placeholders
        placeholder_patterns = [
            r'\[PLACEHOLDER\]',
            r'\[TODO\]',
            r'\[TBD\]',
            r'\[INSERT\s+\w+\]',
            r'\[FILL\s+IN\]',
        ]

        placeholders_found = []
        for pattern in placeholder_patterns:
            matches = re.findall(pattern, self.content, re.IGNORECASE)
            placeholders_found.extend(matches)

        if placeholders_found:
            self._add_result(
                category="Quality",
                check="No placeholders",
                passed=False,
                message=f"Found {len(placeholders_found)} placeholder(s): {set(placeholders_found[:5])}",
                severity="error"
            )
        else:
            self._add_result(
                category="Quality",
                check="No placeholders",
                passed=True,
                message="No placeholders found",
                severity="info"
            )

        # Check heading hierarchy
        h1_count = len(re.findall(r'^# ', self.content, re.MULTILINE))
        h2_count = len(re.findall(r'^## ', self.content, re.MULTILINE))
        h3_count = len(re.findall(r'^### ', self.content, re.MULTILINE))

        if h1_count >= 1 and h2_count >= 8:
            self._add_result(
                category="Quality",
                check="Heading structure",
                passed=True,
                message=f"Good structure: {h1_count} H1, {h2_count} H2, {h3_count} H3",
                severity="info"
            )
        else:
            self._add_result(
                category="Quality",
                check="Heading structure",
                passed=False,
                message=f"Missing headings: {h1_count} H1, {h2_count} H2 (need 8+ sections)",
                severity="warning"
            )

        # Check for table of contents
        if 'table of contents' in self.content.lower() or '[table of contents]' in self.content.lower():
            self._add_result(
                category="Quality",
                check="Table of contents",
                passed=True,
                message="Table of contents present",
                severity="info"
            )
        else:
            self._add_result(
                category="Quality",
                check="Table of contents",
                passed=False,
                message="No table of contents found (recommended)",
                severity="warning"
            )

    def check_integration(self):
        """Check README integration requirements."""
        # These are manual checks - just add info reminders
        self._add_result(
            category="Integration",
            check="README update",
            passed=True,
            message="Manual check required: README.md should feature product overview first",
            severity="info"
        )

        self._add_result(
            category="Integration",
            check="Document versions table",
            passed=True,
            message="Manual check required: Document versions table should include product overview",
            severity="info"
        )

        # Check file naming convention
        filename = self.file_path.name
        expected_pattern = re.compile(r'.*-Product-Overview\.md$', re.IGNORECASE)

        if expected_pattern.match(filename):
            self._add_result(
                category="Integration",
                check="File naming convention",
                passed=True,
                message=f"Filename follows convention: {filename}",
                severity="info"
            )
        else:
            self._add_result(
                category="Integration",
                check="File naming convention",
                passed=False,
                message=f"Filename should end with '-Product-Overview.md': {filename}",
                severity="warning"
            )

    def _add_result(self, category: str, check: str, passed: bool, message: str, severity: str):
        """Add a validation result."""
        self.results.append(ValidationResult(
            category=category,
            check=check,
            passed=passed,
            message=message,
            severity=severity
        ))

    def format_markdown(self) -> str:
        """Format results as markdown."""
        lines = [
            "# Product Overview Validation Report",
            "",
            f"**File**: {self.file_path.name}",
            "",
            "## Summary",
            "",
            f"- **Total Checks**: {self.summary.total_checks}",
            f"- **Passed**: {self.summary.passed}",
            f"- **Failed**: {self.summary.failed}",
            f"- **Errors**: {self.summary.errors}",
            f"- **Warnings**: {self.summary.warnings}",
            f"- **Valid**: {'Yes' if self.summary.is_valid else 'No'}",
            "",
            "## Results",
            "",
            "| Category | Check | Status | Message |",
            "|----------|-------|--------|---------|",
        ]

        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            icon = "v" if result.passed else "x"
            lines.append(f"| {result.category} | {result.check} | {icon} {status} | {result.message} |")

        return "\n".join(lines)

    def format_json(self) -> str:
        """Format results as JSON."""
        import json
        return json.dumps({
            "file": str(self.file_path),
            "summary": {
                "total_checks": self.summary.total_checks,
                "passed": self.summary.passed,
                "failed": self.summary.failed,
                "errors": self.summary.errors,
                "warnings": self.summary.warnings,
                "is_valid": self.summary.is_valid
            },
            "results": [
                {
                    "category": r.category,
                    "check": r.check,
                    "passed": r.passed,
                    "message": r.message,
                    "severity": r.severity
                }
                for r in self.results
            ]
        }, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Validate product overview document",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "file_path",
        help="Path to product overview document"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings (not just errors)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format (default: markdown)"
    )

    args = parser.parse_args()

    # Validate file exists
    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"Error: File not found: {args.file_path}", file=sys.stderr)
        sys.exit(2)

    # Run validation
    validator = ProductOverviewValidator(file_path)
    validator.validate_all()

    # Output results
    if args.format == "json":
        print(validator.format_json())
    else:
        print(validator.format_markdown())

    # Determine exit code
    if not validator.summary.is_valid:
        sys.exit(2)  # Errors present
    elif args.strict and validator.summary.warnings > 0:
        sys.exit(1)  # Warnings in strict mode
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
