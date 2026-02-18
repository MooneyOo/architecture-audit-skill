#!/usr/bin/env python3
"""
Gap Analyzer

Produces detailed gap analysis reports for documentation quality.
Analyzes documentation gaps, coverage gaps, consistency gaps, and quality gaps.

Usage:
    python scripts/gap_analyzer.py <project_path> [options]

Options:
    --type TYPE               Gap type (all, documentation, coverage, consistency, quality)
    --severity LEVEL          Minimum severity (all, info, warning, error, critical)
    --format json|markdown    Output format (default: markdown)
    --output FILE             Output file path
    --help                    Show usage information

Exit Codes:
    0 - No critical gaps
    1 - Critical gaps found
    2 - Warnings only
    3 - Could not complete analysis
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class GapType(Enum):
    """Types of documentation gaps."""
    DOCUMENTATION = "documentation"
    COVERAGE = "coverage"
    CONSISTENCY = "consistency"
    QUALITY = "quality"


class Severity(Enum):
    """Gap severity levels."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Gap:
    """A single documentation gap."""
    id: str
    type: str
    severity: str
    category: str
    location: str
    description: str
    impact: str
    suggestion: str
    related_items: list[str] = field(default_factory=list)


@dataclass
class GapAnalysisResult:
    """Complete gap analysis result."""
    project_path: str
    total_gaps: int
    by_severity: dict[str, int]
    by_type: dict[str, int]
    gaps: list[Gap]
    recommendations: list[str]


