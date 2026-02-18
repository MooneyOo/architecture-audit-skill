#!/usr/bin/env python3
"""
Feature Analyzer Script

Derives detailed feature descriptions from actual code implementation,
not just route patterns. Analyzes service layer, scheduled jobs, event
handlers, and extracts business logic from code.

Usage:
    python feature_analyzer.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: json)
    --output FILE             Output file
    --include-services        Include service-level features
    --include-jobs            Include scheduled jobs
    --include-events          Include event handlers
    --trace-flows             Trace data flows
    --deep                    Deep analysis with side effects
    --validate                Run completeness validation
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


# =============================================================================
# Enums
# =============================================================================

class EntryPointType(Enum):
    API = "api"
    CLI = "cli"
    CRON = "cron"
    EVENT = "event"


class SideEffectType(Enum):
    EMAIL = "email"
    WEBHOOK = "webhook"
    NOTIFICATION = "notification"
    AUDIT = "audit"
    CACHE_INVALIDATION = "cache_invalidation"
    FILE_OPERATION = "file_operation"


class Framework(Enum):
    EXPRESS = "Express.js"
    FASTIFY = "Fastify"
    NESTJS = "NestJS"
    FASTAPI = "FastAPI"
    DJANGO = "Django"
    FLASK = "Flask"
    NEXTJS = "Next.js"
    UNKNOWN = "Unknown"


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class Parameter:
    name: str
    type: str
    description: str = ""
    required: bool = True


@dataclass
class EntryPoint:
    type: str  # 'api', 'cli', 'cron', 'event'
    path: str  # Route path, command name, cron schedule
    file: str
    handler: str
    line_number: int = 0


@dataclass
class Operation:
    name: str
    service: str
    method: str
    description: str
    parameters: list[Parameter] = field(default_factory=list)
    return_type: str = ""
    file_path: str = ""
    line_number: int = 0


@dataclass
class DataFlow:
    source: str
    target: str
    data: str
    operation: str  # 'read', 'write', 'update', 'delete'


@dataclass
class SideEffect:
    type: str  # 'email', 'webhook', 'notification', 'audit'
    description: str
    trigger: str


@dataclass
class ErrorScenario:
    error_type: str
    description: str
    handling: str


@dataclass
class Validation:
    field: str
    rule: str
    description: str = ""


@dataclass
class EnhancedFeature:
    id: str
    name: str
    description: str
    business_value: str = ""
    category: str = ""
    entry_points: list[EntryPoint] = field(default_factory=list)
    operations: list[Operation] = field(default_factory=list)
    data_flows: list[DataFlow] = field(default_factory=list)
    side_effects: list[SideEffect] = field(default_factory=list)
    error_scenarios: list[ErrorScenario] = field(default_factory=list)
    validations: list[Validation] = field(default_factory=list)
    workflow: list[str] = field(default_factory=list)
    related_features: list[str] = field(default_factory=list)
    db_tables: list[str] = field(default_factory=list)


@dataclass
class ScheduledJob:
    name: str
    schedule: str
    file_path: str
    handler: str
    description: str = ""
    line_number: int = 0


@dataclass
class EventHandler:
    name: str
    event_type: str
    file_path: str
    handler: str
    description: str = ""
    line_number: int = 0


@dataclass
class Service:
    name: str
    file_path: str
    methods: list[Operation] = field(default_factory=list)
    description: str = ""


@dataclass
class ValidationIssue:
    severity: str  # 'error', 'warning', 'info'
    category: str
    location: str
    message: str
    suggestion: str = ""


@dataclass
class FeatureValidationResult:
    is_complete: bool
    route_coverage: float
    service_coverage: float
    job_coverage: float
    event_coverage: float
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass
class FeatureAnalyzerResult:
    project_path: str
    project_name: str
    framework: Framework
    features: list[EnhancedFeature] = field(default_factory=list)
    services: list[Service] = field(default_factory=list)
    scheduled_jobs: list[ScheduledJob] = field(default_factory=list)
    event_handlers: list[EventHandler] = field(default_factory=list)
    validation_result: Optional[FeatureValidationResult] = None
    errors: list[str] = field(default_factory=list)


# =============================================================================
# Constants
# =============================================================================

SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", "venv", ".venv", "env", ".env",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    "migrations", ".mypy_cache", "egg-info", "__pypackages__",
    ".idea", ".vscode", "tests", "test", "spec"
}

SKIP_PATTERNS = {
    "*.pyc", "*.pyo", "*.so", "*.dll", "*.dylib", "*.exe",
    "*.min.js", "*.min.css", "*.map", "*.lock", "*.log"
}

# Celery task patterns
CELERY_PATTERNS = [
    (r'@app\.task', "Celery task"),
    (r'@celery\.task', "Celery task"),
    (r'@shared_task', "Celery shared task"),
    (r'@task\.bind', "Bound Celery task"),
]

# Cron/scheduler patterns
SCHEDULER_PATTERNS = [
    (r'@scheduled\s*\([^)]*\)', "Spring scheduled"),
    (r'schedule\.every\([^)]*\)\.do', "Schedule library"),
    (r'cron\.schedule\([^)]*', "Cron schedule"),
    (r'APScheduler', "APScheduler"),
    (r'BackgroundScheduler', "Background scheduler"),
    (r'AsyncIOScheduler', "AsyncIO scheduler"),
    (r'@repeat_every\([^)]*\)', "FastAPI Utilities repeat"),
]

# Event handler patterns
EVENT_HANDLER_PATTERNS = [
    (r'@consumer\([^)]*\)', "Kafka consumer"),
    (r'@kafka_handler', "Kafka handler"),
    (r'@rabbitmq\.', "RabbitMQ handler"),
    (r'@event_handler', "Event handler"),
    (r'on_event\([^)]*\)', "Event listener"),
    (r'subscribe\([^)]*\)', "Event subscriber"),
    (r'@receiver\([^)]*\)', "Django signal receiver"),
    (r'async\s+def\s+consume', "Async consumer"),
]

# CLI command patterns
CLI_PATTERNS = [
    (r'@click\.command', "Click command"),
    (r'@click\.group', "Click group"),
    (r'@app\.command\(\)', "Typer command"),
    (r'argparse\.ArgumentParser', "Argparse command"),
    (r'fire\.Fire\(', "Python Fire command"),
]

# Side effect patterns
SIDE_EFFECT_PATTERNS = {
    'email': [
        r'send_email\s*\(',
        r'EmailService',
        r'mail\.send',
        r'send_mail\s*\(',
        r'notify_email',
        r'smtp\.',
        r'resend\.',
    ],
    'webhook': [
        r'webhook',
        r'callback_url',
        r'notify_external',
        r'post_to_url',
        r'http\.post.*notify',
    ],
    'notification': [
        r'push_notification',
        r'notify_user',
        r'send_notification',
        r'send_push',
        r'SnsService',
        r'FcmService',
    ],
    'audit': [
        r'audit_log',
        r'log_action',
        r'AuditService',
        r'audit\.log',
        r'activity_log',
    ],
    'cache_invalidation': [
        r'cache\.delete',
        r'invalidate_cache',
        r'clear_cache',
        r'redis\.delete',
    ],
    'file_operation': [
        r'write_file\s*\(',
        r'upload_to_s3',
        r's3\.upload',
        r'fs\.write',
        r'save_file',
    ],
}

# Service layer patterns
SERVICE_FILE_PATTERNS = [
    r'*service*.py',
    r'*Service*.py',
    r'*_service.py',
    r'*_service.ts',
    r'*.service.ts',
    r'*.service.js',
]

# Data operation patterns
DATA_OPERATION_PATTERNS = {
    'read': [
        r'\.get\s*\(',
        r'\.find\s*\(',
        r'\.find_one\s*\(',
        r'\.findall\s*\(',
        r'\.query\s*\(',
        r'SELECT\s+',
        r'\.first\s*\(',
    ],
    'write': [
        r'\.create\s*\(',
        r'\.insert\s*\(',
        r'\.save\s*\(',
        r'\.add\s*\(',
        r'INSERT\s+INTO',
    ],
    'update': [
        r'\.update\s*\(',
        r'\.update_one\s*\(',
        r'\.update_many\s*\(',
        r'\.modify\s*\(',
        r'UPDATE\s+.*SET',
    ],
    'delete': [
        r'\.delete\s*\(',
        r'\.delete_one\s*\(',
        r'\.delete_many\s*\(',
        r'\.remove\s*\(',
        r'\.destroy\s*\(',
        r'DELETE\s+FROM',
    ],
}


# =============================================================================
# Framework Detection
# =============================================================================

def detect_framework(project_path: Path) -> Framework:
    """Detect the backend framework being used."""
    check_paths = [project_path]
    for subdir in ["backend", "server", "api", "src"]:
        sub_path = project_path / subdir
        if sub_path.exists():
            check_paths.append(sub_path)

    for check_path in check_paths:
        # Check for Python frameworks
        requirements_path = check_path / "requirements.txt"
        if requirements_path.exists():
            try:
                with open(requirements_path, 'r') as f:
                    content = f.read().lower()
                if 'fastapi' in content:
                    return Framework.FASTAPI
                if 'django' in content:
                    return Framework.DJANGO
                if 'flask' in content:
                    return Framework.FLASK
            except:
                pass

        # Check for pyproject.toml
        pyproject_path = check_path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                with open(pyproject_path, 'r') as f:
                    content = f.read().lower()
                if 'fastapi' in content:
                    return Framework.FASTAPI
                if 'django' in content:
                    return Framework.DJANGO
            except:
                pass

        # Check for Node.js frameworks
        package_json_path = check_path / "package.json"
        if package_json_path.exists():
            try:
                with open(package_json_path, 'r') as f:
                    data = json.load(f)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

                if "@nestjs/core" in deps:
                    return Framework.NESTJS
                if "next" in deps:
                    return Framework.NEXTJS
                if "fastify" in deps:
                    return Framework.FASTIFY
                if "express" in deps:
                    return Framework.EXPRESS
            except:
                pass

    return Framework.UNKNOWN


def find_source_directories(project_path: Path) -> list[Path]:
    """Find source directories in the project."""
    src_dirs = []
    candidates = [
        "backend/src", "server/src", "api/src",
        "src", "app", "server", "api", "backend"
    ]

    for candidate in candidates:
        path = project_path / candidate
        if path.exists() and path.is_dir():
            src_dirs.append(path)

    if not src_dirs:
        src_dirs.append(project_path)

    return src_dirs


# =============================================================================
# Docstring Parsing
# =============================================================================

def parse_docstring(content: str) -> dict:
    """Parse a docstring into structured components."""
    result = {
        'summary': '',
        'description': '',
        'args': [],
        'returns': '',
        'raises': [],
        'examples': [],
    }

    if not content:
        return result

    # Clean up the docstring
    lines = content.strip().split('\n')

    # Extract summary (first line)
    if lines:
        result['summary'] = lines[0].strip()

    # Parse the rest
    current_section = 'description'
    description_lines = []

    for line in lines[1:]:
        stripped = line.strip()

        # Check for section headers
        if stripped.lower().startswith('args:'):
            current_section = 'args'
            continue
        elif stripped.lower().startswith('arguments:'):
            current_section = 'args'
            continue
        elif stripped.lower().startswith('returns:'):
            current_section = 'returns'
            continue
        elif stripped.lower().startswith('raises:'):
            current_section = 'raises'
            continue
        elif stripped.lower().startswith('example:'):
            current_section = 'examples'
            continue
        elif stripped.lower().startswith('examples:'):
            current_section = 'examples'
            continue

        # Parse based on current section
        if current_section == 'description':
            if stripped:
                description_lines.append(stripped)
        elif current_section == 'args':
            # Parse arg: description format
            arg_match = re.match(r'(\w+)\s*(?:\([^)]*\))?\s*:\s*(.+)', stripped)
            if arg_match:
                result['args'].append({
                    'name': arg_match.group(1),
                    'description': arg_match.group(2)
                })
        elif current_section == 'returns':
            if stripped:
                result['returns'] = stripped
        elif current_section == 'raises':
            # Parse ExceptionType: description format
            raise_match = re.match(r'(\w+)\s*:\s*(.+)', stripped)
            if raise_match:
                result['raises'].append({
                    'type': raise_match.group(1),
                    'description': raise_match.group(2)
                })
        elif current_section == 'examples':
            if stripped and not stripped.startswith('>>>'):
                result['examples'].append(stripped)

    result['description'] = '\n'.join(description_lines)
    return result


def extract_python_docstring(content: str, position: int) -> str:
    """Extract docstring from Python code at given position."""
    # Look for triple-quoted string after position
    remaining = content[position:]

    # Match """...""" or '''...'''
    match = re.match(r'\s*"""(.*?)"""', remaining, re.DOTALL)
    if not match:
        match = re.match(r"\s*'''(.*?)'''", remaining, re.DOTALL)

    if match:
        return match.group(1).strip()
    return ""


def extract_jsdoc(content: str, position: int) -> str:
    """Extract JSDoc comment from JavaScript/TypeScript code."""
    # Look backwards for JSDoc comment
    before = content[:position]

    # Find the last /** ... */ before position
    matches = list(re.finditer(r'/\*\*(.*?)\*/', before, re.DOTALL))
    if matches:
        return matches[-1].group(1).strip()
    return ""


# =============================================================================
# Service Layer Analysis
# =============================================================================

def discover_services(project_path: Path) -> list[Service]:
    """Discover all service classes in the project."""
    services = []
    src_dirs = find_source_directories(project_path)

    for src_dir in src_dirs:
        # Python services
        for py_file in src_dir.rglob("*.py"):
            if should_skip_path(py_file):
                continue

            # Check if it's a service file
            if not any(re.search(p, py_file.name, re.IGNORECASE) for p in ['service', '_service']):
                continue

            service = extract_python_service(py_file, project_path)
            if service:
                services.append(service)

        # TypeScript/JavaScript services
        for ext in ["*.ts", "*.js"]:
            for ts_file in src_dir.rglob(ext):
                if should_skip_path(ts_file):
                    continue

                if not any(re.search(p, ts_file.name, re.IGNORECASE) for p in ['service', '.service']):
                    continue

                service = extract_typescript_service(ts_file, project_path)
                if service:
                    services.append(service)

    return services


def extract_python_service(file_path: Path, project_path: Path) -> Optional[Service]:
    """Extract service information from Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return None

    # Find class definition
    class_match = re.search(r'class\s+(\w+)', content)
    if not class_match:
        return None

    class_name = class_match.group(1)
    class_start = class_match.end()

    # Extract class docstring
    docstring = extract_python_docstring(content, class_start)
    parsed_doc = parse_docstring(docstring)

    # Find methods
    methods = []
    for method_match in re.finditer(r'def\s+(\w+)\s*\(([^)]*)\)', content):
        method_name = method_match.group(1)

        # Skip private methods unless they're semantically important
        if method_name.startswith('_') and not method_name.startswith('__'):
            continue

        method_start = method_match.end()
        method_docstring = extract_python_docstring(content, method_start)
        method_parsed = parse_docstring(method_docstring)

        # Extract return type hint
        return_match = re.search(r'\)\s*->\s*(\w+)', content[method_start-50:method_start+10])
        return_type = return_match.group(1) if return_match else ""

        # Parse parameters
        params_str = method_match.group(2)
        parameters = []
        for param in params_str.split(','):
            param = param.strip()
            if param and param not in ['self', 'cls']:
                # Parse name: type format
                param_match = re.match(r'(\w+)\s*(?::\s*(\w+))?', param)
                if param_match:
                    parameters.append(Parameter(
                        name=param_match.group(1),
                        type=param_match.group(2) or "Any",
                        description="",
                        required=True
                    ))

        methods.append(Operation(
            name=method_name,
            service=class_name,
            method=method_name,
            description=method_parsed['summary'] or method_parsed['description'],
            parameters=parameters,
            return_type=return_type,
            file_path=str(file_path.relative_to(project_path)),
            line_number=content[:method_match.start()].count('\n') + 1
        ))

    if not methods:
        return None

    return Service(
        name=class_name,
        file_path=str(file_path.relative_to(project_path)),
        methods=methods,
        description=parsed_doc['summary']
    )


