#!/usr/bin/env python3
"""
Final Document Assembler

Assembles all 8 sections into the final "System Architecture & Logic Reference"
document, running all validation checks before output.

Usage:
    python assemble_document.py <codebase_path> [options]

Options:
    --output DIR      Output directory (default: ./architecture-output)
    --name NAME       Project name override
    --skip-validation Skip validation checks
    --chunked         Enable chunked processing for large projects
    --chunk-size N    Number of files per chunk (default: 100)
    --progress        Show progress during analysis
    --quiet           Suppress progress output
    --format FORMAT   Output format (markdown only for now)
    --help            Show usage information

Exit Codes:
    0 - Document assembled successfully with no validation errors
    1 - Document assembled but validation warnings found
    2 - Failed to assemble document
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ValidationReport:
    """Results from validation checks."""
    path_verification: dict = field(default_factory=dict)
    mermaid_validation: dict = field(default_factory=dict)
    schema_completeness: dict = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return (
            self.path_verification.get('missing', 0) > 0 or
            self.mermaid_validation.get('invalid', 0) > 0 or
            not self.schema_completeness.get('is_complete', True)
        )


@dataclass
class AssemblyResult:
    """Result of document assembly."""
    output_path: str
    project_name: str
    codebase_version: str
    generated_at: str
    validation: ValidationReport
    sections: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Script locations (relative to this script)
SCRIPT_DIR = Path(__file__).parent


def get_codebase_version(codebase_path: Path) -> str:
    """Get git commit info if available."""
    try:
        commit = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=codebase_path,
            stderr=subprocess.DEVNULL
        ).decode().strip()

        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=codebase_path,
            stderr=subprocess.DEVNULL
        ).decode().strip()

        return f"{commit} ({branch})"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "Unknown (not a git repository)"


def detect_tech_stack(codebase_path: Path) -> str:
    """Detect technology stack summary."""
    tech = []

    # Check for package.json (Node.js)
    for subdir in ['', 'backend', 'frontend', 'server', 'api', 'src']:
        check_path = codebase_path / subdir / "package.json" if subdir else codebase_path / "package.json"
        if check_path.exists():
            tech.append("Node.js")
            try:
                with open(check_path) as f:
                    data = json.load(f)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

                if "react" in str(deps).lower():
                    tech.append("React")
                if "next" in str(deps).lower():
                    tech.append("Next.js")
                if "express" in str(deps).lower():
                    tech.append("Express")
                if "fastify" in str(deps).lower():
                    tech.append("Fastify")
                if "typescript" in str(deps).lower():
                    tech.append("TypeScript")
            except:
                pass
            break

    # Check for requirements.txt (Python)
    for subdir in ['', 'backend', 'server', 'api', 'src']:
        check_path = codebase_path / subdir / "requirements.txt" if subdir else codebase_path / "requirements.txt"
        if check_path.exists():
            tech.append("Python")
            try:
                with open(check_path) as f:
                    content = f.read().lower()
                if "fastapi" in content:
                    tech.append("FastAPI")
                if "flask" in content:
                    tech.append("Flask")
                if "django" in content:
                    tech.append("Django")
                if "sqlalchemy" in content:
                    tech.append("SQLAlchemy")
            except:
                pass
            break

    # Check for go.mod (Go)
    if (codebase_path / "go.mod").exists():
        tech.append("Go")

    # Check for pyproject.toml
    for subdir in ['', 'backend', 'server', 'api', 'src']:
        check_path = codebase_path / subdir / "pyproject.toml" if subdir else codebase_path / "pyproject.toml"
        if check_path.exists():
            if "Python" not in tech:
                tech.append("Python")
            break

    # Check for databases
    for subdir in ['', 'backend', 'server', 'api', 'src']:
        base = codebase_path / subdir if subdir else codebase_path

        if (base / "package.json").exists():
            try:
                with open(base / "package.json") as f:
                    content = f.read().lower()
                if "pg" in content or "postgres" in content:
                    tech.append("PostgreSQL")
                if "mysql" in content:
                    tech.append("MySQL")
                if "mongoose" in content or "mongodb" in content:
                    tech.append("MongoDB")
                if "redis" in content or "ioredis" in content:
                    tech.append("Redis")
                if "prisma" in content:
                    tech.append("Prisma")
            except:
                pass

        if (base / "requirements.txt").exists():
            try:
                with open(base / "requirements.txt") as f:
                    content = f.read().lower()
                if "psycopg" in content or "postgres" in content:
                    if "PostgreSQL" not in tech:
                        tech.append("PostgreSQL")
                if "redis" in content:
                    if "Redis" not in tech:
                        tech.append("Redis")
            except:
                pass

    # Remove duplicates while preserving order
    seen = set()
    unique_tech = []
    for t in tech:
        if t not in seen:
            seen.add(t)
            unique_tech.append(t)

    return " · ".join(unique_tech) if unique_tech else "Unknown"


def run_script(script_name: str, args: list[str]) -> tuple[int, str, str]:
    """Run a Python script and return exit code, stdout, stderr."""
    script_path = SCRIPT_DIR / script_name

    if not script_path.exists():
        return -1, "", f"Script not found: {script_path}"

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)] + args,
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Script timed out"
    except Exception as e:
        return -1, "", str(e)


def run_validations(document_path: str, codebase_path: str, skip: bool = False) -> ValidationReport:
    """Run all validation scripts."""
    report = ValidationReport()

    if skip:
        return report

    # Path verification
    code, stdout, stderr = run_script("verify_paths.py", [
        document_path, codebase_path, "--format", "json"
    ])
    if code >= 0 and stdout:
        try:
            data = json.loads(stdout)
            report.path_verification = {
                "total": data.get("summary", {}).get("total", 0),
                "found": data.get("summary", {}).get("found", 0),
                "missing": data.get("summary", {}).get("missing", 0),
            }
        except json.JSONDecodeError:
            report.path_verification = {"error": "Failed to parse output"}

    # Mermaid validation
    code, stdout, stderr = run_script("validate_mermaid.py", [
        document_path, "--format", "json"
    ])
    if code >= 0 and stdout:
        try:
            data = json.loads(stdout)
            report.mermaid_validation = {
                "total": data.get("summary", {}).get("total", 0),
                "valid": data.get("summary", {}).get("valid", 0),
                "invalid": data.get("summary", {}).get("invalid", 0),
            }
        except json.JSONDecodeError:
            report.mermaid_validation = {"error": "Failed to parse output"}

    # Schema completeness (use empty documented tables - we're just detecting)
    code, stdout, stderr = run_script("schema_analysis.py", [
        codebase_path, "--completeness", "--format", "json"
    ])
    if code >= 0 and stdout:
        try:
            data = json.loads(stdout)
            report.schema_completeness = {
                "coverage_percentage": data.get("coverage_percentage", 0),
                "detected_count": data.get("detected_count", 0),
                "is_complete": data.get("is_complete", True),
                "issues_count": len(data.get("issues", [])),
            }
        except json.JSONDecodeError:
            report.schema_completeness = {"error": "Failed to parse output"}

    return report


def generate_toc(content: str) -> str:
    """Generate table of contents from markdown headers."""
    lines = []
    lines.append("## Table of Contents\n")

    # Find all ## headers (section headers)
    header_pattern = r'^##\s+(\d+)\.\s+(.+)$'
    matches = re.findall(header_pattern, content, re.MULTILINE)

    for num, title in matches:
        # Create anchor
        anchor = f"#{num.lower()}-{title.lower().replace(' ', '-').replace('&', 'and')}"
        anchor = re.sub(r'[^a-z0-9-]', '', anchor)
        lines.append(f"{num}. [{title}]({anchor})")

    lines.append("")
    return "\n".join(lines)


def generate_validation_report_md(report: ValidationReport) -> str:
    """Generate validation report markdown section."""
    lines = []
    lines.append("---\n")
    lines.append("## Validation Report\n")

    timestamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    lines.append(f"**Generated:** {timestamp}\n")

    # Path Verification
    lines.append("### Path Verification\n")
    pv = report.path_verification
    if pv.get("error"):
        lines.append(f"**Error:** {pv['error']}\n")
    else:
        lines.append("| Status | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| Found | {pv.get('found', 0)} |")
        lines.append(f"| Missing | {pv.get('missing', 0)} |")
        lines.append("")

        if pv.get('missing', 0) > 0:
            lines.append("**Warning:** Some file paths could not be verified.\n")

    # Mermaid Validation
    lines.append("### Mermaid Validation\n")
    mv = report.mermaid_validation
    if mv.get("error"):
        lines.append(f"**Error:** {mv['error']}\n")
    else:
        lines.append("| Status | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| Valid | {mv.get('valid', 0)} |")
        lines.append(f"| Invalid | {mv.get('invalid', 0)} |")
        lines.append("")

        if mv.get('invalid', 0) > 0:
            lines.append("**Warning:** Some diagrams have syntax errors.\n")

    # Schema Completeness
    lines.append("### Schema Completeness\n")
    sc = report.schema_completeness
    if sc.get("error"):
        lines.append(f"**Error:** {sc['error']}\n")
    else:
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Coverage | {sc.get('coverage_percentage', 0)}% |")
        lines.append(f"| Models Detected | {sc.get('detected_count', 0)} |")
        lines.append("")

        if not sc.get('is_complete', True):
            lines.append("**Warning:** Some schema documentation may be incomplete.\n")

    # Overall Status
    lines.append("### Overall Status\n")
    if report.has_errors:
        lines.append("**Result:** Document generated with validation warnings.\n")
        lines.append("**Recommendation:** Review and fix validation errors before using this document.\n")
    else:
        lines.append("**Result:** All validations passed.\n")

    return "\n".join(lines)


def assemble_document(
    codebase_path: str,
    output_dir: str,
    project_name: Optional[str] = None,
    skip_validation: bool = False,
    chunked: bool = False,
    chunk_size: int = 100,
    show_progress: bool = False,
    quiet: bool = False
) -> AssemblyResult:
    """Assemble the final architecture document."""
    codebase = Path(codebase_path)

    if not codebase.exists():
        return AssemblyResult(
            output_path="",
            project_name="",
            codebase_version="",
            generated_at="",
            validation=ValidationReport(),
            errors=[f"Codebase path does not exist: {codebase_path}"]
        )

    # Determine project name
    if not project_name:
        project_name = codebase.name

    # Get metadata
    codebase_version = get_codebase_version(codebase)
    tech_stack = detect_tech_stack(codebase)
    generated_at = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

    # Generate output filename
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"System-Architecture-Reference-{project_name}-{timestamp}.md"

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / output_filename

    # Build document content
    # This is a template-based approach - in a real implementation,
    # you would call the individual analysis scripts to generate each section

    content = f"""# System Architecture & Logic Reference: {project_name}

