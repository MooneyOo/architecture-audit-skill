#!/usr/bin/env python3
"""
Dependency Analysis Script

Analyzes project dependencies from various package managers and outputs
structured reports in JSON or Markdown format.

Usage:
    python analyze_dependencies.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: json)
    --include-dev             Include dev dependencies
    --check-vulnerabilities   Check for known vulnerabilities (placeholder)
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


class PackageManager(Enum):
    NPM = "npm"
    PIP = "pip"
    GO = "go"
    POETRY = "poetry"
    UNKNOWN = "unknown"


@dataclass
class Dependency:
    name: str
    version: str
    dep_type: str = "unknown"  # framework, database, testing, utility, etc.
    is_dev: bool = False


@dataclass
class AnalysisResult:
    project_path: str
    package_manager: PackageManager
    dependencies: list[Dependency] = field(default_factory=list)
    deprecated: list[str] = field(default_factory=list)
    vulnerabilities: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Framework detection patterns
FRAMEWORK_PATTERNS = {
    # JavaScript/TypeScript
    "next": "Next.js",
    "express": "Express.js",
    "fastify": "Fastify",
    "nuxt": "Nuxt.js",
    "nest": "NestJS",
    "react": "React",
    "vue": "Vue.js",
    "angular": "Angular",
    "svelte": "Svelte",
    "vite": "Vite",
    # Python
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "sanic": "Sanic",
    "tornado": "Tornado",
    "starlette": "Starlette",
    # Go
    "gin-gonic/gin": "Gin",
    "labstack/echo": "Echo",
    "gofiber/fiber": "Fiber",
}

# Database/ORM detection patterns
DATABASE_PATTERNS = {
    "pg": "PostgreSQL",
    "postgres": "PostgreSQL",
    "psycopg": "PostgreSQL",
    "psycopg2": "PostgreSQL",
    "mysql": "MySQL",
    "mysql2": "MySQL",
    "mongodb": "MongoDB",
    "mongoose": "MongoDB",
    "redis": "Redis",
    "ioredis": "Redis",
    "sqlite": "SQLite",
    "prisma": "Prisma ORM",
    "typeorm": "TypeORM",
    "sequelize": "Sequelize",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic (migrations)",
    "django.db": "Django ORM",
}

# Service detection patterns
SERVICE_PATTERNS = {
    "stripe": "Stripe Payments",
    "aws-sdk": "AWS",
    "boto3": "AWS",
    "@google-cloud": "Google Cloud",
    "firebase": "Firebase",
    "sendgrid": "SendGrid Email",
    "twilio": "Twilio",
    "auth0": "Auth0",
    "passport": "Passport.js Auth",
    "httpx": "HTTP Client",
    "axios": "HTTP Client",
    "fetch": "HTTP Client",
    "openpyxl": "Excel Processing",
    "python-jose": "JWT Handling",
}

# Testing patterns
TESTING_PATTERNS = {
    "jest": "Jest",
    "vitest": "Vitest",
    "mocha": "Mocha",
    "pytest": "pytest",
    "playwright": "Playwright",
    "cypress": "Cypress",
    "@testing-library": "Testing Library",
}


def categorize_dependency(name: str) -> str:
    """Categorize a dependency by type."""
    name_lower = name.lower()

    for pattern, category in FRAMEWORK_PATTERNS.items():
        if pattern in name_lower:
            return "framework"

    for pattern, category in DATABASE_PATTERNS.items():
        if pattern in name_lower:
            return "database"

    for pattern, category in SERVICE_PATTERNS.items():
        if pattern in name_lower:
            return "service"

    for pattern, category in TESTING_PATTERNS.items():
        if pattern in name_lower:
            return "testing"

    return "utility"


def parse_package_json(project_path: Path) -> AnalysisResult:
    """Parse package.json for Node.js projects."""
    result = AnalysisResult(
        project_path=str(project_path),
        package_manager=PackageManager.NPM
    )

    package_json_path = project_path / "package.json"
    if not package_json_path.exists():
        result.errors.append("package.json not found")
        return result

    try:
        with open(package_json_path, "r") as f:
            data = json.load(f)

        # Production dependencies
        for name, version in data.get("dependencies", {}).items():
            clean_version = version.lstrip("^~>=<")
            result.dependencies.append(Dependency(
                name=name,
                version=clean_version,
                dep_type=categorize_dependency(name),
                is_dev=False
            ))

        # Development dependencies
        for name, version in data.get("devDependencies", {}).items():
            clean_version = version.lstrip("^~>=<")
            result.dependencies.append(Dependency(
                name=name,
                version=clean_version,
                dep_type=categorize_dependency(name),
                is_dev=True
            ))

    except json.JSONDecodeError as e:
        result.errors.append(f"Invalid JSON in package.json: {e}")
    except Exception as e:
        result.errors.append(f"Error reading package.json: {e}")

    return result


def parse_requirements_txt(project_path: Path) -> AnalysisResult:
    """Parse requirements.txt for Python projects."""
    result = AnalysisResult(
        project_path=str(project_path),
        package_manager=PackageManager.PIP
    )

    requirements_path = project_path / "requirements.txt"
    if not requirements_path.exists():
        result.errors.append("requirements.txt not found")
        return result

    try:
        with open(requirements_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Skip lines with environment markers (e.g., ; extra == "dev")
                if ";" in line:
                    line = line.split(";")[0].strip()

                # Parse package==version or package>=version formats
                match = re.match(r'^([a-zA-Z0-9_-]+)\s*([=<>!]+)\s*(.+)$', line)
                if match:
                    name = match.group(1)
                    version = match.group(3)
                else:
                    # Just package name
                    match = re.match(r'^([a-zA-Z0-9_-]+)$', line)
                    if match:
                        name = match.group(1)
                        version = "latest"
                    else:
                        continue

                result.dependencies.append(Dependency(
                    name=name,
                    version=version,
                    dep_type=categorize_dependency(name),
                    is_dev=False  # requirements.txt doesn't distinguish
                ))

    except Exception as e:
        result.errors.append(f"Error reading requirements.txt: {e}")

    return result


def parse_go_mod(project_path: Path) -> AnalysisResult:
    """Parse go.mod for Go projects."""
    result = AnalysisResult(
        project_path=str(project_path),
        package_manager=PackageManager.GO
    )

    go_mod_path = project_path / "go.mod"
    if not go_mod_path.exists():
        result.errors.append("go.mod not found")
        return result

    try:
        with open(go_mod_path, "r") as f:
            content = f.read()

        # Extract Go version
        go_version_match = re.search(r'go\s+(\d+\.\d+(?:\.\d+)?)', content)
        if go_version_match:
            result.dependencies.append(Dependency(
                name="go",
                version=go_version_match.group(1),
                dep_type="language",
                is_dev=False
            ))

        # Extract require block
        require_match = re.search(r'require\s*\(([\s\S]*?)\)', content)
        if require_match:
            for line in require_match.group(1).strip().split('\n'):
                parts = line.strip().split()
                if len(parts) >= 2:
                    result.dependencies.append(Dependency(
                        name=parts[0],
                        version=parts[1],
                        dep_type=categorize_dependency(parts[0]),
                        is_dev=False
                    ))

        # Single-line requires
        single_requires = re.findall(r'require\s+([^\s]+)\s+([^\s]+)', content)
        for name, version in single_requires:
            result.dependencies.append(Dependency(
                name=name,
                version=version,
                dep_type=categorize_dependency(name),
                is_dev=False
            ))

    except Exception as e:
        result.errors.append(f"Error reading go.mod: {e}")

    return result


def parse_pyproject_toml(project_path: Path) -> AnalysisResult:
    """Parse pyproject.toml for Python Poetry projects."""
    result = AnalysisResult(
        project_path=str(project_path),
        package_manager=PackageManager.POETRY
    )

    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.exists():
        result.errors.append("pyproject.toml not found")
        return result

    try:
        with open(pyproject_path, "r") as f:
            content = f.read()

        # Simple TOML parsing for dependencies (basic implementation)
        # Look for [tool.poetry.dependencies] section
        in_deps = False
        in_dev_deps = False

        for line in content.split('\n'):
            line_stripped = line.strip()

            if line_stripped == '[tool.poetry.dependencies]':
                in_deps = True
                in_dev_deps = False
                continue
            elif line_stripped == '[tool.poetry.group.dev.dependencies]':
                in_deps = False
                in_dev_deps = True
                continue
            elif line_stripped.startswith('['):
                in_deps = False
                in_dev_deps = False
                continue

            if in_deps or in_dev_deps:
                # Parse: package = "version" or package = {version = "x"}
                match = re.match(r'^([a-zA-Z0-9_-]+)\s*=\s*"?([^"\n]+)"?', line_stripped)
                if match:
                    name = match.group(1)
                    version_spec = match.group(2)

                    # Skip python version spec
                    if name == 'python':
                        continue

                    # Extract version from {version = "x"} format
                    version_match = re.search(r'version\s*=\s*"([^"]+)"', version_spec)
                    if version_match:
                        version = version_match.group(1)
                    else:
                        version = version_spec.strip('"\'')

                    result.dependencies.append(Dependency(
                        name=name,
                        version=version,
                        dep_type=categorize_dependency(name),
                        is_dev=in_dev_deps
                    ))

    except Exception as e:
        result.errors.append(f"Error reading pyproject.toml: {e}")

    return result


def detect_package_manager(project_path: Path) -> list[PackageManager]:
    """Detect which package managers are used in the project."""
    managers = []

    if (project_path / "package.json").exists():
        managers.append(PackageManager.NPM)

    if (project_path / "requirements.txt").exists():
        managers.append(PackageManager.PIP)

    if (project_path / "go.mod").exists():
        managers.append(PackageManager.GO)

    if (project_path / "pyproject.toml").exists():
        managers.append(PackageManager.POETRY)

    return managers if managers else [PackageManager.UNKNOWN]


def analyze_project(project_path: str, include_dev: bool = True) -> list[AnalysisResult]:
    """Analyze a project for all detected package managers."""
    path = Path(project_path)

    if not path.exists():
        return [AnalysisResult(
            project_path=project_path,
            package_manager=PackageManager.UNKNOWN,
            errors=[f"Project path does not exist: {project_path}"]
        )]

    managers = detect_package_manager(path)
    results = []

    for manager in managers:
        if manager == PackageManager.NPM:
            result = parse_package_json(path)
        elif manager == PackageManager.PIP:
            result = parse_requirements_txt(path)
        elif manager == PackageManager.GO:
            result = parse_go_mod(path)
        elif manager == PackageManager.POETRY:
            result = parse_pyproject_toml(path)
        else:
            result = AnalysisResult(
                project_path=str(path),
                package_manager=PackageManager.UNKNOWN,
                errors=["No supported package manager detected"]
            )

        # Filter out dev dependencies if not requested
        if not include_dev:
            result.dependencies = [d for d in result.dependencies if not d.is_dev]

        results.append(result)

    return results


def output_json(results: list[AnalysisResult]) -> str:
    """Format results as JSON."""
    output = []

    for result in results:
        deps = {"production": [], "development": []}

        for dep in result.dependencies:
            dep_dict = {
                "name": dep.name,
                "version": dep.version,
                "type": dep.dep_type
            }
            if dep.is_dev:
                deps["development"].append(dep_dict)
            else:
                deps["production"].append(dep_dict)

        output.append({
            "project_path": result.project_path,
            "package_manager": result.package_manager.value,
            "dependencies": deps,
            "deprecated": result.deprecated,
            "vulnerabilities": result.vulnerabilities,
            "errors": result.errors
        })

    return json.dumps(output, indent=2)


def output_markdown(results: list[AnalysisResult]) -> str:
    """Format results as Markdown."""
    lines = ["# Dependency Analysis Report\n"]

    for result in results:
        lines.append(f"## Project: `{result.project_path}`\n")
        lines.append(f"**Package Manager:** {result.package_manager.value}\n")

        if result.errors:
            lines.append("### Errors\n")
            for error in result.errors:
                lines.append(f"- {error}\n")
            lines.append("\n")

        # Production dependencies
        prod_deps = [d for d in result.dependencies if not d.is_dev]
        if prod_deps:
            lines.append("### Production Dependencies\n")
            lines.append("| Package | Version | Type |")
            lines.append("|---------|---------|------|")
            for dep in sorted(prod_deps, key=lambda x: x.name):
                lines.append(f"| {dep.name} | {dep.version} | {dep.dep_type} |")
            lines.append("")

        # Development dependencies
        dev_deps = [d for d in result.dependencies if d.is_dev]
        if dev_deps:
            lines.append("### Development Dependencies\n")
            lines.append("| Package | Version | Type |")
            lines.append("|---------|---------|------|")
            for dep in sorted(dev_deps, key=lambda x: x.name):
                lines.append(f"| {dep.name} | {dep.version} | {dep.dep_type} |")
            lines.append("")

        # Summary
        lines.append("### Summary\n")
        lines.append(f"- Total production dependencies: {len(prod_deps)}")
        lines.append(f"- Total development dependencies: {len(dev_deps)}")

        # Group by type
        type_counts = {}
        for dep in result.dependencies:
            type_counts[dep.dep_type] = type_counts.get(dep.dep_type, 0) + 1

        lines.append("\n**Dependency Types:**")
        for dep_type, count in sorted(type_counts.items()):
            lines.append(f"- {dep_type}: {count}")

        lines.append("\n---\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze project dependencies from various package managers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --format markdown
  %(prog)s /path/to/project --format json --include-dev
"""
    )

    parser.add_argument(
        "project_path",
        help="Path to the project directory"
    )

    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)"
    )

    parser.add_argument(
        "--include-dev",
        action="store_true",
        default=True,
        help="Include development dependencies (default: True)"
    )

    parser.add_argument(
        "--no-dev",
        action="store_true",
        help="Exclude development dependencies"
    )

    parser.add_argument(
        "--check-vulnerabilities",
        action="store_true",
        help="Check for known vulnerabilities (placeholder for future)"
    )

    args = parser.parse_args()

    # Handle --no-dev flag
    include_dev = args.include_dev and not args.no_dev

    # Analyze project
    results = analyze_project(args.project_path, include_dev)

    # Check for critical errors
    has_errors = any(r.errors and not r.dependencies for r in results)

    # Output results
    if args.format == "json":
        print(output_json(results))
    else:
        print(output_markdown(results))

    # Return appropriate exit code
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