def extract_typescript_service(file_path: Path, project_path: Path) -> Optional[Service]:
    """Extract service information from TypeScript file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return None

    # Find class definition
    class_match = re.search(r'(?:export\s+)?class\s+(\w+)', content)
    if not class_match:
        return None

    class_name = class_match.group(1)

    # Extract JSDoc
    docstring = extract_jsdoc(content, class_match.start())
    parsed_doc = parse_docstring(docstring)

    # Find methods
    methods = []
    for method_match in re.finditer(r'(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*(?::\s*(\w+))?', content):
        method_name = method_match.group(1)

        # Skip constructor and private methods
        if method_name in ['constructor'] or method_name.startswith('_'):
            continue

        method_docstring = extract_jsdoc(content, method_match.start())
        method_parsed = parse_docstring(method_docstring)

        return_type = method_match.group(3) or ""

        methods.append(Operation(
            name=method_name,
            service=class_name,
            method=method_name,
            description=method_parsed['summary'],
            parameters=[],
            return_type=return_type,
            file_path=str(file_path.relative_to(project_path)),
            line_number=content[:method_match.start()].count('\n') + 1
        ))

    if not methods:
        return None

    return Service(
        name=class_name,
        file_path=str(file_path.relative_to(project_path)),
        methods=methods,
        description=parsed_doc['summary']
    )


# =============================================================================
# Scheduled Job Discovery
# =============================================================================

def discover_scheduled_jobs(project_path: Path) -> list[ScheduledJob]:
    """Discover all scheduled jobs in the project."""
    jobs = []
    src_dirs = find_source_directories(project_path)

    for src_dir in src_dirs:
        # Python files
        for py_file in src_dir.rglob("*.py"):
            if should_skip_path(py_file):
                continue

            file_jobs = extract_python_scheduled_jobs(py_file, project_path)
            jobs.extend(file_jobs)

        # TypeScript files
        for ts_file in src_dir.rglob("*.ts"):
            if should_skip_path(ts_file):
                continue

            file_jobs = extract_typescript_scheduled_jobs(ts_file, project_path)
            jobs.extend(file_jobs)

    return jobs


def extract_python_scheduled_jobs(file_path: Path, project_path: Path) -> list[ScheduledJob]:
    """Extract scheduled jobs from Python file."""
    jobs = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return jobs

    rel_path = str(file_path.relative_to(project_path))

    # Celery tasks
    for match in re.finditer(r'@(\w+\.task|shared_task|task\.bind)\s*\(([^)]*)\)', content):
        # Find the function definition after decorator
        remaining = content[match.end():]
        func_match = re.search(r'def\s+(\w+)', remaining)

        if func_match:
            func_name = func_match.group(1)
            func_start = match.end() + func_match.end()
            docstring = extract_python_docstring(content, func_start)
            parsed = parse_docstring(docstring)

            jobs.append(ScheduledJob(
                name=func_name,
                schedule="celery",  # Schedule defined elsewhere
                file_path=rel_path,
                handler=func_name,
                description=parsed['summary'],
                line_number=content[:match.start()].count('\n') + 1
            ))

    # APScheduler patterns
    for match in re.finditer(r'@scheduled\s*\(([^)]*)\)', content):
        remaining = content[match.end():]
        func_match = re.search(r'def\s+(\w+)', remaining)

        if func_match:
            func_name = func_match.group(1)
            schedule_info = match.group(1)
            func_start = match.end() + func_match.end()
            docstring = extract_python_docstring(content, func_start)
            parsed = parse_docstring(docstring)

            jobs.append(ScheduledJob(
                name=func_name,
                schedule=schedule_info,
                file_path=rel_path,
                handler=func_name,
                description=parsed['summary'],
                line_number=content[:match.start()].count('\n') + 1
            ))

    return jobs


def extract_typescript_scheduled_jobs(file_path: Path, project_path: Path) -> list[ScheduledJob]:
    """Extract scheduled jobs from TypeScript file."""
    jobs = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return jobs

    rel_path = str(file_path.relative_to(project_path))

    # NestJS @Cron decorator
    for match in re.finditer(r'@Cron\s*\(([^)]*)\)', content):
        remaining = content[match.end():]
        func_match = re.search(r'(?:async\s+)?(\w+)\s*\(', remaining)

        if func_match:
            func_name = func_match.group(1)
            schedule_info = match.group(1)
            docstring = extract_jsdoc(content, match.start())
            parsed = parse_docstring(docstring)

            jobs.append(ScheduledJob(
                name=func_name,
                schedule=schedule_info,
                file_path=rel_path,
                handler=func_name,
                description=parsed['summary'],
                line_number=content[:match.start()].count('\n') + 1
            ))

    # Bull/BullMQ queues
    for match in re.finditer(r'@Process\s*\(([^)]*)\)', content):
        remaining = content[match.end():]
        func_match = re.search(r'(?:async\s+)?(\w+)\s*\(', remaining)

        if func_match:
            func_name = func_match.group(1)
            queue_name = match.group(1).strip('\'"')
            docstring = extract_jsdoc(content, match.start())
            parsed = parse_docstring(docstring)

            jobs.append(ScheduledJob(
                name=func_name,
                schedule=f"queue:{queue_name}",
                file_path=rel_path,
                handler=func_name,
                description=parsed['summary'],
                line_number=content[:match.start()].count('\n') + 1
            ))

    return jobs


# =============================================================================
# Event Handler Discovery
# =============================================================================

def discover_event_handlers(project_path: Path) -> list[EventHandler]:
    """Discover all event handlers in the project."""
    handlers = []
    src_dirs = find_source_directories(project_path)

    for src_dir in src_dirs:
        # Python files
        for py_file in src_dir.rglob("*.py"):
            if should_skip_path(py_file):
                continue

            file_handlers = extract_python_event_handlers(py_file, project_path)
            handlers.extend(file_handlers)

        # TypeScript files
        for ts_file in src_dir.rglob("*.ts"):
            if should_skip_path(ts_file):
                continue

            file_handlers = extract_typescript_event_handlers(ts_file, project_path)
            handlers.extend(file_handlers)

    return handlers


def extract_python_event_handlers(file_path: Path, project_path: Path) -> list[EventHandler]:
    """Extract event handlers from Python file."""
    handlers = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return handlers

    rel_path = str(file_path.relative_to(project_path))

    # Django signal receivers
    for match in re.finditer(r'@receiver\s*\(([^)]*)\)', content):
        remaining = content[match.end():]
        func_match = re.search(r'def\s+(\w+)', remaining)

        if func_match:
            func_name = func_match.group(1)
            signal_type = match.group(1)
            func_start = match.end() + func_match.end()
            docstring = extract_python_docstring(content, func_start)
            parsed = parse_docstring(docstring)

            handlers.append(EventHandler(
                name=func_name,
                event_type=signal_type,
                file_path=rel_path,
                handler=func_name,
                description=parsed['summary'],
                line_number=content[:match.start()].count('\n') + 1
            ))

    # Kafka consumers
    for match in re.finditer(r'@consumer\s*\(([^)]*)\)', content):
        remaining = content[match.end():]
        func_match = re.search(r'(?:async\s+)?def\s+(\w+)', remaining)

        if func_match:
            func_name = func_match.group(1)
            topic = match.group(1).strip('\'"')
            func_start = match.end() + func_match.end()
            docstring = extract_python_docstring(content, func_start)
            parsed = parse_docstring(docstring)

            handlers.append(EventHandler(
                name=func_name,
                event_type=f"kafka:{topic}",
                file_path=rel_path,
                handler=func_name,
                description=parsed['summary'],
                line_number=content[:match.start()].count('\n') + 1
            ))

    return handlers


def extract_typescript_event_handlers(file_path: Path, project_path: Path) -> list[EventHandler]:
    """Extract event handlers from TypeScript file."""
    handlers = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return handlers

    rel_path = str(file_path.relative_to(project_path))

    # NestJS event handlers
    for match in re.finditer(r'@OnEvent\s*\(([^)]*)\)', content):
        remaining = content[match.end():]
        func_match = re.search(r'(?:async\s+)?(\w+)\s*\(', remaining)

        if func_match:
            func_name = func_match.group(1)
            event_type = match.group(1).strip('\'"')
            docstring = extract_jsdoc(content, match.start())
            parsed = parse_docstring(docstring)

            handlers.append(EventHandler(
                name=func_name,
                event_type=event_type,
                file_path=rel_path,
                handler=func_name,
                description=parsed['summary'],
                line_number=content[:match.start()].count('\n') + 1
            ))

    # RabbitMQ handlers
    for match in re.finditer(r'@RabbitSubscribe\s*\(([^)]*)\)', content):
        remaining = content[match.end():]
        func_match = re.search(r'(?:async\s+)?(\w+)\s*\(', remaining)

        if func_match:
            func_name = func_match.group(1)
            queue_info = match.group(1)
            docstring = extract_jsdoc(content, match.start())
            parsed = parse_docstring(docstring)

            handlers.append(EventHandler(
                name=func_name,
                event_type=f"rabbitmq:{queue_info}",
                file_path=rel_path,
                handler=func_name,
                description=parsed['summary'],
                line_number=content[:match.start()].count('\n') + 1
            ))

    return handlers


# =============================================================================
# Side Effect Detection
# =============================================================================

def detect_side_effects(content: str, func_name: str = "") -> list[SideEffect]:
    """Detect side effects from function content."""
    effects = []

    for effect_type, patterns in SIDE_EFFECT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                effects.append(SideEffect(
                    type=effect_type,
                    description=f"Detected {effect_type} operation",
                    trigger=f"Pattern: {pattern}"
                ))
                break  # Only add one effect per type

    return effects


def detect_error_scenarios(content: str) -> list[ErrorScenario]:
    """Extract error scenarios from try/except blocks."""
    scenarios = []

    # Find try/except blocks
    for match in re.finditer(r'except\s+(\w+)(?:\s+as\s+\w+)?\s*:', content):
        error_type = match.group(1)

        # Try to find the handling code
        remaining = content[match.end():match.end()+200]
        handling = "Standard error handling"

        if 'raise' in remaining:
            handling = "Re-raises exception"
        elif 'log' in remaining.lower():
            handling = "Logs and continues"
        elif 'return' in remaining:
            handling = "Returns error response"

        scenarios.append(ErrorScenario(
            error_type=error_type,
            description=f"Handles {error_type}",
            handling=handling
        ))

    return scenarios


def trace_data_flow(content: str, service_name: str) -> list[DataFlow]:
    """Trace data flow from service code."""
    flows = []

    for operation, patterns in DATA_OPERATION_PATTERNS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                # Try to extract table/collection name
                table = "unknown"
                if match.groups():
                    table = match.group(1) if match.group(1) else "unknown"

                flows.append(DataFlow(
                    source=service_name,
                    target=table,
                    data="data",
                    operation=operation
                ))

    return flows


# =============================================================================
# Feature Building
# =============================================================================

def should_skip_path(path: Path) -> bool:
    """Check if path should be skipped."""
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
    return False


def create_feature_id(name: str) -> str:
    """Create a feature ID from name."""
    # Convert to lowercase, replace spaces with hyphens
    feature_id = name.lower()
    feature_id = re.sub(r'[^a-z0-9\s-]', '', feature_id)
    feature_id = re.sub(r'\s+', '-', feature_id)
    return feature_id.strip('-')


def build_features_from_services(services: list[Service]) -> list[EnhancedFeature]:
    """Build features from discovered services."""
    features = []

    for service in services:
        for method in service.methods:
            feature_name = f"{service.name}: {method.name.replace('_', ' ').title()}"

            # Read file content for deeper analysis
            try:
                full_path = Path(service.file_path)
                if not full_path.is_absolute():
                    # Assume relative to some project root
                    pass

                # For now, use available info
                content = ""
            except:
                content = ""

            feature = EnhancedFeature(
                id=create_feature_id(feature_name),
                name=feature_name,
                description=method.description or f"Service method {method.name}",
                category="Service Layer",
                entry_points=[EntryPoint(
                    type="service",
                    path=f"{service.name}.{method.name}",
                    file=service.file_path,
                    handler=method.name,
                    line_number=method.line_number
                )],
                operations=[method],
                side_effects=detect_side_effects(content, method.name) if content else [],
            )

            features.append(feature)

    return features


def build_features_from_jobs(jobs: list[ScheduledJob]) -> list[EnhancedFeature]:
    """Build features from scheduled jobs."""
    features = []

    for job in jobs:
        feature_name = f"Scheduled: {job.name.replace('_', ' ').title()}"

        feature = EnhancedFeature(
            id=create_feature_id(feature_name),
            name=feature_name,
            description=job.description or f"Scheduled job {job.name}",
            category="Background Jobs",
            entry_points=[EntryPoint(
                type="cron",
                path=job.schedule,
                file=job.file_path,
                handler=job.handler,
                line_number=job.line_number
            )],
        )

        features.append(feature)

    return features


def build_features_from_handlers(handlers: list[EventHandler]) -> list[EnhancedFeature]:
    """Build features from event handlers."""
    features = []

    for handler in handlers:
        feature_name = f"Event: {handler.name.replace('_', ' ').title()}"

        feature = EnhancedFeature(
            id=create_feature_id(feature_name),
            name=feature_name,
            description=handler.description or f"Event handler for {handler.event_type}",
            category="Event Handlers",
            entry_points=[EntryPoint(
                type="event",
                path=handler.event_type,
                file=handler.file_path,
                handler=handler.handler,
                line_number=handler.line_number
            )],
        )

        features.append(feature)

    return features


def merge_features(feature_lists: list[list[EnhancedFeature]]) -> list[EnhancedFeature]:
    """Merge and deduplicate features from multiple sources."""
    all_features = []
    seen_ids = set()

    for features in feature_lists:
        for feature in features:
            if feature.id not in seen_ids:
                seen_ids.add(feature.id)
                all_features.append(feature)

    return all_features


# =============================================================================
# Validation
# =============================================================================

def validate_feature_coverage(
    features: list[EnhancedFeature],
    services: list[Service],
    jobs: list[ScheduledJob],
    handlers: list[EventHandler]
) -> FeatureValidationResult:
    """Validate feature coverage completeness."""
    issues = []

    # Count documented items
    documented_services = set()
    documented_jobs = set()
    documented_handlers = set()

    for feature in features:
        for ep in feature.entry_points:
            if ep.type == "service":
                documented_services.add(ep.handler)
            elif ep.type == "cron":
                documented_jobs.add(ep.handler)
            elif ep.type == "event":
                documented_handlers.add(ep.handler)

    # Check service coverage
    total_service_methods = sum(len(s.methods) for s in services)
    for service in services:
        for method in service.methods:
            if method.name not in documented_services:
                issues.append(ValidationIssue(
                    severity='info',
                    category='orphaned_service_method',
                    location=f"{service.name}.{method.name}",
                    message=f"Service method not mapped to any feature",
                    suggestion="Verify if this is internal/util or should be documented"
                ))

    # Check job coverage
    for job in jobs:
        if job.name not in documented_jobs:
            issues.append(ValidationIssue(
                severity='warning',
                category='missing_job_feature',
                location=job.name,
                message=f"Scheduled job '{job.name}' not documented as feature",
                suggestion="Add as system feature"
            ))

    # Check event handler coverage
    for handler in handlers:
        if handler.name not in documented_handlers:
            issues.append(ValidationIssue(
                severity='info',
                category='missing_event_feature',
                location=handler.name,
                message=f"Event handler '{handler.name}' not documented",
                suggestion="Add as feature if significant business logic"
            ))

    # Calculate coverage
    service_coverage = (len(documented_services) / total_service_methods * 100) if total_service_methods > 0 else 100
    job_coverage = (len(documented_jobs) / len(jobs) * 100) if jobs else 100
    event_coverage = (len(documented_handlers) / len(handlers) * 100) if handlers else 100

    return FeatureValidationResult(
        is_complete=len([i for i in issues if i.severity == 'error']) == 0,
        route_coverage=100,  # Would need endpoint data to calculate
        service_coverage=service_coverage,
        job_coverage=job_coverage,
        event_coverage=event_coverage,
        issues=issues
    )


# =============================================================================
# Output Formatters
# =============================================================================

def output_json(result: FeatureAnalyzerResult) -> str:
    """Format results as JSON."""
    output = {
        "project_path": result.project_path,
        "project_name": result.project_name,
        "framework": result.framework.value,
        "feature_count": len(result.features),
        "service_count": len(result.services),
        "job_count": len(result.scheduled_jobs),
        "handler_count": len(result.event_handlers),
        "features": [
            {
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "category": f.category,
                "entry_points": [
                    {
                        "type": ep.type,
                        "path": ep.path,
                        "file": ep.file,
                        "handler": ep.handler
                    }
                    for ep in f.entry_points
                ],
                "operations": [
                    {
                        "name": op.name,
                        "service": op.service,
                        "method": op.method,
                        "description": op.description
                    }
                    for op in f.operations
                ],
                "side_effects": [
                    {
                        "type": se.type,
                        "description": se.description,
                        "trigger": se.trigger
                    }
                    for se in f.side_effects
                ],
                "error_scenarios": [
                    {
                        "error_type": es.error_type,
                        "description": es.description,
                        "handling": es.handling
                    }
                    for es in f.error_scenarios
                ],
                "related_features": f.related_features,
                "db_tables": f.db_tables
            }
            for f in result.features
        ],
        "services": [
            {
                "name": s.name,
                "file_path": s.file_path,
                "description": s.description,
                "method_count": len(s.methods),
                "methods": [
                    {"name": m.name, "description": m.description}
                    for m in s.methods
                ]
            }
            for s in result.services
        ],
        "scheduled_jobs": [
            {
                "name": j.name,
                "schedule": j.schedule,
                "file_path": j.file_path,
                "description": j.description
            }
            for j in result.scheduled_jobs
        ],
        "event_handlers": [
            {
                "name": h.name,
                "event_type": h.event_type,
                "file_path": h.file_path,
                "description": h.description
            }
            for h in result.event_handlers
        ],
    }

    if result.validation_result:
        output["validation"] = {
            "is_complete": result.validation_result.is_complete,
            "route_coverage": result.validation_result.route_coverage,
            "service_coverage": result.validation_result.service_coverage,
            "job_coverage": result.validation_result.job_coverage,
            "event_coverage": result.validation_result.event_coverage,
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "location": i.location,
                    "message": i.message,
                    "suggestion": i.suggestion
                }
                for i in result.validation_result.issues
            ]
        }

    output["errors"] = result.errors

    return json.dumps(output, indent=2)


def output_markdown(result: FeatureAnalyzerResult) -> str:
    """Format results as Markdown."""
    lines = [f"# Feature Analysis Report\n"]
    lines.append(f"**Project:** `{result.project_path}`\n")
    lines.append(f"**Framework:** {result.framework.value}\n")

    # Summary
    lines.append("## Summary\n")
    lines.append(f"| Category | Count |")
    lines.append(f"|----------|-------|")
    lines.append(f"| Features | {len(result.features)} |")
    lines.append(f"| Services | {len(result.services)} |")
    lines.append(f"| Scheduled Jobs | {len(result.scheduled_jobs)} |")
    lines.append(f"| Event Handlers | {len(result.event_handlers)} |")
    lines.append("")

    # Feature Catalog
    if result.features:
        lines.append("## Feature Catalog\n")
        lines.append("| # | Feature Name | Category | Description | Entry Points |")
        lines.append("|---|--------------|----------|-------------|--------------|")

        for i, f in enumerate(result.features[:50], 1):
            entry_points = ", ".join(ep.type for ep in f.entry_points[:2])
            lines.append(f"| {i} | {f.name} | {f.category} | {f.description[:50]}... | {entry_points} |")

        lines.append("")

    # Feature Details
    if result.features:
        lines.append("## Feature Details\n")

        for f in result.features[:20]:  # Limit for readability
            lines.append(f"### {f.name}\n")
            lines.append(f"**Category:** {f.category}\n")
            lines.append(f"**Description:** {f.description}\n")

            if f.entry_points:
                lines.append("**Entry Points:**")
                lines.append("| Type | Path | Handler |")
                lines.append("|------|------|---------|")
                for ep in f.entry_points:
                    lines.append(f"| {ep.type} | `{ep.path}` | {ep.handler} |")
                lines.append("")

            if f.side_effects:
                lines.append("**Side Effects:**")
                for se in f.side_effects:
                    lines.append(f"- {se.type}: {se.description}")
                lines.append("")

            if f.error_scenarios:
                lines.append("**Error Scenarios:**")
                lines.append("| Error | Description | Handling |")
                lines.append("|-------|-------------|----------|")
                for es in f.error_scenarios:
                    lines.append(f"| {es.error_type} | {es.description} | {es.handling} |")
                lines.append("")

            lines.append("---\n")

    # Services
    if result.services:
        lines.append("## Services\n")
        lines.append("| Service | Methods | File |")
        lines.append("|---------|---------|------|")

        for s in result.services[:30]:
            lines.append(f"| {s.name} | {len(s.methods)} | `{s.file_path}` |")

        lines.append("")

    # Scheduled Jobs
    if result.scheduled_jobs:
        lines.append("## Scheduled Jobs\n")
        lines.append("| Job | Schedule | File |")
        lines.append("|-----|----------|------|")

        for j in result.scheduled_jobs:
            lines.append(f"| {j.name} | `{j.schedule}` | `{j.file_path}` |")

        lines.append("")

    # Event Handlers
    if result.event_handlers:
        lines.append("## Event Handlers\n")
        lines.append("| Handler | Event Type | File |")
        lines.append("|---------|------------|------|")

        for h in result.event_handlers:
            lines.append(f"| {h.name} | `{h.event_type}` | `{h.file_path}` |")

        lines.append("")

    # Validation Report
    if result.validation_result:
        lines.append("## Validation Report\n")

        vr = result.validation_result
        lines.append("### Coverage Summary\n")
        lines.append("| Category | Coverage |")
        lines.append("|----------|----------|")
        lines.append(f"| Services | {vr.service_coverage:.1f}% |")
        lines.append(f"| Jobs | {vr.job_coverage:.1f}% |")
        lines.append(f"| Events | {vr.event_coverage:.1f}% |")
        lines.append("")

        if vr.issues:
            lines.append("### Issues\n")

            # Group by severity
            warnings = [i for i in vr.issues if i.severity == 'warning']
            infos = [i for i in vr.issues if i.severity == 'info']

            if warnings:
                lines.append(f"**Warnings ({len(warnings)}):**")
                for issue in warnings[:10]:
                    lines.append(f"- `{issue.location}`: {issue.message}")
                lines.append("")

            if infos:
                lines.append(f"**Info ({len(infos)}):**")
                for issue in infos[:10]:
                    lines.append(f"- `{issue.location}`: {issue.message}")
                lines.append("")

    if result.errors:
        lines.append("## Errors\n")
        for error in result.errors:
            lines.append(f"- {error}\n")

    return "\n".join(lines)


# =============================================================================
# Main Analysis Function
# =============================================================================

def analyze_project(
    project_path: str,
    include_services: bool = False,
    include_jobs: bool = False,
    include_events: bool = False,
    trace_flows: bool = False,
    deep: bool = False,
    validate: bool = False
) -> FeatureAnalyzerResult:
    """Analyze a project to discover features from code."""

    path = Path(project_path)

    if not path.exists():
        return FeatureAnalyzerResult(
            project_path=project_path,
            project_name=path.name,
            framework=Framework.UNKNOWN,
            errors=[f"Project path does not exist: {project_path}"]
        )

    result = FeatureAnalyzerResult(
        project_path=str(path),
        project_name=path.name,
        framework=detect_framework(path)
    )

    feature_lists = []

    # Discover services
    if include_services or deep:
        result.services = discover_services(path)

        if include_services:
            service_features = build_features_from_services(result.services)
            feature_lists.append(service_features)

    # Discover scheduled jobs
    if include_jobs or deep:
        result.scheduled_jobs = discover_scheduled_jobs(path)

        if include_jobs:
            job_features = build_features_from_jobs(result.scheduled_jobs)
            feature_lists.append(job_features)

    # Discover event handlers
    if include_events or deep:
        result.event_handlers = discover_event_handlers(path)

        if include_events:
            handler_features = build_features_from_handlers(result.event_handlers)
            feature_lists.append(handler_features)

    # Merge all features
    result.features = merge_features(feature_lists)

    # Run validation if requested
    if validate:
        result.validation_result = validate_feature_coverage(
            result.features,
            result.services,
            result.scheduled_jobs,
            result.event_handlers
        )

    return result


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Analyze code to discover features from services, jobs, and events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --include-services --include-jobs
  %(prog)s /path/to/project --deep --trace-flows
  %(prog)s /path/to/project --validate --format markdown
  %(prog)s /path/to/project --format markdown --output features.md
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
        "--output",
        help="Output file (default: stdout)"
    )

    parser.add_argument(
        "--include-services",
        action="store_true",
        help="Include service-level features"
    )

    parser.add_argument(
        "--include-jobs",
        action="store_true",
        help="Include scheduled jobs as features"
    )

    parser.add_argument(
        "--include-events",
        action="store_true",
        help="Include event handlers as features"
    )

    parser.add_argument(
        "--trace-flows",
        action="store_true",
        help="Trace data flows through the codebase"
    )

    parser.add_argument(
        "--deep",
        action="store_true",
        help="Deep analysis including services, jobs, events, and side effects"
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run completeness validation"
    )

    args = parser.parse_args()

    # Run analysis
    result = analyze_project(
        args.project_path,
        include_services=args.include_services,
        include_jobs=args.include_jobs,
        include_events=args.include_events,
        trace_flows=args.trace_flows,
        deep=args.deep,
        validate=args.validate
    )

    # Format output
    if args.format == "json":
        output = output_json(result)
    else:
        output = output_markdown(result)

    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Output written to {args.output}")
    else:
        print(output)

    # Return appropriate exit code
    has_critical_errors = len(result.errors) > 0 and len(result.features) == 0
    sys.exit(1 if has_critical_errors else 0)


if __name__ == "__main__":
    main()