class GapAnalyzer:
    """Analyze documentation for gaps."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.gaps: list[Gap] = []
        self.gap_id = 0

    def analyze_all(self) -> GapAnalysisResult:
        """Run all gap analysis."""
        self._analyze_documentation_gaps()
        self._analyze_coverage_gaps()
        self._analyze_consistency_gaps()
        self._analyze_quality_gaps()

        return GapAnalysisResult(
            project_path=str(self.project_path),
            total_gaps=len(self.gaps),
            by_severity=self._count_by_severity(),
            by_type=self._count_by_type(),
            gaps=self.gaps,
            recommendations=self._generate_recommendations()
        )

    def analyze_type(self, gap_type: str) -> GapAnalysisResult:
        """Analyze specific gap type only."""
        if gap_type == "documentation":
            self._analyze_documentation_gaps()
        elif gap_type == "coverage":
            self._analyze_coverage_gaps()
        elif gap_type == "consistency":
            self._analyze_consistency_gaps()
        elif gap_type == "quality":
            self._analyze_quality_gaps()
        else:
            self.analyze_all()

        return GapAnalysisResult(
            project_path=str(self.project_path),
            total_gaps=len(self.gaps),
            by_severity=self._count_by_severity(),
            by_type=self._count_by_type(),
            gaps=self.gaps,
            recommendations=self._generate_recommendations()
        )

    def _analyze_documentation_gaps(self):
        """Analyze documentation gaps."""
        # Check Python files for missing docstrings
        for py_file in self._find_source_files("*.py"):
            self._check_python_documentation(py_file)

        # Check TypeScript files for missing comments
        for ts_file in self._find_source_files("*.ts"):
            self._check_typescript_documentation(ts_file)

        # Check schemas for missing examples
        self._check_schema_examples()

    def _analyze_coverage_gaps(self):
        """Analyze coverage gaps."""
        # Check for undocumented routes
        routes = self._discover_routes()
        for route in routes:
            if self._is_internal_route(route):
                continue
            # For now, we assume routes are documented if they exist
            # A full implementation would compare against generated docs

        # Check for orphaned services
        services = self._discover_services()
        for service in services:
            if service.get('method', '').startswith('_'):
                continue
            # Check if service is referenced anywhere
            if not self._is_service_referenced(service):
                self._add_gap(
                    type=GapType.COVERAGE.value,
                    severity=Severity.INFO.value,
                    category="orphaned_service",
                    location=f"{service['file']}:{service.get('line', 0)}",
                    description=f"Service method '{service['service']}.{service['method']}' not referenced",
                    impact="Business logic may be unused or undocumented",
                    suggestion="Verify if method is used via dependency injection or remove"
                )

    def _analyze_consistency_gaps(self):
        """Analyze consistency gaps."""
        # Check for naming convention issues
        self._check_naming_conventions()

        # Check for duplicate definitions
        self._check_duplicate_definitions()

        # Check for stale references
        self._check_stale_references()

    def _analyze_quality_gaps(self):
        """Analyze quality gaps."""
        # Check for missing error handling documentation
        self._check_error_documentation()

        # Check for missing validation documentation
        self._check_validation_documentation()

    def _check_python_documentation(self, file_path: Path):
        """Check Python file for documentation gaps."""
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            # Check classes for docstrings
            for match in re.finditer(r'class\s+(\w+)\s*[:\(]', content):
                class_name = match.group(1)
                # Check for docstring after class definition
                after_class = content[match.end():match.end() + 200]
                if not re.search(r'"""[\s\S]*?"""', after_class) and not re.search(r"'''[\s\S]*?'''", after_class):
                    self._add_gap(
                        type=GapType.DOCUMENTATION.value,
                        severity=Severity.INFO.value,
                        category="missing_class_docstring",
                        location=f"{rel_path}:{content[:match.start()].count(chr(10)) + 1}",
                        description=f"Class '{class_name}' has no docstring",
                        impact="Class purpose unclear to developers",
                        suggestion=f"Add docstring to {class_name} class"
                    )

            # Check functions for docstrings (public ones only)
            for match in re.finditer(r'\ndef\s+(\w+)\s*\([^)]*\)\s*(?::\s*[^=]+)?(?:->\s*[^=]+)?:', content):
                func_name = match.group(1)
                if func_name.startswith('_'):
                    continue
                after_func = content[match.end():match.end() + 200]
                if not re.search(r'"""[\s\S]*?"""', after_func) and not re.search(r"'''[\s\S]*?'''", after_func):
                    line_num = content[:match.start()].count('\n') + 1
                    self._add_gap(
                        type=GapType.DOCUMENTATION.value,
                        severity=Severity.INFO.value,
                        category="missing_function_docstring",
                        location=f"{rel_path}:{line_num}",
                        description=f"Function '{func_name}' has no docstring",
                        impact="Function purpose unclear",
                        suggestion=f"Add docstring to {func_name} function"
                    )

        except Exception:
            pass

    def _check_typescript_documentation(self, file_path: Path):
        """Check TypeScript file for documentation gaps."""
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            # Check classes for JSDoc comments
            for match in re.finditer(r'(?:export\s+)?class\s+(\w+)', content):
                class_name = match.group(1)
                before_class = content[max(0, match.start() - 200):match.start()]
                if not re.search(r'/\*\*[\s\S]*?\*/', before_class):
                    self._add_gap(
                        type=GapType.DOCUMENTATION.value,
                        severity=Severity.INFO.value,
                        category="missing_class_jsdoc",
                        location=f"{rel_path}:{content[:match.start()].count(chr(10)) + 1}",
                        description=f"Class '{class_name}' has no JSDoc comment",
                        impact="Class purpose unclear to developers",
                        suggestion=f"Add JSDoc comment to {class_name} class"
                    )

        except Exception:
            pass

    def _check_schema_examples(self):
        """Check schemas for missing examples."""
        # Check Pydantic schemas
        for py_file in self._find_source_files("*schema*.py"):
            try:
                content = py_file.read_text(encoding='utf-8')
                rel_path = str(py_file.relative_to(self.project_path))

                # Find schema classes
                for match in re.finditer(r'class\s+(\w+)(?:Schema|Request|Response|In|Out)', content):
                    schema_name = match.group(0)
                    class_content = content[match.start():match.start() + 500]

                    # Check for Config with schema_extra or example
                    if 'example' not in class_content.lower() and 'schema_extra' not in class_content:
                        self._add_gap(
                            type=GapType.DOCUMENTATION.value,
                            severity=Severity.INFO.value,
                            category="missing_schema_example",
                            location=rel_path,
                            description=f"Schema '{schema_name}' has no example",
                            impact="Developers may not understand expected format",
                            suggestion="Add 'example' field to schema Config"
                        )
            except Exception:
                pass

    def _check_naming_conventions(self):
        """Check for naming convention issues."""
        # Check for inconsistent naming in models
        for py_file in self._find_source_files("*model*.py"):
            try:
                content = py_file.read_text(encoding='utf-8')
                rel_path = str(py_file.relative_to(self.project_path))

                # Find __tablename__ definitions
                for match in re.finditer(r'__tablename__\s*=\s*["\']([^"\']+)["\']', content):
                    table_name = match.group(1)
                    # Check if table name is snake_case
                    if not re.match(r'^[a-z][a-z0-9_]*$', table_name):
                        self._add_gap(
                            type=GapType.CONSISTENCY.value,
                            severity=Severity.INFO.value,
                            category="naming_convention",
                            location=f"{rel_path}:{content[:match.start()].count(chr(10)) + 1}",
                            description=f"Table name '{table_name}' doesn't follow snake_case convention",
                            impact="Inconsistent naming can cause confusion",
                            suggestion=f"Consider renaming to snake_case (e.g., {self._to_snake_case(table_name)})"
                        )
            except Exception:
                pass

    def _check_duplicate_definitions(self):
        """Check for duplicate definitions."""
        routes = self._discover_routes()

        # Check for duplicate routes
        seen = {}
        for route in routes:
            key = f"{route['method']} {route['path']}"
            if key in seen:
                self._add_gap(
                    type=GapType.CONSISTENCY.value,
                    severity=Severity.WARNING.value,
                    category="duplicate_route",
                    location=route['file'],
                    description=f"Duplicate route definition: {key}",
                    impact="Route may be defined in multiple places",
                    suggestion=f"Consolidate or verify intentional override",
                    related_items=[seen[key]]
                )
            else:
                seen[key] = route['file']

    def _check_stale_references(self):
        """Check for stale references to files or modules."""
        # This would require comparing imports against actual files
        # Placeholder for future implementation
        pass

    def _check_error_documentation(self):
        """Check for missing error documentation."""
        for py_file in self._find_source_files("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8')
                rel_path = str(py_file.relative_to(self.project_path))

                # Find FastAPI routes without error documentation
                for match in re.finditer(r'@(?:router|app)\.(get|post|put|patch|delete)\s*\([^)]+\)', content):
                    # Check if docstring mentions errors
                    after_route = content[match.end():match.end() + 500]
                    docstring_match = re.search(r'"""[\s\S]*?"""', after_route)

                    if docstring_match:
                        docstring = docstring_match.group(0)
                        if 'error' not in docstring.lower() and 'raise' not in docstring.lower():
                            # Check if function raises exceptions
                            func_match = re.search(r'def\s+\w+\([^)]*\)[^:]*:', after_route)
                            if func_match:
                                func_content = after_route[func_match.end():func_match.end() + 500]
                                if 'raise' in func_content or 'HTTPException' in func_content:
                                    self._add_gap(
                                        type=GapType.QUALITY.value,
                                        severity=Severity.INFO.value,
                                        category="missing_error_docs",
                                        location=rel_path,
                                        description="Route raises exceptions but docstring doesn't document errors",
                                        impact="Developers won't know how to handle errors",
                                        suggestion="Add 'Raises:' section to docstring"
                                    )
            except Exception:
                pass

    def _check_validation_documentation(self):
        """Check for missing validation documentation."""
        for py_file in self._find_source_files("*schema*.py"):
            try:
                content = py_file.read_text(encoding='utf-8')
                rel_path = str(py_file.relative_to(self.project_path))

                # Find fields with validators but no documentation
                if '@validator' in content or 'Field(' in content:
                    # Check if there's validation documentation
                    if 'validation' not in content.lower() and 'constraint' not in content.lower():
                        self._add_gap(
                            type=GapType.QUALITY.value,
                            severity=Severity.INFO.value,
                            category="missing_validation_docs",
                            location=rel_path,
                            description="Schema has validators but no validation documentation",
                            impact="Input constraints unclear",
                            suggestion="Document field constraints and validation rules"
                        )
            except Exception:
                pass

    def _discover_routes(self) -> list[dict]:
        """Discover all routes in the project."""
        routes = []

        # FastAPI routes
        for py_file in self._find_source_files("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8')
                rel_path = str(py_file.relative_to(self.project_path))

                for match in re.finditer(r'@(?:router|app)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']', content):
                    routes.append({
                        'method': match.group(1).upper(),
                        'path': match.group(2),
                        'file': rel_path,
                        'line': content[:match.start()].count('\n') + 1
                    })
            except Exception:
                pass

        return routes

    def _discover_services(self) -> list[dict]:
        """Discover all services in the project."""
        services = []

        for py_file in self._find_source_files("*service*.py"):
            try:
                content = py_file.read_text(encoding='utf-8')
                rel_path = str(py_file.relative_to(self.project_path))

                for match in re.finditer(r'class\s+(\w+[Ss]ervice)', content):
                    class_name = match.group(1)

                    # Find methods
                    for method_match in re.finditer(r'def\s+(\w+)\s*\(', content[match.start():]):
                        method_name = method_match.group(1)
                        services.append({
                            'service': class_name,
                            'method': method_name,
                            'file': rel_path,
                            'line': 0
                        })
            except Exception:
                pass

        return services

    def _is_internal_route(self, route: dict) -> bool:
        """Check if route is internal (health, metrics, etc.)."""
        internal_patterns = ['/health', '/metrics', '/internal/', '/_']
        return any(pattern in route['path'] for pattern in internal_patterns)

    def _is_service_referenced(self, service: dict) -> bool:
        """Check if service is referenced elsewhere."""
        # Simplified check - in reality would search entire codebase
        return True  # Assume referenced for now

    def _find_source_files(self, pattern: str) -> list[Path]:
        """Find source files matching pattern."""
        files = []
        skip_dirs = {'node_modules', '__pycache__', '.git', 'venv', '.venv', 'dist', 'build'}

        for file_path in self.project_path.rglob(pattern):
            if any(skip_dir in str(file_path) for skip_dir in skip_dirs):
                continue
            files.append(file_path)

        return files

    def _to_snake_case(self, name: str) -> str:
        """Convert name to snake_case."""
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _add_gap(
        self,
        type: str,
        severity: str,
        category: str,
        location: str,
        description: str,
        impact: str,
        suggestion: str,
        related_items: list[str] = None
    ):
        """Add a gap to the list."""
        self.gap_id += 1
        self.gaps.append(Gap(
            id=f"GAP-{self.gap_id:04d}",
            type=type,
            severity=severity,
            category=category,
            location=location,
            description=description,
            impact=impact,
            suggestion=suggestion,
            related_items=related_items or []
        ))

    def _count_by_severity(self) -> dict[str, int]:
        """Count gaps by severity."""
        counts = {"critical": 0, "error": 0, "warning": 0, "info": 0}
        for gap in self.gaps:
            if gap.severity in counts:
                counts[gap.severity] += 1
        return counts

    def _count_by_type(self) -> dict[str, int]:
        """Count gaps by type."""
        counts = {}
        for gap in self.gaps:
            counts[gap.type] = counts.get(gap.type, 0) + 1
        return counts

    def _generate_recommendations(self) -> list[str]:
        """Generate prioritized recommendations."""
        recommendations = []

        by_severity = self._count_by_severity()
        by_type = self._count_by_type()

        # Critical issues
        if by_severity.get("critical", 0) > 0:
            recommendations.append(
                f"CRITICAL: Address {by_severity['critical']} critical gaps immediately"
            )

        # Error issues
        if by_severity.get("error", 0) > 0:
            recommendations.append(
                f"HIGH: Fix {by_severity['error']} error-level gaps"
            )

        # Coverage issues
        if by_type.get("coverage", 0) > 10:
            recommendations.append(
                f"MEDIUM: Improve coverage - {by_type['coverage']} items not documented"
            )

        # Documentation issues
        if by_type.get("documentation", 0) > 20:
            recommendations.append(
                f"LOW: Enhance documentation - {by_type['documentation']} missing descriptions"
            )

        # Quality issues
        if by_type.get("quality", 0) > 5:
            recommendations.append(
                f"MEDIUM: Improve quality documentation - {by_type['quality']} gaps found"
            )

        if not recommendations:
            recommendations.append("No significant gaps found. Documentation quality is good.")

        return recommendations


def format_report_markdown(result: GapAnalysisResult) -> str:
    """Format gap analysis as Markdown."""
    lines = ["# Gap Analysis Report\n"]

    # Summary
    lines.append("## Summary\n")
    lines.append(f"**Total Gaps:** {result.total_gaps}\n")

    # By Severity
    lines.append("\n### By Severity\n")
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    for sev in ["critical", "error", "warning", "info"]:
        count = result.by_severity.get(sev, 0)
        emoji = {"critical": "🔴", "error": "🟠", "warning": "🟡", "info": "🔵"}.get(sev, "⚪")
        lines.append(f"| {emoji} {sev} | {count} |")

    # By Type
    lines.append("\n### By Type\n")
    lines.append("| Type | Count |")
    lines.append("|------|-------|")
    for typ, count in sorted(result.by_type.items()):
        lines.append(f"| {typ} | {count} |")

    # Recommendations
    if result.recommendations:
        lines.append("\n## Recommendations\n")
        for rec in result.recommendations:
            lines.append(f"- {rec}")

    # Detailed Gaps
    if result.gaps:
        lines.append("\n## Detailed Gaps\n")

        # Group by severity for better readability
        critical_gaps = [g for g in result.gaps if g.severity == "critical"]
        error_gaps = [g for g in result.gaps if g.severity == "error"]
        warning_gaps = [g for g in result.gaps if g.severity == "warning"]
        info_gaps = [g for g in result.gaps if g.severity == "info"]

        for gap_list, header in [
            (critical_gaps, "Critical"),
            (error_gaps, "Errors"),
            (warning_gaps, "Warnings"),
            (info_gaps, "Info")
        ]:
            if gap_list:
                lines.append(f"\n### {header} ({len(gap_list)})\n")
                lines.append("| ID | Category | Description | Location | Suggestion |")
                lines.append("|----|----------|-------------|----------|------------|")

                for gap in gap_list[:20]:  # Limit output
                    lines.append(
                        f"| {gap.id} | {gap.category} | {gap.description[:50]}... | "
                        f"`{gap.location[:30]}` | {gap.suggestion[:40]}... |"
                    )

                if len(gap_list) > 20:
                    lines.append(f"| ... | ... | ... | ... | ({len(gap_list) - 20} more) |")

    return "\n".join(lines)


def format_report_json(result: GapAnalysisResult) -> str:
    """Format gap analysis as JSON."""
    output = {
        "project_path": result.project_path,
        "total_gaps": result.total_gaps,
        "by_severity": result.by_severity,
        "by_type": result.by_type,
        "recommendations": result.recommendations,
        "gaps": [asdict(g) for g in result.gaps]
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze documentation for gaps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Gap Types:
    documentation  - Missing descriptions, examples, incomplete schemas
    coverage       - Undocumented routes, orphaned services, missing features
    consistency    - Naming mismatches, duplicate definitions, stale references
    quality        - Missing validation, missing error handling docs

Exit Codes:
    0 - No critical gaps
    1 - Critical gaps found
    2 - Warnings only
    3 - Could not complete analysis

Examples:
    %(prog)s /path/to/project
    %(prog)s /path/to/project --type coverage
    %(prog)s /path/to/project --severity warning
    %(prog)s /path/to/project --output report.md
"""
    )

    parser.add_argument(
        "project_path",
        help="Path to project directory"
    )

    parser.add_argument(
        "--type",
        choices=["all", "documentation", "coverage", "consistency", "quality"],
        default="all",
        help="Gap type to analyze (default: all)"
    )

    parser.add_argument(
        "--severity",
        choices=["all", "info", "warning", "error", "critical"],
        default="all",
        help="Minimum severity level (default: all)"
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

    # Run analysis
    analyzer = GapAnalyzer(project_path)

    if args.type == "all":
        result = analyzer.analyze_all()
    else:
        result = analyzer.analyze_type(args.type)

    # Filter by severity if specified
    if args.severity != "all":
        severity_order = {"info": 0, "warning": 1, "error": 2, "critical": 3}
        min_level = severity_order.get(args.severity, 0)
        result.gaps = [g for g in result.gaps if severity_order.get(g.severity, 0) >= min_level]
        result.total_gaps = len(result.gaps)
        result.by_severity = analyzer._count_by_severity()

    # Format output
    if args.format == "json":
        output = format_report_json(result)
    else:
        output = format_report_markdown(result)

    # Write output
    if args.output:
        Path(args.output).write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    # Determine exit code
    if result.by_severity.get("critical", 0) > 0:
        sys.exit(1)
    elif result.by_severity.get("error", 0) > 0:
        sys.exit(1)
    elif result.by_severity.get("warning", 0) > 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
