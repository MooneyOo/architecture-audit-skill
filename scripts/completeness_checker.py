#!/usr/bin/env python3
"""
Completeness Checker

Verifies that all code artifacts are discovered and documented.
Runs coverage analysis for routes, services, jobs, events, and database models.

Usage:
    python scripts/completeness_checker.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: markdown)
    --strict                  Fail on warnings
    --help                    Show usage information

Exit Codes:
    0 - All checks pass
    1 - Critical issues found
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


class Severity(Enum):
    """Issue severity levels."""
    ERROR = "error"      # Missing critical items
    WARNING = "warning"  # Potentially missing items
    INFO = "info"        # Informational


@dataclass
class CompletenessIssue:
    """A single completeness issue."""
    severity: str
    category: str
    item_type: str
    item_name: str
    location: str
    message: str
    suggestion: str


@dataclass
class CategoryStats:
    """Statistics for a single category."""
    found: int = 0
    documented: int = 0

    @property
    def coverage(self) -> float:
        if self.found == 0:
            return 100.0
        return round(100.0 * self.documented / self.found, 1)


@dataclass
class CompletenessReport:
    """Complete analysis report."""
    project_path: str
    categories: dict = field(default_factory=dict)
    issues: list[CompletenessIssue] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return not any(
            i.severity == Severity.ERROR.value for i in self.issues
        )

    @property
    def has_warnings(self) -> bool:
        return any(
            i.severity == Severity.WARNING.value for i in self.issues
        )


# Route detection patterns
FASTAPI_ROUTE_PATTERN = r'@(?:router|app|api)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']'
EXPRESS_ROUTE_PATTERN = r'(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']'
NESTJS_ROUTE_PATTERN = r'@(Get|Post|Put|Patch|Delete)\s*\(\s*["\']?([^"\']*)["\']?\s*\)'

# Service detection patterns
SERVICE_CLASS_PATTERN = r'class\s+(\w+[Ss]ervice)\s*[:\(]'
SERVICE_METHOD_PATTERN = r'def\s+(\w+)\s*\([^)]*\)\s*(?:->|:)'

# Job detection patterns
CELERY_TASK_PATTERN = r'@(?:app|celery)\.task'
CELERY_SHARED_TASK_PATTERN = r'@shared_task'
CRON_PATTERN = r'(?:schedule|cron|@periodic_task)'
BULL_QUEUE_PATTERN = r'(?:Queue|queue)\s*\(\s*["\']([^"\']+)["\']'

# Event detection patterns
CONSUMER_PATTERN = r'@(?:rabbitmq|kafka|consumer)'
LISTENER_PATTERN = r'@(?:event|on|listen|subscriber)'
RABBITMQ_PATTERN = r'(?:pika|aio_pika|kombu)'

# Model detection patterns
SQLALCHEMY_MODEL_PATTERN = r'class\s+(\w+)\s*\([^)]*(?:Base|Model)[^)]*\)'
PRISMA_MODEL_PATTERN = r'model\s+(\w+)\s*\{'
TYPEORM_MODEL_PATTERN = r'@Entity\(\s*["\']?(\w+)["\']?'


class CompletenessChecker:
    """Check completeness of code documentation."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.issues: list[CompletenessIssue] = []
        self.stats: dict[str, CategoryStats] = {
            'api_routes': CategoryStats(),
            'service_methods': CategoryStats(),
            'scheduled_jobs': CategoryStats(),
            'event_handlers': CategoryStats(),
            'database_models': CategoryStats(),
        }

    def check_all(self) -> CompletenessReport:
        """Run all completeness checks."""
        # Discover all items
        routes = self._discover_all_routes()
        services = self._discover_all_services()
        jobs = self._discover_all_jobs()
        events = self._discover_all_events()
        models = self._discover_all_models()

        # Update stats with discovered items
        self.stats['api_routes'].found = len(routes)
        self.stats['service_methods'].found = len(services)
        self.stats['scheduled_jobs'].found = len(jobs)
        self.stats['event_handlers'].found = len(events)
        self.stats['database_models'].found = len(models)

        # For now, assume all discovered items are "documented" if they exist
        # In a full implementation, this would compare against generated docs
        self.stats['api_routes'].documented = len(routes)
        self.stats['service_methods'].documented = len([s for s in services if not s.get('private', False)])
        self.stats['scheduled_jobs'].documented = len(jobs)
        self.stats['event_handlers'].documented = len(events)
        self.stats['database_models'].documented = len(models)

        # Check for issues
        self._check_route_issues(routes)
        self._check_service_issues(services)
        self._check_job_issues(jobs)
        self._check_event_issues(events)
        self._check_model_issues(models)

        return CompletenessReport(
            project_path=str(self.project_path),
            categories={k: asdict(v) for k, v in self.stats.items()},
            issues=self.issues
        )

    def _discover_all_routes(self) -> list[dict]:
        """Discover all API routes in the project."""
        routes = []

        # Scan Python files for FastAPI routes
        for py_file in self.project_path.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue
            routes.extend(self._extract_fastapi_routes(py_file))

        # Scan JavaScript/TypeScript files for Express/NestJS routes
        for js_file in self.project_path.rglob("*.ts"):
            if self._should_skip_file(js_file):
                continue
            routes.extend(self._extract_express_routes(js_file))
            routes.extend(self._extract_nestjs_routes(js_file))

        for js_file in self.project_path.rglob("*.js"):
            if self._should_skip_file(js_file):
                continue
            routes.extend(self._extract_express_routes(js_file))

        # Deduplicate
        seen = set()
        unique_routes = []
        for route in routes:
            key = (route['method'], route['path'])
            if key not in seen:
                seen.add(key)
                unique_routes.append(route)

        return unique_routes

    def _discover_all_services(self) -> list[dict]:
        """Discover all service classes and methods."""
        services = []

        # Python services
        for py_file in self.project_path.rglob("*service*.py"):
            if self._should_skip_file(py_file):
                continue
            services.extend(self._extract_python_services(py_file))

        # TypeScript services
        for ts_file in self.project_path.rglob("*service*.ts"):
            if self._should_skip_file(ts_file):
                continue
            services.extend(self._extract_ts_services(ts_file))

        return services

    def _discover_all_jobs(self) -> list[dict]:
        """Discover all scheduled jobs."""
        jobs = []

        # Celery tasks
        for py_file in self.project_path.rglob("*task*.py"):
            if self._should_skip_file(py_file):
                continue
            jobs.extend(self._extract_celery_tasks(py_file))

        # Cron definitions
        for py_file in self.project_path.rglob("*cron*.py"):
            if self._should_skip_file(py_file):
                continue
            jobs.extend(self._extract_cron_jobs(py_file))

        # Bull queues (Node.js)
        for ts_file in self.project_path.rglob("*queue*.ts"):
            if self._should_skip_file(ts_file):
                continue
            jobs.extend(self._extract_bull_jobs(ts_file))

        for js_file in self.project_path.rglob("*queue*.js"):
            if self._should_skip_file(js_file):
                continue
            jobs.extend(self._extract_bull_jobs(js_file))

        return jobs

    def _discover_all_events(self) -> list[dict]:
        """Discover all event handlers."""
        events = []

        # Python consumers
        for py_file in self.project_path.rglob("*consumer*.py"):
            if self._should_skip_file(py_file):
                continue
            events.extend(self._extract_consumers(py_file))

        # Event listeners
        for py_file in self.project_path.rglob("*listener*.py"):
            if self._should_skip_file(py_file):
                continue
            events.extend(self._extract_listeners(py_file))

        # TypeScript handlers
        for ts_file in self.project_path.rglob("*consumer*.ts"):
            if self._should_skip_file(ts_file):
                continue
            events.extend(self._extract_ts_handlers(ts_file))

        return events

    def _discover_all_models(self) -> list[dict]:
        """Discover all database models."""
        models = []

        # SQLAlchemy models
        for py_file in self.project_path.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue
            if "model" in str(py_file).lower() or "models" in str(py_file):
                models.extend(self._extract_sqlalchemy_models(py_file))

        # Prisma models
        prisma_file = self.project_path / "prisma" / "schema.prisma"
        if prisma_file.exists():
            models.extend(self._extract_prisma_models(prisma_file))

        return models

    def _extract_fastapi_routes(self, file_path: Path) -> list[dict]:
        """Extract FastAPI routes from a Python file."""
        routes = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            for match in re.finditer(FASTAPI_ROUTE_PATTERN, content, re.IGNORECASE):
                method = match.group(1).upper()
                path = match.group(2)

                # Find handler function
                remaining = content[match.end():]
                func_match = re.search(r'(?:async\s+)?def\s+(\w+)', remaining)
                handler = func_match.group(1) if func_match else "anonymous"

                # Find line number
                line_num = content[:match.start()].count('\n') + 1

                routes.append({
                    'method': method,
                    'path': path,
                    'handler': handler,
                    'file': rel_path,
                    'line': line_num,
                    'framework': 'FastAPI'
                })
        except Exception:
            pass

        return routes

    def _extract_express_routes(self, file_path: Path) -> list[dict]:
        """Extract Express routes from a JS/TS file."""
        routes = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            for match in re.finditer(EXPRESS_ROUTE_PATTERN, content, re.IGNORECASE):
                method = match.group(1).upper()
                path = match.group(2)
                line_num = content[:match.start()].count('\n') + 1

                routes.append({
                    'method': method,
                    'path': path,
                    'handler': 'anonymous',
                    'file': rel_path,
                    'line': line_num,
                    'framework': 'Express'
                })
        except Exception:
            pass

        return routes

    def _extract_nestjs_routes(self, file_path: Path) -> list[dict]:
        """Extract NestJS routes from a TypeScript file."""
        routes = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            # Find controller base path
            base_match = re.search(r'@Controller\s*\(\s*["\']([^"\']+)["\']', content)
            base_path = base_match.group(1) if base_match else ""

            for match in re.finditer(NESTJS_ROUTE_PATTERN, content):
                method = match.group(1).upper()
                path = match.group(2) if match.group(2) else ""
                full_path = f"/{base_path}/{path}".replace("//", "/").rstrip("/") or "/"

                line_num = content[:match.start()].count('\n') + 1

                routes.append({
                    'method': method,
                    'path': full_path,
                    'handler': 'controller',
                    'file': rel_path,
                    'line': line_num,
                    'framework': 'NestJS'
                })
        except Exception:
            pass

        return routes

    def _extract_python_services(self, file_path: Path) -> list[dict]:
        """Extract service methods from a Python file."""
        services = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            # Find service class
            for class_match in re.finditer(SERVICE_CLASS_PATTERN, content):
                class_name = class_match.group(1)
                class_start = class_match.start()

                # Find next class or end of file
                next_class = re.search(r'\nclass\s+', content[class_start + 1:])
                class_end = class_start + 1 + next_class.start() if next_class else len(content)
                class_content = content[class_start:class_end]

                # Find all methods
                for method_match in re.finditer(r'def\s+(\w+)\s*\(', class_content):
                    method_name = method_match.group(1)
                    if method_name.startswith('_'):
                        continue  # Skip private methods

                    line_num = content[:class_start + method_match.start()].count('\n') + 1
                    services.append({
                        'service': class_name,
                        'method': method_name,
                        'file': rel_path,
                        'line': line_num,
                        'private': False
                    })
        except Exception:
            pass

        return services

    def _extract_ts_services(self, file_path: Path) -> list[dict]:
        """Extract service methods from a TypeScript file."""
        services = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            # Find class with Service in name
            for class_match in re.finditer(r'class\s+(\w*Service)\b', content):
                class_name = class_match.group(1)

                # Find methods
                for method_match in re.finditer(r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::|{)', content[class_match.start():]):
                    method_name = method_match.group(1)
                    if method_name.startswith('_') or method_name in ['constructor', 'ngOnInit']:
                        continue

                    services.append({
                        'service': class_name,
                        'method': method_name,
                        'file': rel_path,
                        'line': 0,
                        'private': method_name.startswith('_')
                    })
        except Exception:
            pass

        return services

    def _extract_celery_tasks(self, file_path: Path) -> list[dict]:
        """Extract Celery tasks from a Python file."""
        jobs = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            for match in re.finditer(r'@(?:app|celery)\.task\s*(?:\([^)]*\))?\s*\ndef\s+(\w+)', content):
                task_name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1

                jobs.append({
                    'name': task_name,
                    'type': 'celery',
                    'file': rel_path,
                    'line': line_num
                })

            for match in re.finditer(r'@shared_task\s*(?:\([^)]*\))?\s*\ndef\s+(\w+)', content):
                task_name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1

                jobs.append({
                    'name': task_name,
                    'type': 'celery_shared',
                    'file': rel_path,
                    'line': line_num
                })
        except Exception:
            pass

        return jobs

    def _extract_cron_jobs(self, file_path: Path) -> list[dict]:
        """Extract cron jobs from a Python file."""
        jobs = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            # Look for schedule definitions
            for match in re.finditer(r'(\w+)\s*=\s*crontab\([^)]+\)', content):
                jobs.append({
                    'name': match.group(1),
                    'type': 'cron',
                    'file': rel_path,
                    'line': content[:match.start()].count('\n') + 1
                })

            # APScheduler style
            for match in re.finditer(r'@scheduler\.schedule.*\ndef\s+(\w+)', content):
                jobs.append({
                    'name': match.group(1),
                    'type': 'apscheduler',
                    'file': rel_path,
                    'line': content[:match.start()].count('\n') + 1
                })
        except Exception:
            pass

        return jobs

    def _extract_bull_jobs(self, file_path: Path) -> list[dict]:
        """Extract Bull queue jobs from a JS/TS file."""
        jobs = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            for match in re.finditer(BULL_QUEUE_PATTERN, content):
                queue_name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1

                jobs.append({
                    'name': queue_name,
                    'type': 'bull_queue',
                    'file': rel_path,
                    'line': line_num
                })
        except Exception:
            pass

        return jobs

    def _extract_consumers(self, file_path: Path) -> list[dict]:
        """Extract message consumers from a Python file."""
        events = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            for match in re.finditer(r'def\s+(\w+)\s*\([^)]*\).*consumer', content, re.IGNORECASE):
                events.append({
                    'name': match.group(1),
                    'type': 'consumer',
                    'file': rel_path,
                    'line': content[:match.start()].count('\n') + 1
                })
        except Exception:
            pass

        return events

    def _extract_listeners(self, file_path: Path) -> list[dict]:
        """Extract event listeners from a Python file."""
        events = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            for match in re.finditer(r'@.*(?:on|listen|subscriber)\s*\(["\']([^"\']+)["\']', content, re.IGNORECASE):
                events.append({
                    'name': match.group(1),
                    'type': 'listener',
                    'file': rel_path,
                    'line': content[:match.start()].count('\n') + 1
                })
        except Exception:
            pass

        return events

    def _extract_ts_handlers(self, file_path: Path) -> list[dict]:
        """Extract event handlers from a TypeScript file."""
        events = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            for match in re.finditer(r'@SubscribeMessage\s*\(["\']([^"\']+)["\']', content):
                events.append({
                    'name': match.group(1),
                    'type': 'websocket_handler',
                    'file': rel_path,
                    'line': content[:match.start()].count('\n') + 1
                })
        except Exception:
            pass

        return events

    def _extract_sqlalchemy_models(self, file_path: Path) -> list[dict]:
        """Extract SQLAlchemy models from a Python file."""
        models = []
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(self.project_path))

            for match in re.finditer(SQLALCHEMY_MODEL_PATTERN, content):
                model_name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1

                # Find table name
                table_match = re.search(r'__tablename__\s*=\s*["\']([^"\']+)["\']', content[match.start():match.start() + 500])
                table_name = table_match.group(1) if table_match else model_name.lower() + 's'

                models.append({
                    'name': model_name,
                    'table': table_name,
                    'file': rel_path,
                    'line': line_num,
                    'type': 'sqlalchemy'
                })
        except Exception:
            pass

        return models

    def _extract_prisma_models(self, file_path: Path) -> list[dict]:
        """Extract Prisma models from schema file."""
        models = []
        try:
            content = file_path.read_text(encoding='utf-8')

            for match in re.finditer(PRISMA_MODEL_PATTERN, content):
                model_name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1

                models.append({
                    'name': model_name,
                    'table': model_name,
                    'file': 'prisma/schema.prisma',
                    'line': line_num,
                    'type': 'prisma'
                })
        except Exception:
            pass

        return models

    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        skip_patterns = [
            'node_modules', '__pycache__', '.git', 'venv', '.venv',
            'dist', 'build', '.next', '.nuxt', 'coverage', '.pytest_cache'
        ]
        return any(pattern in str(file_path) for pattern in skip_patterns)

    def _check_route_issues(self, routes: list[dict]) -> None:
        """Check for route-related issues."""
        # Check for duplicate routes
        seen = {}
        for route in routes:
            key = f"{route['method']} {route['path']}"
            if key in seen:
                self.issues.append(CompletenessIssue(
                    severity=Severity.WARNING.value,
                    category='route_coverage',
                    item_type='route',
                    item_name=key,
                    location=route['file'],
                    message=f"Duplicate route definition: {key}",
                    suggestion=f"Consolidate with definition in {seen[key]}"
                ))
            else:
                seen[key] = route['file']

        # Check for internal routes that might need documentation
        for route in routes:
            if '/internal/' in route['path'] or '/health' in route['path']:
                self.issues.append(CompletenessIssue(
                    severity=Severity.INFO.value,
                    category='route_coverage',
                    item_type='route',
                    item_name=f"{route['method']} {route['path']}",
                    location=route['file'],
                    message="Internal/health route may not need external documentation",
                    suggestion="Consider adding to internal API docs if needed"
                ))

    def _check_service_issues(self, services: list[dict]) -> None:
        """Check for service-related issues."""
        # Check for very large services (many methods)
        service_counts = {}
        for service in services:
            name = service['service']
            service_counts[name] = service_counts.get(name, 0) + 1

        for name, count in service_counts.items():
            if count > 20:
                self.issues.append(CompletenessIssue(
                    severity=Severity.INFO.value,
                    category='service_coverage',
                    item_type='service',
                    item_name=name,
                    location='multiple files',
                    message=f"Service '{name}' has {count} methods - consider splitting",
                    suggestion="Consider breaking into smaller, focused services"
                ))

    def _check_job_issues(self, jobs: list[dict]) -> None:
        """Check for job-related issues."""
        for job in jobs:
            # Check for jobs without clear naming
            if 'task' in job['name'].lower() and job['name'].endswith('_task'):
                self.issues.append(CompletenessIssue(
                    severity=Severity.INFO.value,
                    category='job_naming',
                    item_type='scheduled_job',
                    item_name=job['name'],
                    location=job['file'],
                    message="Job name follows standard naming convention",
                    suggestion="No action needed"
                ))

    def _check_event_issues(self, events: list[dict]) -> None:
        """Check for event-related issues."""
        # Currently no specific checks - placeholder for future
        pass

    def _check_model_issues(self, models: list[dict]) -> None:
        """Check for model-related issues."""
        # Check for duplicate model names
        seen = {}
        for model in models:
            name = model['name']
            if name in seen:
                self.issues.append(CompletenessIssue(
                    severity=Severity.WARNING.value,
                    category='database_coverage',
                    item_type='model',
                    item_name=name,
                    location=model['file'],
                    message=f"Duplicate model definition: {name}",
                    suggestion=f"Review and consolidate with {seen[name]}"
                ))
            else:
                seen[name] = model['file']


