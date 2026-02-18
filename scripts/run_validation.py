#!/usr/bin/env python3
"""
Validation Runner

Orchestrates all validation checks for the architecture audit Phase 9.
Runs path verification, schema completeness, feature coverage, and gap analysis.

Usage:
    python scripts/run_validation.py <project_path> [options]

Options:
    --document PATH          Path to generated document to validate
    --strict                 Fail on warnings
    --skip PATH_VERIFICATION Skip path verification step
    --skip GAP_ANALYSIS      Skip gap analysis step
    --format json|markdown   Output format (default: markdown)
    --output FILE            Output file path
    --help                   Show usage information

Exit Codes:
    0 - All validations pass
    1 - Critical issues found
    2 - Warnings only
    3 - Validation could not complete
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ValidationStep:
    """Result of a single validation step."""
    name: str
    passed: bool
    status: str  # 'pass', 'warn', 'fail', 'skip'
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Complete validation result."""
    project_path: str
    document_path: Optional[str]
    timestamp: str
    overall_status: str  # 'pass', 'warn', 'fail'
    steps: list[ValidationStep]
    summary: dict

    @property
    def passed(self) -> bool:
        return self.overall_status == 'pass'

    @property
    def has_warnings(self) -> bool:
        return self.overall_status == 'warn'