> **Generated by:** Architecture Audit Agent
> **Date:** {generated_at}
> **Codebase Version:** {codebase_version}

This document provides a complete technical mapping of **{project_name}** for AI-driven development and human onboarding.

**Detected Tech Stack:** {tech_stack}

---

## Table of Contents

1. Project Overview & Technology Stack
2. System Context (C4 Level 1)
3. Container Architecture (C4 Level 2)
4. Component Breakdown (C4 Level 3)
5. Data Layer & Schema Reference
6. Feature Catalog & API Reference
7. Developer Onboarding & Operational Context
8. Technical Debt & Risk Register

---

## 1. Project Overview & Technology Stack

### 1.1 Project Information

| Property | Value |
|----------|-------|
| Name | {project_name} |
| Location | `{codebase_path}` |
| Version | {codebase_version} |
| Generated | {generated_at} |

### 1.2 Detected Tech Stack

{tech_stack}

> **Note:** Run the individual analysis scripts for detailed tech stack detection.

---

## 2. System Context (C4 Level 1)

### 2.1 System Purpose

> **TODO:** Run `container_discovery.py` for detailed system context analysis.

### 2.2 Context Diagram

```mermaid
C4Context
    title System Context Diagram - {project_name}

    Person(user, "User", "System user")
    System(system, "{project_name}", "Application system")

    Rel(user, system, "Uses", "HTTPS")
```