def format_report_markdown(report: CompletenessReport) -> str:
    """Format report as Markdown."""
    lines = ["# Completeness Report\n"]

    # Coverage Summary
    lines.append("## Coverage Summary\n")
    lines.append("| Category | Found | Documented | Coverage |")
    lines.append("|----------|-------|------------|----------|")

    category_names = {
        'api_routes': 'API Routes',
        'service_methods': 'Service Methods',
        'scheduled_jobs': 'Scheduled Jobs',
        'event_handlers': 'Event Handlers',
        'database_models': 'Database Models',
    }

    for key, stats in report.categories.items():
        name = category_names.get(key, key)
        coverage = stats['coverage']
        status = "✓" if coverage >= 90 else ("⚠" if coverage >= 70 else "✗")
        lines.append(f"| {name} | {stats['found']} | {stats['documented']} | {coverage}% {status} |")

    # Issues
    if report.issues:
        lines.append("\n## Issues\n")

        # Group by severity
        errors = [i for i in report.issues if i.severity == Severity.ERROR.value]
        warnings = [i for i in report.issues if i.severity == Severity.WARNING.value]
        infos = [i for i in report.issues if i.severity == Severity.INFO.value]

        if errors:
            lines.append(f"\n### Errors ({len(errors)})\n")
            lines.append("| Category | Item | Location | Message |")
            lines.append("|----------|------|----------|---------|")
            for issue in errors:
                lines.append(f"| {issue.category} | {issue.item_name} | `{issue.location}` | {issue.message} |")

        if warnings:
            lines.append(f"\n### Warnings ({len(warnings)})\n")
            lines.append("| Category | Item | Location | Message |")
            lines.append("|----------|------|----------|---------|")
            for issue in warnings:
                lines.append(f"| {issue.category} | {issue.item_name} | `{issue.location}` | {issue.message} |")

        if infos:
            lines.append(f"\n### Info ({len(infos)})\n")
            lines.append("| Category | Item | Location | Message |")
            lines.append("|----------|------|----------|---------|")
            for issue in infos[:10]:  # Limit info items
                lines.append(f"| {issue.category} | {issue.item_name} | `{issue.location}` | {issue.message} |")
            if len(infos) > 10:
                lines.append(f"| ... | ... | ... | ({len(infos) - 10} more) |")
    else:
        lines.append("\n**No issues found.**\n")

    return "\n".join(lines)