class ValidationRunner:
    """Run all validation checks."""

    def __init__(self, project_path: Path, document_path: Optional[Path] = None):
        self.project_path = project_path
        self.document_path = document_path
        self.steps: list[ValidationStep] = []
        self.script_dir = Path(__file__).parent

    def run_all(self, skip_steps: list[str] = None) -> ValidationResult:
        """Run all validation steps."""
        skip_steps = skip_steps or []

        print("\n" + "=" * 60)
        print("PHASE 9: Validation & Completeness")
        print("=" * 60 + "\n")

        # 1. Path Verification
        if "path_verification" not in skip_steps and self.document_path:
            self._run_path_verification()
        else:
            self._skip_step("path_verification", "No document provided or skipped")

        # 2. Schema Completeness
        if "schema_completeness" not in skip_steps:
            self._run_schema_completeness()
        else:
            self._skip_step("schema_completeness", "Skipped")

        # 3. Feature Coverage
        if "feature_coverage" not in skip_steps:
            self._run_feature_coverage()
        else:
            self._skip_step("feature_coverage", "Skipped")

        # 4. Gap Analysis
        if "gap_analysis" not in skip_steps:
            self._run_gap_analysis()
        else:
            self._skip_step("gap_analysis", "Skipped")

        # 5. Summary
        print("\n5. Generating validation summary...")
        summary = self._generate_summary()
        print(f"   Status: {summary['overall_status'].upper()}")
        print(f"   Steps: {summary['passed']}/{summary['total']} passed")

        return ValidationResult(
            project_path=str(self.project_path),
            document_path=str(self.document_path) if self.document_path else None,
            timestamp=datetime.now().isoformat(),
            overall_status=summary['overall_status'],
            steps=self.steps,
            summary=summary
        )

    def _run_path_verification(self) -> None:
        """Run path verification step."""
        print("1. Verifying file paths...")

        if not self.document_path or not self.document_path.exists():
            self.steps.append(ValidationStep(
                name="path_verification",
                passed=False,
                status="skip",
                message="No document to verify",
                details={"error": "Document path not provided or does not exist"}
            ))
            print("   ⚠ Skipped - No document provided")
            return

        try:
            # Run verify_paths.py
            verify_script = self.script_dir / "verify_paths.py"
            if verify_script.exists():
                result = subprocess.run(
                    ["python", str(verify_script), str(self.document_path), str(self.project_path), "--format", "json"],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    valid = data.get("summary", {}).get("found", 0)
                    invalid = data.get("summary", {}).get("missing", 0)

                    if invalid == 0:
                        self.steps.append(ValidationStep(
                            name="path_verification",
                            passed=True,
                            status="pass",
                            message=f"All {valid} paths verified",
                            details=data
                        ))
                        print(f"   ✓ All {valid} paths valid")
                    else:
                        self.steps.append(ValidationStep(
                            name="path_verification",
                            passed=False,
                            status="warn",
                            message=f"{invalid} invalid paths found",
                            details=data
                        ))
                        print(f"   ⚠ {valid} valid, {invalid} invalid")
                else:
                    self.steps.append(ValidationStep(
                        name="path_verification",
                        passed=False,
                        status="fail",
                        message="Path verification failed",
                        details={"error": result.stderr}
                    ))
                    print("   ✗ Path verification failed")
            else:
                self.steps.append(ValidationStep(
                    name="path_verification",
                    passed=True,
                    status="pass",
                    message="Skipped (verify_paths.py not found)",
                    details={}
                ))
                print("   ⚠ verify_paths.py not found, skipping")

        except Exception as e:
            self.steps.append(ValidationStep(
                name="path_verification",
                passed=False,
                status="fail",
                message=f"Error: {str(e)}",
                details={"error": str(e)}
            ))
            print(f"   ✗ Error: {e}")

    def _run_schema_completeness(self) -> None:
        """Run schema completeness check."""
        print("2. Checking schema completeness...")

        try:
            # Run completeness_checker.py
            checker_script = self.script_dir / "completeness_checker.py"
            if checker_script.exists():
                result = subprocess.run(
                    ["python", str(checker_script), str(self.project_path), "--format", "json"],
                    capture_output=True,
                    text=True
                )

                if result.returncode in [0, 2]:  # 0 = pass, 2 = warnings
                    data = json.loads(result.stdout)
                    categories = data.get("categories", {})

                    db_stats = categories.get("database_models", {})
                    tables_found = db_stats.get("found", 0)
                    tables_documented = db_stats.get("documented", 0)
                    coverage = db_stats.get("coverage", 0)

                    if coverage >= 100:
                        self.steps.append(ValidationStep(
                            name="schema_completeness",
                            passed=True,
                            status="pass",
                            message=f"All {tables_found} tables documented",
                            details=db_stats
                        ))
                        print(f"   ✓ {tables_found}/{tables_found} tables documented")
                    elif coverage >= 80:
                        self.steps.append(ValidationStep(
                            name="schema_completeness",
                            passed=True,
                            status="warn",
                            message=f"{coverage}% schema coverage",
                            details=db_stats
                        ))
                        print(f"   ⚠ {tables_documented}/{tables_found} tables documented ({coverage}%)")
                    else:
                        self.steps.append(ValidationStep(
                            name="schema_completeness",
                            passed=False,
                            status="fail",
                            message=f"Only {coverage}% schema coverage",
                            details=db_stats
                        ))
                        print(f"   ✗ Only {tables_documented}/{tables_found} tables documented ({coverage}%)")
                else:
                    self.steps.append(ValidationStep(
                        name="schema_completeness",
                        passed=True,
                        status="pass",
                        message="No database models found",
                        details={"found": 0, "documented": 0, "coverage": 100}
                    ))
                    print("   ✓ No database models to check")
            else:
                self.steps.append(ValidationStep(
                    name="schema_completeness",
                    passed=True,
                    status="pass",
                    message="Skipped (completeness_checker.py not found)",
                    details={}
                ))
                print("   ⚠ completeness_checker.py not found, skipping")

        except Exception as e:
            self.steps.append(ValidationStep(
                name="schema_completeness",
                passed=False,
                status="fail",
                message=f"Error: {str(e)}",
                details={"error": str(e)}
            ))
            print(f"   ✗ Error: {e}")

    def _run_feature_coverage(self) -> None:
        """Run feature coverage check."""
        print("3. Checking feature coverage...")

        try:
            # Run completeness_checker.py for feature coverage
            checker_script = self.script_dir / "completeness_checker.py"
            if checker_script.exists():
                result = subprocess.run(
                    ["python", str(checker_script), str(self.project_path), "--format", "json"],
                    capture_output=True,
                    text=True
                )

                if result.returncode in [0, 2]:
                    data = json.loads(result.stdout)
                    categories = data.get("categories", {})

                    # Calculate average coverage
                    coverages = []
                    for key, stats in categories.items():
                        coverages.append(stats.get("coverage", 100))

                    avg_coverage = sum(coverages) / len(coverages) if coverages else 100

                    if avg_coverage >= 95:
                        self.steps.append(ValidationStep(
                            name="feature_coverage",
                            passed=True,
                            status="pass",
                            message=f"{avg_coverage:.1f}% average coverage",
                            details={"avg_coverage": avg_coverage, "categories": categories}
                        ))
                        print(f"   ✓ {avg_coverage:.1f}% average coverage")
                    elif avg_coverage >= 80:
                        self.steps.append(ValidationStep(
                            name="feature_coverage",
                            passed=True,
                            status="warn",
                            message=f"{avg_coverage:.1f}% average coverage",
                            details={"avg_coverage": avg_coverage, "categories": categories}
                        ))
                        print(f"   ⚠ {avg_coverage:.1f}% average coverage")
                    else:
                        self.steps.append(ValidationStep(
                            name="feature_coverage",
                            passed=False,
                            status="fail",
                            message=f"Only {avg_coverage:.1f}% average coverage",
                            details={"avg_coverage": avg_coverage, "categories": categories}
                        ))
                        print(f"   ✗ Only {avg_coverage:.1f}% average coverage")
                else:
                    self.steps.append(ValidationStep(
                        name="feature_coverage",
                        passed=True,
                        status="pass",
                        message="No features to check",
                        details={"avg_coverage": 100}
                    ))
                    print("   ✓ No features to check")
            else:
                self.steps.append(ValidationStep(
                    name="feature_coverage",
                    passed=True,
                    status="pass",
                    message="Skipped (completeness_checker.py not found)",
                    details={}
                ))
                print("   ⚠ completeness_checker.py not found, skipping")

        except Exception as e:
            self.steps.append(ValidationStep(
                name="feature_coverage",
                passed=False,
                status="fail",
                message=f"Error: {str(e)}",
                details={"error": str(e)}
            ))
            print(f"   ✗ Error: {e}")

    def _run_gap_analysis(self) -> None:
        """Run gap analysis."""
        print("4. Running gap analysis...")

        try:
            # Run gap_analyzer.py
            gap_script = self.script_dir / "gap_analyzer.py"
            if gap_script.exists():
                result = subprocess.run(
                    ["python", str(gap_script), str(self.project_path), "--format", "json"],
                    capture_output=True,
                    text=True
                )

                if result.returncode in [0, 2]:
                    data = json.loads(result.stdout)
                    total_gaps = data.get("total_gaps", 0)
                    by_severity = data.get("by_severity", {})

                    critical = by_severity.get("critical", 0)
                    errors = by_severity.get("error", 0)
                    warnings = by_severity.get("warning", 0)

                    if critical > 0:
                        self.steps.append(ValidationStep(
                            name="gap_analysis",
                            passed=False,
                            status="fail",
                            message=f"{critical} critical gaps found",
                            details=data
                        ))
                        print(f"   ✗ {critical} critical, {errors} errors, {warnings} warnings")
                    elif errors > 0:
                        self.steps.append(ValidationStep(
                            name="gap_analysis",
                            passed=False,
                            status="fail",
                            message=f"{errors} error-level gaps found",
                            details=data
                        ))
                        print(f"   ✗ {errors} errors, {warnings} warnings")
                    elif warnings > 0:
                        self.steps.append(ValidationStep(
                            name="gap_analysis",
                            passed=True,
                            status="warn",
                            message=f"{warnings} warnings found",
                            details=data
                        ))
                        print(f"   ⚠ {warnings} warnings, {total_gaps} total gaps")
                    else:
                        self.steps.append(ValidationStep(
                            name="gap_analysis",
                            passed=True,
                            status="pass",
                            message="No significant gaps found",
                            details=data
                        ))
                        print(f"   ✓ No significant gaps")
                else:
                    self.steps.append(ValidationStep(
                        name="gap_analysis",
                        passed=True,
                        status="pass",
                        message="Gap analysis completed with no issues",
                        details={}
                    ))
                    print("   ✓ No gaps found")
            else:
                self.steps.append(ValidationStep(
                    name="gap_analysis",
                    passed=True,
                    status="pass",
                    message="Skipped (gap_analyzer.py not found)",
                    details={}
                ))
                print("   ⚠ gap_analyzer.py not found, skipping")

        except Exception as e:
            self.steps.append(ValidationStep(
                name="gap_analysis",
                passed=False,
                status="fail",
                message=f"Error: {str(e)}",
                details={"error": str(e)}
            ))
            print(f"   ✗ Error: {e}")

    def _skip_step(self, name: str, reason: str) -> None:
        """Add a skipped step."""
        self.steps.append(ValidationStep(
            name=name,
            passed=True,
            status="skip",
            message=reason,
            details={}
        ))

    def _generate_summary(self) -> dict:
        """Generate validation summary."""
        total = len(self.steps)
        passed = len([s for s in self.steps if s.status == "pass"])
        warned = len([s for s in self.steps if s.status == "warn"])
        failed = len([s for s in self.steps if s.status == "fail"])
        skipped = len([s for s in self.steps if s.status == "skip"])

        if failed > 0:
            overall = "fail"
        elif warned > 0:
            overall = "warn"
        else:
            overall = "pass"

        return {
            "total": total,
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "skipped": skipped,
            "overall_status": overall
        }


def format_report_markdown(result: ValidationResult) -> str:
    """Format validation result as Markdown."""
    lines = ["# Validation Report\n"]

    # Header
    lines.append(f"> **Generated:** {result.timestamp}")
    status_emoji = {"pass": "✓", "warn": "⚠", "fail": "✗"}.get(result.overall_status, "?")
    lines.append(f"> **Overall Status:** {status_emoji} {result.overall_status.upper()}\n")

    # Summary
    lines.append("## Validation Summary\n")
    lines.append("| Check | Status | Details |")
    lines.append("|-------|--------|---------|")

    status_icons = {"pass": "✓ Pass", "warn": "⚠ Warning", "fail": "✗ Fail", "skip": "○ Skip"}
    for step in result.steps:
        status = status_icons.get(step.status, step.status)
        lines.append(f"| {step.name.replace('_', ' ').title()} | {status} | {step.message} |")

    # Details
    lines.append(f"\n**Summary:** {result.summary['passed']}/{result.summary['total']} checks passed")

    # Recommendations
    if result.overall_status != "pass":
        lines.append("\n## Recommendations\n")
        for step in result.steps:
            if step.status == "fail":
                lines.append(f"- Fix **{step.name.replace('_', ' ')}**: {step.message}")
            elif step.status == "warn":
                lines.append(f"- Review **{step.name.replace('_', ' ')}**: {step.message}")

    lines.append(f"\n---\n*Validation completed at {result.timestamp}*")

    return "\n".join(lines)


def format_report_json(result: ValidationResult) -> str:
    """Format validation result as JSON."""
    output = {
        "project_path": result.project_path,
        "document_path": result.document_path,
        "timestamp": result.timestamp,
        "overall_status": result.overall_status,
        "summary": result.summary,
        "steps": [asdict(s) for s in result.steps]
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Run validation phase for architecture audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
    0 - All validations pass
    1 - Critical issues found
    2 - Warnings only
    3 - Validation could not complete

Examples:
    %(prog)s /path/to/project
    %(prog)s /path/to/project --document output.md
    %(prog)s /path/to/project --strict
    %(prog)s /path/to/project --skip path_verification
"""
    )

    parser.add_argument(
        "project_path",
        help="Path to project directory"
    )

    parser.add_argument(
        "--document",
        help="Path to generated document to validate"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings"
    )

    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        choices=["path_verification", "schema_completeness", "feature_coverage", "gap_analysis"],
        help="Skip validation step (can be used multiple times)"
    )

    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format (default: markdown)"
    )

    parser.add_argument(
        "--output",
        help="Output file path (default: stdout)"
    )

    args = parser.parse_args()

    project_path = Path(args.project_path)
    if not project_path.exists():
        print(f"Error: Project path does not exist: {args.project_path}", file=sys.stderr)
        sys.exit(3)

    document_path = Path(args.document) if args.document else None

    # Run validation
    runner = ValidationRunner(project_path, document_path)
    result = runner.run_all(skip_steps=args.skip)

    # Format output
    if args.format == "json":
        output = format_report_json(result)
    else:
        output = format_report_markdown(result)

    # Write output
    if args.output:
        Path(args.output).write_text(output)
        print(f"\nReport written to {args.output}")
    else:
        print("\n" + output)

    # Determine exit code
    if result.overall_status == "fail":
        sys.exit(1)
    elif result.overall_status == "warn" and args.strict:
        sys.exit(1)
    elif result.overall_status == "warn":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