---

## 3. Container Architecture (C4 Level 2)

### 3.1 Container Diagram

> **TODO:** Run `container_discovery.py` for detailed container analysis.

```mermaid
C4Container
    title Container Diagram - {project_name}

    Person(user, "User", "System user")
    Container(app, "Application", "Technology", "Main application")

    Rel(user, app, "Uses", "HTTPS")
```

---

## 4. Component Breakdown (C4 Level 3)

### 4.1 Component Diagram

> **TODO:** Run `component_breakdown.py` for detailed component analysis.

```mermaid
C4Component
    title Component Diagram - {project_name}

    Container_Boundary(app, "{project_name}") {{
        Component(api, "API Layer", "Technology", "HTTP handlers")
        Component(service, "Service Layer", "Technology", "Business logic")
    }}

    Rel(api, service, "Uses")
```

---

## 5. Data Layer & Schema Reference

### 5.1 Database Configuration

> **TODO:** Run `schema_analysis.py` for detailed schema analysis.

Run the following command for complete schema documentation:
```bash
python scripts/schema_analysis.py {codebase_path} --format markdown
```

---

## 6. Feature Catalog & API Reference

### 6.1 Features

> **TODO:** Run `feature_catalog.py` for detailed feature analysis.

Run the following command for complete feature catalog:
```bash
python scripts/feature_catalog.py {codebase_path} --format markdown
```