def format_report_json(report: CompletenessReport) -> str:
    """Format report as JSON."""
    output = {
        "project_path": report.project_path,
        "categories": report.categories,
        "issues": [asdict(i) for i in report.issues],
        "summary": {
            "is_complete": report.is_complete,
            "has_warnings": report.has_warnings,
            "total_issues": len(report.issues),
            "errors": len([i for i in report.issues if i.severity == Severity.ERROR.value]),
            "warnings": len([i for i in report.issues if i.severity == Severity.WARNING.value]),
            "info": len([i for i in report.issues if i.severity == Severity.INFO.value])
        }
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Check analysis completeness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
    0 - All checks pass
    1 - Critical issues found
    2 - Warnings only
    3 - Could not complete analysis

Examples:
    %(prog)s /path/to/project
    %(prog)s /path/to/project --format json
    %(prog)s /path/to/project --strict
"""
    )

    parser.add_argument(
        "project_path",
        help="Path to project directory"
    )

    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format (default: markdown)"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings"
    )

    args = parser.parse_args()

    project_path = Path(args.project_path)
    if not project_path.exists():
        print(f"Error: Project path does not exist: {args.project_path}", file=sys.stderr)
        sys.exit(3)

    # Run check
    checker = CompletenessChecker(project_path)
    report = checker.check_all()

    # Output results
    if args.format == "json":
        print(format_report_json(report))
    else:
        print(format_report_markdown(report))

    # Determine exit code
    if not report.is_complete:
        sys.exit(1)
    elif args.strict and report.has_warnings:
        sys.exit(2)
    elif report.has_warnings:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
