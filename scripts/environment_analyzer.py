#!/usr/bin/env python3
"""
Environment Variable Analysis Script

Analyzes project environment configuration from multiple sources and outputs
structured reports in JSON or Markdown format.

Usage:
    python environment_analyzer.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: json)
    --help                    Show usage information

Sources analyzed:
    - .env.example, .env.sample files
    - Pydantic BaseSettings classes (config.py, settings.py)
    - Code references (process.env, os.environ, os.getenv)
    - Docker Compose environment variables
    - Package.json scripts for startup hints
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class EnvVariable:
    """Represents an environment variable."""
    name: str
    purpose: str = ""
    example_value: str = ""
    required: bool = True
    default: str = ""
    source_file: str = ""
    line_number: int = 0
    detected_in_code: bool = False


@dataclass
class Prerequisite:
    """Represents a system prerequisite."""
    name: str
    version: str = ""
    installation_command: str = ""
    detection_source: str = ""


@dataclass
class StartupStep:
    """Represents a startup sequence step."""
    step_number: int
    description: str
    command: str


@dataclass
class EnvironmentAnalysisResult:
    """Result of environment analysis."""
    project_path: str
    env_variables: list[EnvVariable] = field(default_factory=list)
    prerequisites: list[Prerequisite] = field(default_factory=list)
    startup_sequence: list[StartupStep] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Environment variable detection patterns by language
ENV_PATTERNS = {
    'python': [
        r"os\.environ\[['\"](\w+)['\"]\]",
        r"os\.environ\.get\(['\"](\w+)['\"]",
        r"os\.getenv\(['\"](\w+)['\"]",
        r"settings\.(\w+)",
    ],
    'nodejs': [
        r"process\.env\.(\w+)",
        r"process\.env\[['\"](\w+)['\"]\]",
        r"import\.meta\.env\.(\w+)",
    ],
    'go': [
        r"os\.Getenv\(['\"](\w+)['\"]\)",
    ],
}

# Config file patterns to search for
CONFIG_FILES = [
    '.env.example', '.env.sample', '.env.template',
    'config.py', 'settings.py', 'config.ts', 'config.js',
]

# Pydantic BaseSettings field pattern
PYDANTIC_FIELD_PATTERN = r"(\w+):\s*(?:Optional\[)?str(?:\].*?=\s*(?:Field\([^)]*default\s*=\s*[\"']?([^\"'),]+)[\"']?|None|[\"']([^\"']+)[\"']))"

# Version requirement patterns
VERSION_PATTERNS = {
    'python': r'python\s*>=?\s*(\d+\.\d+)',
    'node': r'"node":\s*">=?\s*(\d+\.\d+)',
    'postgres': r'postgres.*?(\d+\.\d+)',
}


def parse_env_file(file_path: Path) -> list[EnvVariable]:
    """Parse .env.example or similar files with comments as descriptions."""
    variables = []

    if not file_path.exists():
        return variables

    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        current_comment = ""
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # Skip empty lines
            if not line_stripped:
                current_comment = ""
                continue

            # Capture comments as descriptions
            if line_stripped.startswith('#'):
                comment = line_stripped[1:].strip()
                if comment and not comment.startswith('!'):  # Skip shebang
                    current_comment = comment
                continue

            # Parse variable assignment
            match = re.match(r'^(\w+)=?(.*)$', line_stripped)
            if match:
                name = match.group(1)
                value = match.group(2).strip()

                # Determine if required based on value presence
                required = not value or value == ''

                # Clean up example value
                example_value = value.strip('"\'') if value else ""

                variables.append(EnvVariable(
                    name=name,
                    purpose=current_comment,
                    example_value=example_value,
                    required=required,
                    source_file=str(file_path),
                    line_number=line_num,
                ))
                current_comment = ""

    except Exception as e:
        pass  # Error handled in main analysis

    return variables


def scan_codebase_env_usage(project_path: Path, file_extensions: list[str]) -> dict[str, list[tuple[str, int]]]:
    """Scan codebase for environment variable usage."""
    env_usage = {}

    for ext in file_extensions:
        for file_path in project_path.rglob(f"*{ext}"):
            # Skip common non-source directories
            if any(part in file_path.parts for part in ['node_modules', '.git', '__pycache__', 'venv', '.venv', 'dist', 'build']):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                relative_path = str(file_path.relative_to(project_path))

                # Check Python patterns
                for pattern in ENV_PATTERNS.get('python', []):
                    if ext in ['.py']:
                        for match in re.finditer(pattern, content):
                            var_name = match.group(1)
                            if var_name not in env_usage:
                                env_usage[var_name] = []
                            # Find line number
                            line_num = content[:match.start()].count('\n') + 1
                            env_usage[var_name].append((relative_path, line_num))

                # Check Node.js patterns
                for pattern in ENV_PATTERNS.get('nodejs', []):
                    if ext in ['.js', '.ts', '.tsx', '.jsx']:
                        for match in re.finditer(pattern, content):
                            var_name = match.group(1)
                            if var_name not in env_usage:
                                env_usage[var_name] = []
                            line_num = content[:match.start()].count('\n') + 1
                            env_usage[var_name].append((relative_path, line_num))

                # Check Go patterns
                for pattern in ENV_PATTERNS.get('go', []):
                    if ext in ['.go']:
                        for match in re.finditer(pattern, content):
                            var_name = match.group(1)
                            if var_name not in env_usage:
                                env_usage[var_name] = []
                            line_num = content[:match.start()].count('\n') + 1
                            env_usage[var_name].append((relative_path, line_num))

            except Exception:
                continue

    return env_usage


def extract_pydantic_settings(project_path: Path) -> list[EnvVariable]:
    """Extract environment variables from Pydantic BaseSettings classes."""
    variables = []

    settings_files = list(project_path.rglob("config.py")) + list(project_path.rglob("settings.py"))

    for settings_file in settings_files:
        # Skip virtual environments
        if any(part in settings_file.parts for part in ['venv', '.venv', '__pycache__']):
            continue

        try:
            with open(settings_file, 'r') as f:
                content = f.read()

            # Check if it's a BaseSettings class
            if 'BaseSettings' not in content:
                continue

            relative_path = str(settings_file.relative_to(project_path))

            # Find class definitions that inherit from BaseSettings
            class_pattern = r'class\s+(\w+)\s*\([^)]*BaseSettings[^)]*\):\s*\n((?:\s{4,}[^\n]*\n)*)'
            for class_match in re.finditer(class_pattern, content):
                class_body = class_match.group(2)

                # Parse field definitions
                field_pattern = r'^\s+(\w+):\s*(?:Optional\[)?(\w+)(?:\[[^\]]+\])?(?:\])?\s*(?:=\s*(?:Field\([^)]*(?:default\s*=\s*)?([^\)]+)\)|([^,\n]+)))?'
                for field_match in re.finditer(field_pattern, class_body, re.MULTILINE):
                    name = field_match.group(1)
                    field_type = field_match.group(2)
                    default_val = field_match.group(3) or field_match.group(4) or ""

                    # Clean up default value
                    default_val = default_val.strip().strip('"\'').strip(',')
                    if default_val in ['None', '...', '']:
                        default_val = ""

                    # Calculate line number
                    line_num = content[:class_match.start()].count('\n') + 1 + class_body[:field_match.start()].count('\n') + 1

                    variables.append(EnvVariable(
                        name=name.upper(),  # Convert to ENV_VAR format
                        purpose=f"Pydantic setting ({field_type})",
                        default=default_val,
                        required=not bool(default_val),
                        source_file=relative_path,
                        line_number=line_num,
                    ))

        except Exception:
            continue

    return variables


def detect_docker_config(project_path: Path) -> tuple[list[EnvVariable], list[StartupStep]]:
    """Extract environment and startup info from docker-compose.yml."""
    variables = []
    startup_steps = []

    compose_file = project_path / "docker-compose.yml"
    if not compose_file.exists():
        compose_file = project_path / "docker-compose.yaml"

    if not compose_file.exists():
        return variables, startup_steps

    try:
        import yaml
        with open(compose_file, 'r') as f:
            compose = yaml.safe_load(f)

        if not compose:
            return variables, startup_steps

        # Extract environment variables from services
        services = compose.get('services', {})
        for service_name, service_config in services.items():
            if isinstance(service_config, dict):
                # Check environment section
                env_vars = service_config.get('environment', [])
                if isinstance(env_vars, dict):
                    for name, value in env_vars.items():
                        variables.append(EnvVariable(
                            name=name,
                            example_value=str(value) if value else "",
                            purpose=f"Docker environment for {service_name}",
                            required=False,
                            source_file="docker-compose.yml",
                        ))
                elif isinstance(env_vars, list):
                    for env_item in env_vars:
                        if isinstance(env_item, str) and '=' in env_item:
                            name, value = env_item.split('=', 1)
                            variables.append(EnvVariable(
                                name=name,
                                example_value=value,
                                purpose=f"Docker environment for {service_name}",
                                required=False,
                                source_file="docker-compose.yml",
                            ))

        # Generate Docker startup step
        startup_steps.append(StartupStep(
            step_number=1,
            description="Start services with Docker Compose",
            command="docker-compose up -d"
        ))

    except ImportError:
        # YAML not available, try regex parsing
        try:
            with open(compose_file, 'r') as f:
                content = f.read()

            # Simple regex for environment variables
            env_pattern = r'-\s*(\w+)=([^\n]+)'
            for match in re.finditer(env_pattern, content):
                variables.append(EnvVariable(
                    name=match.group(1),
                    example_value=match.group(2).strip().strip('"\''),
                    purpose="Docker environment",
                    required=False,
                    source_file="docker-compose.yml",
                ))
        except Exception:
            pass
    except Exception:
        pass

    return variables, startup_steps


def detect_package_managers(project_path: Path) -> list[str]:
    """Detect package managers used in the project."""
    managers = []

    if (project_path / "package.json").exists():
        managers.append("npm")
    if (project_path / "yarn.lock").exists():
        managers.append("yarn")
    if (project_path / "pnpm-lock.yaml").exists():
        managers.append("pnpm")
    if (project_path / "requirements.txt").exists():
        managers.append("pip")
    if (project_path / "pyproject.toml").exists():
        managers.append("poetry/pip")
    if (project_path / "go.mod").exists():
        managers.append("go modules")
    if (project_path / "Cargo.toml").exists():
        managers.append("cargo")

    return managers


def generate_startup_sequence(project_path: Path, package_managers: list[str]) -> list[StartupStep]:
    """Generate startup sequence based on project type."""
    steps = []
    step_num = 1

    # Check for Docker first
    has_docker = (project_path / "docker-compose.yml").exists() or (project_path / "docker-compose.yaml").exists()

    if has_docker:
        steps.append(StartupStep(
            step_number=step_num,
            description="Clone and start with Docker",
            command="git clone <repo> && cd <project> && docker-compose up -d"
        ))
        return steps

    # Clone step
    steps.append(StartupStep(
        step_number=step_num,
        description="Clone and navigate to project",
        command="git clone <repo> && cd <project>"
    ))
    step_num += 1

    # Install dependencies based on package manager
    if "npm" in package_managers or "yarn" in package_managers or "pnpm" in package_managers:
        if "yarn" in package_managers:
            install_cmd = "yarn install"
        elif "pnpm" in package_managers:
            install_cmd = "pnpm install"
        else:
            install_cmd = "npm install"

        steps.append(StartupStep(
            step_number=step_num,
            description="Install Node.js dependencies",
            command=install_cmd
        ))
        step_num += 1

    if "pip" in package_managers or "poetry/pip" in package_managers:
        if "poetry/pip" in package_managers and (project_path / "pyproject.toml").exists():
            install_cmd = "poetry install"
        else:
            install_cmd = "pip install -r requirements.txt"

        steps.append(StartupStep(
            step_number=step_num,
            description="Install Python dependencies",
            command=install_cmd
        ))
        step_num += 1

    # Environment configuration
    env_example = project_path / ".env.example"
    if env_example.exists():
        steps.append(StartupStep(
            step_number=step_num,
            description="Configure environment variables",
            command="cp .env.example .env  # Edit .env with your values"
        ))
        step_num += 1

    # Database setup
    if (project_path / "alembic.ini").exists():
        steps.append(StartupStep(
            step_number=step_num,
            description="Run database migrations",
            command="alembic upgrade head"
        ))
        step_num += 1
    elif (project_path / "migrations").exists():
        steps.append(StartupStep(
            step_number=step_num,
            description="Run database migrations",
            command="npm run db:migrate  # or similar"
        ))
        step_num += 1

    # Start command
    start_cmd = None
    if "npm" in package_managers or "yarn" in package_managers:
        # Check package.json for scripts
        package_json = project_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json, 'r') as f:
                    pkg = json.load(f)
                scripts = pkg.get('scripts', {})
                if 'dev' in scripts:
                    start_cmd = "npm run dev" if "npm" in package_managers else "yarn dev"
                elif 'start' in scripts:
                    start_cmd = "npm start" if "npm" in package_managers else "yarn start"
            except Exception:
                pass

    if not start_cmd:
        # Check for common entry points
        if (project_path / "main.py").exists():
            start_cmd = "python main.py"
        elif (project_path / "app.py").exists():
            start_cmd = "python app.py"
        elif (project_path / "manage.py").exists():
            start_cmd = "python manage.py runserver"
        elif (project_path / "src" / "main.py").exists():
            start_cmd = "python -m src.main"

    if start_cmd:
        steps.append(StartupStep(
            step_number=step_num,
            description="Start development server",
            command=start_cmd
        ))

    return steps


def detect_prerequisites(project_path: Path, package_managers: list[str]) -> list[Prerequisite]:
    """Detect system prerequisites based on project configuration."""
    prerequisites = []

    # Python version
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        try:
            with open(pyproject, 'r') as f:
                content = f.read()
            match = re.search(r'python\s*>=?\s*["\']?(\d+\.\d+)', content)
            if match:
                prerequisites.append(Prerequisite(
                    name="Python",
                    version=f">= {match.group(1)}",
                    installation_command="brew install python@3.x or pyenv install 3.x",
                    detection_source="pyproject.toml"
                ))
        except Exception:
            pass

    requirements = project_path / "requirements.txt"
    if requirements.exists():
        prerequisites.append(Prerequisite(
            name="Python",
            version="3.8+",
            installation_command="brew install python@3.x",
            detection_source="requirements.txt"
        ))

    # Node.js version
    package_json = project_path / "package.json"
    if package_json.exists():
        try:
            with open(package_json, 'r') as f:
                pkg = json.load(f)
            engines = pkg.get('engines', {})
            node_version = engines.get('node', '18+')
            prerequisites.append(Prerequisite(
                name="Node.js",
                version=node_version,
                installation_command="brew install node@18 or nvm install 18",
                detection_source="package.json"
            ))
        except Exception:
            pass

    # Database
    if list(project_path.rglob("alembic.ini")) or any(
        'postgresql' in str(f) or 'postgres' in str(f)
        for f in project_path.rglob("*.py")
    ):
        prerequisites.append(Prerequisite(
            name="PostgreSQL",
            version="14+",
            installation_command="brew install postgresql@14",
            detection_source="Database configuration"
        ))

    # Docker
    if (project_path / "docker-compose.yml").exists():
        prerequisites.append(Prerequisite(
            name="Docker",
            version="20+",
            installation_command="brew install --cask docker",
            detection_source="docker-compose.yml"
        ))
        prerequisites.append(Prerequisite(
            name="Docker Compose",
            version="2+",
            installation_command="brew install docker-compose",
            detection_source="docker-compose.yml"
        ))

    return prerequisites


def analyze_project(project_path: str) -> EnvironmentAnalysisResult:
    """Analyze a project for environment configuration."""
    path = Path(project_path)
    result = EnvironmentAnalysisResult(project_path=project_path)

    if not path.exists():
        result.errors.append(f"Project path does not exist: {project_path}")
        return result

    # Detect package managers
    result.package_managers = detect_package_managers(path)

    # Find config files
    for config_name in CONFIG_FILES:
        config_path = path / config_name
        if config_path.exists():
            result.config_files.append(config_name)

    # 1. Parse .env.example files
    env_example = path / ".env.example"
    if env_example.exists():
        result.env_variables.extend(parse_env_file(env_example))

    # Also check for .env.sample
    env_sample = path / ".env.sample"
    if env_sample.exists():
        result.env_variables.extend(parse_env_file(env_sample))

    # 2. Extract Pydantic settings
    pydantic_vars = extract_pydantic_settings(path)
    result.env_variables.extend(pydantic_vars)

    # 3. Scan codebase for env usage
    env_usage = scan_codebase_env_usage(path, ['.py', '.js', '.ts', '.tsx', '.go'])

    # Merge with existing variables, marking those found in code
    for var in result.env_variables:
        if var.name in env_usage:
            var.detected_in_code = True

    # Add variables found only in code
    existing_names = {v.name for v in result.env_variables}
    for var_name, locations in env_usage.items():
        if var_name.upper() not in existing_names and not var_name.startswith('_'):
            result.env_variables.append(EnvVariable(
                name=var_name.upper(),
                purpose="Detected in code",
                required=True,
                detected_in_code=True,
                source_file=locations[0][0] if locations else "",
                line_number=locations[0][1] if locations else 0,
            ))

    # 4. Detect Docker config
    docker_vars, docker_steps = detect_docker_config(path)
    result.env_variables.extend(docker_vars)

    # 5. Generate startup sequence
    result.startup_sequence = generate_startup_sequence(path, result.package_managers)
    if docker_steps:
        result.startup_sequence = docker_steps  # Use Docker startup if available

    # 6. Detect prerequisites
    result.prerequisites = detect_prerequisites(path, result.package_managers)

    # Deduplicate variables
    seen = set()
    unique_vars = []
    for var in result.env_variables:
        key = var.name
        if key not in seen:
            seen.add(key)
            unique_vars.append(var)
    result.env_variables = unique_vars

    return result


def output_json(result: EnvironmentAnalysisResult) -> str:
    """Format result as JSON."""
    output = {
        "project_path": result.project_path,
        "package_managers": result.package_managers,
        "config_files": result.config_files,
        "environment_variables": [
            {
                "name": v.name,
                "purpose": v.purpose,
                "example_value": v.example_value,
                "required": v.required,
                "default": v.default,
                "source_file": v.source_file,
                "line_number": v.line_number,
                "detected_in_code": v.detected_in_code,
            }
            for v in result.env_variables
        ],
        "prerequisites": [
            {
                "name": p.name,
                "version": p.version,
                "installation_command": p.installation_command,
            }
            for p in result.prerequisites
        ],
        "startup_sequence": [
            {
                "step": s.step_number,
                "description": s.description,
                "command": s.command,
            }
            for s in result.startup_sequence
        ],
        "errors": result.errors,
    }
    return json.dumps(output, indent=2)


def output_markdown(result: EnvironmentAnalysisResult) -> str:
    """Format result as Markdown."""
    lines = ["# Environment Analysis Report\n"]
    lines.append(f"**Project:** `{result.project_path}`\n")

    if result.package_managers:
        lines.append(f"**Package Managers:** {', '.join(result.package_managers)}\n")

    if result.config_files:
        lines.append(f"**Config Files:** {', '.join(result.config_files)}\n")

    if result.errors:
        lines.append("## Errors\n")
        for error in result.errors:
            lines.append(f"- {error}\n")
        lines.append("\n")

    # Prerequisites
    if result.prerequisites:
        lines.append("## Prerequisites\n")
        lines.append("| Requirement | Version | Installation |")
        lines.append("|-------------|---------|--------------|")
        for prereq in result.prerequisites:
            lines.append(f"| {prereq.name} | {prereq.version} | `{prereq.installation_command}` |")
        lines.append("")

    # Environment Variables
    if result.env_variables:
        lines.append("## Environment Variables\n")

        # Required variables
        required = [v for v in result.env_variables if v.required]
        if required:
            lines.append("### Required Variables\n")
            lines.append("| Variable | Purpose | Example | Source |")
            lines.append("|----------|---------|---------|--------|")
            for var in sorted(required, key=lambda x: x.name):
                source = f"{var.source_file}:{var.line_number}" if var.source_file else "-"
                lines.append(f"| `{var.name}` | {var.purpose or '-'} | {var.example_value or '-'} | {source} |")
            lines.append("")

        # Optional variables
        optional = [v for v in result.env_variables if not v.required]
        if optional:
            lines.append("### Optional Variables\n")
            lines.append("| Variable | Purpose | Default | Source |")
            lines.append("|----------|---------|---------|--------|")
            for var in sorted(optional, key=lambda x: x.name):
                source = f"{var.source_file}:{var.line_number}" if var.source_file else "-"
                lines.append(f"| `{var.name}` | {var.purpose or '-'} | {var.default or '-'} | {source} |")
            lines.append("")

    # Startup Sequence
    if result.startup_sequence:
        lines.append("## Startup Sequence\n")
        lines.append("```bash")
        for step in result.startup_sequence:
            lines.append(f"# Step {step.step_number}: {step.description}")
            lines.append(step.command)
        lines.append("```\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze project environment configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --format markdown
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

    args = parser.parse_args()

    # Analyze project
    result = analyze_project(args.project_path)

    # Output results
    if args.format == "json":
        print(output_json(result))
    else:
        print(output_markdown(result))

    # Return appropriate exit code
    sys.exit(1 if result.errors and not result.env_variables else 0)


if __name__ == "__main__":
    main()