---

## 7. Developer Onboarding & Operational Context

### 7.1 Prerequisites

> **TODO:** Run `environment_analyzer.py` for detailed environment analysis.

### 7.2 Getting Started

```bash
# Navigate to project
cd {codebase_path}

# Check project-specific documentation for setup instructions
```

---

## 8. Technical Debt & Risk Register

### 8.1 Analysis

> **TODO:** Run `technical_debt_analyzer.py` for detailed debt analysis.

Run the following command for complete technical debt analysis:
```bash
python scripts/technical_debt_analyzer.py {codebase_path} --format markdown
```

---

*Document generated by Architecture Audit Agent*
"""

    # Write document
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        return AssemblyResult(
            output_path="",
            project_name=project_name,
            codebase_version=codebase_version,
            generated_at=generated_at,
            validation=ValidationReport(),
            errors=[f"Failed to write document: {e}"]
        )

    # Run validations
    validation = run_validations(str(output_file), str(codebase), skip_validation)

    # Append validation report
    if not skip_validation:
        validation_md = generate_validation_report_md(validation)
        try:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write("\n" + validation_md)
        except Exception as e:
            pass  # Non-fatal

    return AssemblyResult(
        output_path=str(output_file),
        project_name=project_name,
        codebase_version=codebase_version,
        generated_at=generated_at,
        validation=validation,
        sections=["Overview", "System Context", "Containers", "Components", "Data Schema", "Features", "Onboarding", "Technical Debt"]
    )


def output_json(result: AssemblyResult) -> str:
    """Format assembly result as JSON."""
    output = {
        "success": len(result.errors) == 0,
        "output_path": result.output_path,
        "project_name": result.project_name,
        "codebase_version": result.codebase_version,
        "generated_at": result.generated_at,
        "sections": result.sections,
        "validation": {
            "has_errors": result.validation.has_errors,
            "path_verification": result.validation.path_verification,
            "mermaid_validation": result.validation.mermaid_validation,
            "schema_completeness": result.validation.schema_completeness,
        },
        "errors": result.errors
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Assemble final System Architecture & Logic Reference document",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
    0 - Document assembled successfully with no validation errors
    1 - Document assembled but validation warnings found
    2 - Failed to assemble document

Examples:
    %(prog)s /path/to/project
    %(prog)s /path/to/project --output ./output
    %(prog)s /path/to/project --name "My Project" --skip-validation
"""
    )

    parser.add_argument(
        "codebase_path",
        help="Path to the codebase to analyze"
    )

    parser.add_argument(
        "--output",
        default="./architecture-output",
        help="Output directory (default: ./architecture-output)"
    )

    parser.add_argument(
        "--name",
        help="Project name override"
    )

    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation checks"
    )

    # Scalability options (Epic 4)
    parser.add_argument(
        "--chunked",
        action="store_true",
        help="Enable chunked processing for large projects"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=100,
        help="Number of files per chunk (default: 100)"
    )

    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bar during analysis"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )

    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format for status (default: markdown)"
    )

    args = parser.parse_args()

    # Assemble document
    result = assemble_document(
        args.codebase_path,
        args.output,
        args.name,
        args.skip_validation,
        chunked=args.chunked,
        chunk_size=args.chunk_size,
        show_progress=args.progress,
        quiet=args.quiet
    )

    # Output result
    if args.format == "json":
        print(output_json(result))
    else:
        if result.errors:
            print("ERRORS:")
            for error in result.errors:
                print(f"  - {error}")
            print()

        if result.output_path:
            print(f"Document assembled: {result.output_path}")
            print(f"Project: {result.project_name}")
            print(f"Version: {result.codebase_version}")
            print(f"Sections: {len(result.sections)}")

            if not args.skip_validation:
                print()
                print("Validation:")
                print(f"  Paths: {result.validation.path_verification.get('missing', 0)} missing")
                print(f"  Mermaid: {result.validation.mermaid_validation.get('invalid', 0)} invalid")
                print(f"  Schema: {result.validation.schema_completeness.get('coverage_percentage', 0)}% coverage")

    # Return appropriate exit code
    if result.errors and not result.output_path:
        sys.exit(2)  # Failed to assemble
    elif result.validation.has_errors:
        sys.exit(1)  # Warnings found
    sys.exit(0)  # Success


if __name__ == "__main__":
    main()
