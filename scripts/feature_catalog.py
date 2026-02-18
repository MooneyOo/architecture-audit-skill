#!/usr/bin/env python3
"""
Feature Catalog & API Reference Generator

Analyzes a codebase to discover API endpoints, build feature catalogs,
and generate comprehensive API reference documentation.

Usage:
    python feature_catalog.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: json)
    --endpoints               Output endpoint discovery only
    --features                Output feature catalog only
    --api-reference           Output API reference only
    --flows                   Output route flows with traces
    --chunked                 Enable chunked processing for large projects
    --chunk-size N            Number of files per chunk (default: 100)
    --resume                  Resume from interrupted analysis
    --force                   Force re-analysis (ignore cache)
    --progress                Show progress bar
    --quiet                   Suppress progress output
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

# Scalability imports
try:
    from chunked_analyzer import ChunkedAnalyzer, ChunkConfig, count_files
    from cache_manager import CacheManager
    from progress_tracker import ProgressTracker, SpinnerProgress
    SCALABILITY_AVAILABLE = True
except ImportError:
    SCALABILITY_AVAILABLE = False


class Framework(Enum):
    EXPRESS = "Express.js"
    FASTIFY = "Fastify"
    NESTJS = "NestJS"
    FASTAPI = "FastAPI"
    DJANGO = "Django"
    FLASK = "Flask"
    NEXTJS = "Next.js"
    UNKNOWN = "Unknown"


@dataclass
class Middleware:
    name: str
    file_path: str
    line_number: int = 0
    description: str = ""


@dataclass
class Endpoint:
    method: str
    path: str
    handler: str
    file_path: str
    line_number: int = 0
    middleware: list[Middleware] = field(default_factory=list)
    auth_required: bool = False
    request_schema: str = ""
    response_schema: str = ""
    error_codes: list[int] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class ServiceCall:
    name: str
    file_path: str
    line_number: int = 0


@dataclass
class DbOperation:
    operation: str  # SELECT, INSERT, UPDATE, DELETE
    table: str
    file_path: str


@dataclass
class RouteFlow:
    endpoint: Endpoint
    middleware_chain: list[Middleware] = field(default_factory=list)
    service_calls: list[ServiceCall] = field(default_factory=list)
    db_operations: list[DbOperation] = field(default_factory=list)


@dataclass
class Feature:
    name: str
    ui_entry_point: str
    api_endpoints: list[str]
    backend_logic: list[str]
    db_tables: list[str]
    domain: str = ""


@dataclass
class FeatureCatalogResult:
    project_path: str
    project_name: str
    framework: Framework
    endpoints: list[Endpoint] = field(default_factory=list)
    features: list[Feature] = field(default_factory=list)
    route_flows: list[RouteFlow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# HTTP Methods
HTTP_METHODS = ["get", "post", "put", "patch", "delete", "head", "options"]

# Express/Fastify route detection patterns
EXPRESS_ROUTE_PATTERNS = [
    # router.get('/path', handler) or app.get('/path', handler)
    r'(?:app|router|fastify)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
    # router.METHOD('/path', middleware, handler) - capture all args
    r'(?:app|router|fastify)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\'][^)]*\)',
]

# FastAPI route detection patterns
FASTAPI_ROUTE_PATTERNS = [
    # @router.get("/path") or @app.get("/path")
    r'@(?:router|app|api)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
    # @router.get("/path", response_model=...)
    r'@(?:router|app|api)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
]

# Django URL patterns
DJANGO_URL_PATTERNS = [
    # path('url/', view_func, name='...')
    r'path\s*\(\s*["\']([^"\']+)["\']\s*,\s*(\w+)',
    # re_path(r'^url/', view_func)
    r're_path\s*\(\s*r?["\']([^"\']+)["\']\s*,\s*(\w+)',
    # url(r'^url/', view_func) - older Django
    r'url\s*\(\s*r?["\']([^"\']+)["\']\s*,\s*(\w+)',
]

# NestJS route patterns
NESTJS_ROUTE_PATTERNS = [
    # @Get('path') or @Post('path')
    r'@(Get|Post|Put|Patch|Delete)\s*\(\s*["\']?([^"\']*)["\']?\s*\)',
]

# Authentication middleware patterns
AUTH_PATTERNS = [
    r'auth(?:Middleware|enticate|Guard|\.)',
    r'jwt',
    r'token',
    r'passport',
    r'@UseGuards.*Auth',
    r'@LoginRequired',
    r'requireAuth',
    r'checkAuth',
    r'verifyToken',
]

# Service layer patterns
SERVICE_PATTERNS = [
    # service.method() pattern
    r'(\w+[Ss]ervice)\.(\w+)',
    r'await\s+(\w+service)\.(\w+)',
    r'(\w+\.service)\.(\w+)',
    # Direct function calls (imported from service)
    r'await\s+(\w+_user|\w+_token|\w+_password|\w+_refresh)(?=\()',
    r'(authenticate_user|create_user|verify_user|revoke_\w+|change_\w+)(?=\()',
]

# DB operation patterns
DB_PATTERNS = {
    'SELECT': [
        r'SELECT\s+.*?\s+FROM\s+(\w+)',
        r'\.find(?:One|Many|All)?\s*\(',
        r'\.get\s*\(',
        r'\.query\s*\(',
    ],
    'INSERT': [
        r'INSERT\s+INTO\s+(\w+)',
        r'\.create\s*\(',
        r'\.insert\s*\(',
        r'\.save\s*\(',
    ],
    'UPDATE': [
        r'UPDATE\s+(\w+)\s+SET',
        r'\.update\s*\(',
        r'\.updateOne\s*\(',
        r'\.updateMany\s*\(',
    ],
    'DELETE': [
        r'DELETE\s+FROM\s+(\w+)',
        r'\.delete\s*\(',
        r'\.deleteOne\s*\(',
        r'\.deleteMany\s*\(',
        r'\.destroy\s*\(',
    ],
}


def detect_framework(project_path: Path) -> Framework:
    """Detect the backend framework being used."""
    # Check common subdirectories for config files
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
    # Check for nested backend structures first
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


def extract_express_routes(content: str, file_path: str) -> list[Endpoint]:
    """Extract routes from Express/Fastify code."""
    endpoints = []

    for pattern in EXPRESS_ROUTE_PATTERNS:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            method = match.group(1).upper()
            path = match.group(2)

            # Find handler - look for function name after the path
            remaining = content[match.end():]
            handler_match = re.search(r',\s*(\w+)', remaining)
            handler = handler_match.group(1) if handler_match else "anonymous"

            # Find line number
            line_num = content[:match.start()].count('\n') + 1

            # Detect middleware
            middleware = extract_middleware_from_route(remaining, file_path)

            endpoints.append(Endpoint(
                method=method,
                path=path,
                handler=handler,
                file_path=file_path,
                line_number=line_num,
                middleware=middleware
            ))

    return endpoints


def extract_fastapi_routes(content: str, file_path: str) -> list[Endpoint]:
    """Extract routes from FastAPI code."""
    endpoints = []

    for pattern in FASTAPI_ROUTE_PATTERNS:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            method = match.group(1).upper()
            path = match.group(2)

            # Find handler function below decorator
            remaining = content[match.end():]
            func_match = re.search(r'(?:async\s+)?def\s+(\w+)', remaining)
            handler = func_match.group(1) if func_match else "anonymous"

            # Find line number
            line_num = content[:match.start()].count('\n') + 1

            # Check for auth in decorator or function
            auth_required = check_auth_in_code(content[match.start():match.end()+500])

            # Extract schema info
            request_schema, response_schema = extract_fastapi_schemas(remaining)

            endpoints.append(Endpoint(
                method=method,
                path=path,
                handler=handler,
                file_path=file_path,
                line_number=line_num,
                auth_required=auth_required,
                request_schema=request_schema,
                response_schema=response_schema
            ))

    return endpoints


def extract_django_urls(content: str, file_path: str) -> list[Endpoint]:
    """Extract URLs from Django urls.py files."""
    endpoints = []

    for pattern in DJANGO_URL_PATTERNS:
        for match in re.finditer(pattern, content):
            path = match.group(1)
            view = match.group(2) if len(match.groups()) > 1 else "view"

            # Find line number
            line_num = content[:match.start()].count('\n') + 1

            # Django URLs don't have explicit HTTP methods - mark as ANY
            # The view function determines the method
            endpoints.append(Endpoint(
                method="ANY",
                path=path,
                handler=view,
                file_path=file_path,
                line_number=line_num
            ))

    return endpoints


def extract_nestjs_routes(content: str, file_path: str) -> list[Endpoint]:
    """Extract routes from NestJS controllers."""
    endpoints = []

    # Find the controller base path
    base_path_match = re.search(r'@Controller\s*\(\s*["\']([^"\']+)["\']', content)
    base_path = base_path_match.group(1) if base_path_match else ""

    for pattern in NESTJS_ROUTE_PATTERNS:
        for match in re.finditer(pattern, content):
            method = match.group(1).upper()
            path = match.group(2) if match.group(2) else ""

            # Combine base path with method path
            full_path = f"/{base_path}/{path}".replace("//", "/").rstrip("/")

            # Find handler method
            remaining = content[match.end():]
            func_match = re.search(r'(?:async\s+)?(\w+)\s*\(', remaining)
            handler = func_match.group(1) if func_match else "anonymous"

            # Find line number
            line_num = content[:match.start()].count('\n') + 1

            endpoints.append(Endpoint(
                method=method,
                path=full_path or "/",
                handler=handler,
                file_path=file_path,
                line_number=line_num
            ))

    return endpoints


def extract_nextjs_api_routes(project_path: Path) -> list[Endpoint]:
    """Extract API routes from Next.js file-based routing."""
    endpoints = []

    # Pages Router: pages/api/
    pages_api = project_path / "pages" / "api"
    if pages_api.exists():
        for api_file in pages_api.rglob("*"):
            if api_file.suffix in [".ts", ".tsx", ".js", ".jsx"]:
                rel_path = api_file.relative_to(pages_api)
                # Convert file path to route path
                route_path = "/" + str(rel_path.with_suffix("")).replace("\\", "/")
                # Handle dynamic routes
                route_path = re.sub(r'\[(\w+)\]', r':\1', route_path)
                # Handle index files
                route_path = route_path.replace("/index", "").rstrip("/") or "/"

                endpoints.append(Endpoint(
                    method="ANY",  # Next.js API routes handle all methods
                    path=f"/api{route_path}",
                    handler="handler",
                    file_path=str(api_file.relative_to(project_path))
                ))

    # App Router: app/api/
    app_api = project_path / "app" / "api"
    if app_api.exists():
        for route_file in app_api.rglob("route.ts"):
            rel_path = route_file.parent.relative_to(app_api)
            route_path = "/" + str(rel_path).replace("\\", "/")
            route_path = re.sub(r'\[(\w+)\]', r':\1', route_path)

            endpoints.append(Endpoint(
                method="ANY",
                path=f"/api{route_path}".rstrip("/") or "/api",
                handler="route",
                file_path=str(route_file.relative_to(project_path))
            ))

    return endpoints


def extract_middleware_from_route(remaining_content: str, file_path: str) -> list[Middleware]:
    """Extract middleware from route definition."""
    middleware = []

    # Look for middleware between path and final handler
    # Pattern: , middleware1, middleware2, handler)
    middleware_section = remaining_content.split(')')[0] if ')' in remaining_content else ""

    # Find function references
    for match in re.finditer(r',\s*(\w+)\s*(?:,|\))', middleware_section):
        name = match.group(1)
        if name not in HTTP_METHODS and not name.startswith('{'):
            middleware.append(Middleware(
                name=name,
                file_path=file_path
            ))

    return middleware


def check_auth_in_code(code_snippet: str) -> bool:
    """Check if authentication is required based on code patterns."""
    code_lower = code_snippet.lower()
    for pattern in AUTH_PATTERNS:
        if re.search(pattern, code_lower, re.IGNORECASE):
            return True
    return False


def extract_fastapi_schemas(remaining_content: str) -> tuple[str, str]:
    """Extract request and response schemas from FastAPI route."""
    request_schema = ""
    response_schema = ""

    # Look for response_model in decorator
    response_match = re.search(r'response_model\s*=\s*(\w+)', remaining_content[:200])
    if response_match:
        response_schema = response_match.group(1)

    # Look for request body parameter
    # Pattern: param_name: ParamType or param_name: Body(...)
    body_patterns = [
        r'(\w+):\s*(\w+(?:Create|Update|Request|In|Input))',
        r'(\w+):\s*Body\[?(\w+)',
        r'(\w+):\s*(\w+)\s*=\s*Body',
    ]

    for pattern in body_patterns:
        match = re.search(pattern, remaining_content[:500])
        if match:
            request_schema = match.group(2)
            break

    return request_schema, response_schema


def discover_endpoints(project_path: Path, framework: Framework) -> tuple[list[Endpoint], list[str]]:
    """Discover all API endpoints in the project."""
    endpoints = []
    errors = []

    src_dirs = find_source_directories(project_path)

    if framework in [Framework.EXPRESS, Framework.FASTIFY, Framework.NESTJS]:
        # Scan JavaScript/TypeScript files
        for src_dir in src_dirs:
            for ext in ["*.ts", "*.js"]:
                for file_path in src_dir.rglob(ext):
                    if "node_modules" in str(file_path) or ".d.ts" in str(file_path):
                        continue

                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        rel_path = str(file_path.relative_to(project_path))

                        if framework == Framework.NESTJS:
                            endpoints.extend(extract_nestjs_routes(content, rel_path))
                        else:
                            endpoints.extend(extract_express_routes(content, rel_path))

                    except Exception as e:
                        errors.append(f"Error reading {file_path}: {e}")

    elif framework == Framework.FASTAPI:
        # Scan Python files
        for src_dir in src_dirs:
            for py_file in src_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                # Skip test files
                if "test_" in py_file.name or "_test.py" in py_file.name:
                    continue
                if "/tests/" in str(py_file) or "\\tests\\" in str(py_file):
                    continue

                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    rel_path = str(py_file.relative_to(project_path))
                    endpoints.extend(extract_fastapi_routes(content, rel_path))

                except Exception as e:
                    errors.append(f"Error reading {py_file}: {e}")

    elif framework == Framework.DJANGO:
        # Look for urls.py files
        for src_dir in src_dirs:
            for urls_file in src_dir.rglob("urls.py"):
                try:
                    with open(urls_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    rel_path = str(urls_file.relative_to(project_path))
                    endpoints.extend(extract_django_urls(content, rel_path))

                except Exception as e:
                    errors.append(f"Error reading {urls_file}: {e}")

    elif framework == Framework.NEXTJS:
        # File-based routing
        endpoints.extend(extract_nextjs_api_routes(project_path))

    # Deduplicate endpoints
    seen = set()
    unique_endpoints = []
    for ep in endpoints:
        key = (ep.method, ep.path)
        if key not in seen:
            seen.add(key)
            unique_endpoints.append(ep)

    return unique_endpoints, errors


def detect_auth_requirements(endpoints: list[Endpoint], project_path: Path) -> None:
    """Detect authentication requirements for endpoints."""
    # Build a map of middleware files
    auth_middleware_names = set()

    src_dirs = find_source_directories(project_path)

    for src_dir in src_dirs:
        for mw_file in src_dir.rglob("*auth*"):
            if mw_file.suffix in [".ts", ".js", ".py"]:
                auth_middleware_names.add(mw_file.stem)

    # Check each endpoint
    for endpoint in endpoints:
        # Check middleware names
        for mw in endpoint.middleware:
            if any(auth in mw.name.lower() for auth in ["auth", "jwt", "token", "guard"]):
                endpoint.auth_required = True
                break

        # Also check if auth middleware names appear in handler file
        if not endpoint.auth_required:
            full_path = project_path / endpoint.file_path
            if full_path.exists():
                try:
                    with open(full_path, 'r') as f:
                        content = f.read()
                    endpoint.auth_required = check_auth_in_code(content)
                except:
                    pass


def infer_error_codes(method: str, auth_required: bool) -> list[int]:
    """Infer likely error codes based on method and auth requirement."""
    codes = []

    if auth_required:
        codes.extend([401, 403])

    if method in ["POST", "PUT", "PATCH"]:
        codes.append(400)  # Validation errors

    if method in ["GET", "PUT", "PATCH", "DELETE"]:
        codes.append(404)  # Not found

    if method == "POST":
        codes.append(409)  # Conflict

    return sorted(list(set(codes))) if codes else []


def build_feature_catalog(endpoints: list[Endpoint], project_path: Path) -> list[Feature]:
    """Build feature catalog from endpoints."""
    features = []

    # Group endpoints by domain
    domains: dict[str, list[Endpoint]] = {}

    for endpoint in endpoints:
        # Extract domain from path
        parts = endpoint.path.strip("/").split("/")
        domain = parts[0] if parts else "root"

        if domain.startswith(":"):
            domain = parts[1] if len(parts) > 1 else "root"
        if domain.startswith("api"):
            domain = parts[1] if len(parts) > 1 else "root"

        if domain not in domains:
            domains[domain] = []
        domains[domain].append(endpoint)

    # Create features from domain groups
    for domain, domain_endpoints in sorted(domains.items()):
        # Group by resource/action
        resource_features = {}

        for ep in domain_endpoints:
            # Determine feature name from handler or path
            feature_name = ep.handler.replace("_", " ").replace("-", " ").title()

            # Clean up feature name
            for prefix in ["Get ", "List ", "Create ", "Update ", "Delete ", "Post ", "Put ", "Patch "]:
                if feature_name.startswith(prefix):
                    feature_name = f"{prefix.strip()} {domain.title()}"
                    break

            if feature_name not in resource_features:
                resource_features[feature_name] = {
                    "endpoints": [],
                    "handlers": [],
                }

            resource_features[feature_name]["endpoints"].append(f"{ep.method} {ep.path}")
            resource_features[feature_name]["handlers"].append(f"{Path(ep.file_path).name}:{ep.handler}")

        # Create Feature objects
        for feature_name, data in resource_features.items():
            # Infer DB tables from domain
            db_tables = [domain.lower()]
            if "order" in feature_name.lower():
                db_tables.extend(["order_items", "payments"])

            features.append(Feature(
                name=feature_name,
                ui_entry_point=f"/{domain}",  # Inferred
                api_endpoints=data["endpoints"][:3],  # Limit
                backend_logic=data["handlers"][:2],
                db_tables=db_tables,
                domain=domain.title()
            ))

    return features


def trace_route_flows(endpoints: list[Endpoint], project_path: Path) -> list[RouteFlow]:
    """Trace route flows to service layer and database operations."""
    flows = []

    for endpoint in endpoints:
        flow = RouteFlow(endpoint=endpoint)

        full_path = project_path / endpoint.file_path
        if not full_path.exists():
            flows.append(flow)
            continue

        try:
            with open(full_path, 'r') as f:
                content = f.read()

            # Find the handler function
            handler_pattern = rf'(?:async\s+)?def\s+{endpoint.handler}|function\s+{endpoint.handler}|const\s+{endpoint.handler}'
            handler_match = re.search(handler_pattern, content)

            if handler_match:
                # Get handler content (up to next function definition)
                handler_start = handler_match.end()
                next_func = re.search(r'\n(?:def |function |const |async )', content[handler_start:])
                handler_end = handler_start + next_func.start() if next_func else len(content)
                handler_content = content[handler_start:handler_end]

                # Extract service calls
                for pattern in SERVICE_PATTERNS:
                    for match in re.finditer(pattern, handler_content, re.IGNORECASE):
                        service_name = match.group(1)
                        method_name = match.group(2) if len(match.groups()) > 1 else ""
                        flow.service_calls.append(ServiceCall(
                            name=f"{service_name}.{method_name}",
                            file_path=endpoint.file_path
                        ))

                # Extract DB operations
                for op_type, patterns in DB_PATTERNS.items():
                    for pattern in patterns:
                        for match in re.finditer(pattern, handler_content, re.IGNORECASE):
                            table = match.group(1) if match.groups() else "unknown"
                            flow.db_operations.append(DbOperation(
                                operation=op_type,
                                table=table,
                                file_path=endpoint.file_path
                            ))

        except Exception:
            pass

        flows.append(flow)

    return flows


def generate_sequence_diagram(flow: RouteFlow) -> str:
    """Generate a Mermaid sequence diagram for a route flow."""
    lines = ["```mermaid", "sequenceDiagram"]
    lines.append("    participant Client")
    lines.append("    participant Middleware")
    lines.append("    participant Handler")
    lines.append("    participant Service")
    lines.append("    participant Database")
    lines.append("")

    endpoint = flow.endpoint
    lines.append(f"    Client->>Handler: {endpoint.method} {endpoint.path}")

    # Add middleware steps
    for i, mw in enumerate(endpoint.middleware[:3]):
        lines.append(f"    Handler->>Middleware: {mw.name}")

    # Add service calls
    for service in flow.service_calls[:3]:
        lines.append(f"    Handler->>Service: {service.name}")

    # Add DB operations
    for db_op in flow.db_operations[:2]:
        lines.append(f"    Service->>Database: {db_op.operation} {db_op.table}")

    lines.append("    Handler-->>Client: Response")
    lines.append("```")

    return "\n".join(lines)


def output_json(result: FeatureCatalogResult) -> str:
    """Format results as JSON."""
    output = {
        "project_path": result.project_path,
        "project_name": result.project_name,
        "framework": result.framework.value,
        "endpoint_count": len(result.endpoints),
        "feature_count": len(result.features),
        "endpoints": [
            {
                "method": ep.method,
                "path": ep.path,
                "handler": ep.handler,
                "file": ep.file_path,
                "line": ep.line_number,
                "auth_required": ep.auth_required,
                "middleware": [mw.name for mw in ep.middleware],
                "request_schema": ep.request_schema,
                "response_schema": ep.response_schema,
                "error_codes": ep.error_codes
            }
            for ep in result.endpoints
        ],
        "features": [
            {
                "name": f.name,
                "domain": f.domain,
                "ui_entry_point": f.ui_entry_point,
                "api_endpoints": f.api_endpoints,
                "backend_logic": f.backend_logic,
                "db_tables": f.db_tables
            }
            for f in result.features
        ],
        "errors": result.errors
    }

    if result.route_flows:
        output["route_flows"] = [
            {
                "endpoint": f"{rf.endpoint.method} {rf.endpoint.path}",
                "middleware": [mw.name for mw in rf.middleware_chain],
                "service_calls": [sc.name for sc in rf.service_calls],
                "db_operations": [
                    f"{db.operation} {db.table}" for db in rf.db_operations
                ]
            }
            for rf in result.route_flows
        ]

    return json.dumps(output, indent=2)


def output_markdown(result: FeatureCatalogResult, sections: dict = None) -> str:
    """Format results as Markdown."""
    sections = sections or {
        "endpoints": True,
        "features": True,
        "api_reference": True,
        "flows": False
    }

    lines = [f"# Feature Catalog & API Reference\n"]
    lines.append(f"**Project:** `{result.project_path}`\n")
    lines.append(f"**Framework:** {result.framework.value}\n")
    lines.append(f"**Endpoints Found:** {len(result.endpoints)}\n")

    if result.errors:
        lines.append("## Errors\n")
        for error in result.errors:
            lines.append(f"- {error}\n")
        lines.append("")

    # Section: Endpoint Discovery
    if sections.get("endpoints") and result.endpoints:
        lines.append("## 6.0 Discovered Endpoints\n")
        lines.append("| Method | Path | Handler | File | Middleware |")
        lines.append("|--------|------|---------|------|------------|")

        for ep in result.endpoints[:50]:  # Limit output
            mw_names = ", ".join(mw.name for mw in ep.middleware[:2])
            if len(ep.middleware) > 2:
                mw_names += f" (+{len(ep.middleware) - 2})"
            lines.append(f"| {ep.method} | `{ep.path}` | {ep.handler} | `{ep.file_path}` | {mw_names or '-'} |")

        lines.append("")

    # Section: Feature Catalog
    if sections.get("features") and result.features:
        lines.append("## 6.1 Feature Catalog\n")
        lines.append("| # | Feature Name | UI Entry Point | API Endpoint(s) | Backend Logic | DB Tables |")
        lines.append("|---|--------------|----------------|-----------------|---------------|-----------|")

        for i, f in enumerate(result.features[:30], 1):
            api_eps = ", ".join(f.api_endpoints[:2])
            if len(f.api_endpoints) > 2:
                api_eps += f" (+{len(f.api_endpoints) - 2})"
            backend = ", ".join(f.backend_logic[:1]) or "-"
            tables = ", ".join(f.db_tables[:2])
            lines.append(f"| {i} | {f.name} | {f.ui_entry_point} | `{api_eps}` | `{backend}` | {tables} |")

        lines.append("")

    # Section: API Reference
    if sections.get("api_reference") and result.endpoints:
        lines.append("## 6.2 API Reference\n")
        lines.append("| Method | Endpoint | Auth | Request Body | Success Response | Error Codes |")
        lines.append("|--------|----------|------|--------------|------------------|-------------|")

        for ep in result.endpoints[:50]:
            auth = "Yes" if ep.auth_required else "No"
            request = ep.request_schema or "-"
            response = ep.response_schema or "200 OK"
            errors = ", ".join(str(c) for c in ep.error_codes) or "-"

            # Truncate long values
            request = request[:30] + "..." if len(request) > 30 else request
            response = response[:30] + "..." if len(response) > 30 else response

            lines.append(f"| {ep.method} | `{ep.path}` | {auth} | `{request}` | `{response}` | {errors} |")

        lines.append("")

    # Section: Route Flows
    if sections.get("flows") and result.route_flows:
        lines.append("## 6.3 Route Flows\n")

        for flow in result.route_flows[:10]:
            ep = flow.endpoint
            lines.append(f"### {ep.method} {ep.path}\n")
            lines.append(f"**Handler:** `{ep.handler}` (`{ep.file_path}:{ep.line_number}`)\n")

            if ep.middleware:
                lines.append("**Middleware Chain:**")
                for i, mw in enumerate(ep.middleware, 1):
                    lines.append(f"  {i}. `{mw.name}`")
                lines.append("")

            if flow.service_calls:
                lines.append("**Service Calls:**")
                for sc in flow.service_calls:
                    lines.append(f"  - `{sc.name}`")
                lines.append("")

            if flow.db_operations:
                lines.append("**Database Operations:**")
                for db in flow.db_operations:
                    lines.append(f"  - {db.operation} on `{db.table}`")
                lines.append("")

            # Add sequence diagram
            lines.append(generate_sequence_diagram(flow))
            lines.append("")

    return "\n".join(lines)


def analyze_project(project_path: str) -> FeatureCatalogResult:
    """Analyze a project to discover endpoints and build feature catalog."""
    path = Path(project_path)

    if not path.exists():
        return FeatureCatalogResult(
            project_path=project_path,
            project_name=path.name,
            framework=Framework.UNKNOWN,
            errors=[f"Project path does not exist: {project_path}"]
        )

    result = FeatureCatalogResult(
        project_path=str(path),
        project_name=path.name,
        framework=detect_framework(path)
    )

    # Discover endpoints
    result.endpoints, errors = discover_endpoints(path, result.framework)
    result.errors.extend(errors)

    # Detect auth requirements
    detect_auth_requirements(result.endpoints, path)

    # Infer error codes
    for ep in result.endpoints:
        ep.error_codes = infer_error_codes(ep.method, ep.auth_required)

    # Build feature catalog
    result.features = build_feature_catalog(result.endpoints, path)

    # Trace route flows
    result.route_flows = trace_route_flows(result.endpoints, path)

    return result


# ============================================================================
# Chunked Analysis Support (Epic 4)
# ============================================================================

def analyze_project_chunked(
    project_path: str,
    chunk_size: int = 100,
    resume: bool = True,
    force: bool = False,
    show_progress: bool = False,
    quiet: bool = False
) -> FeatureCatalogResult:
    """
    Analyze a project using chunked processing for large codebases.

    Args:
        project_path: Path to the project
        chunk_size: Number of files per chunk
        resume: Resume from interrupted analysis
        force: Force re-analysis (ignore cache)
        show_progress: Show progress bar
        quiet: Suppress progress output

    Returns:
        FeatureCatalogResult with analysis results
    """
    if not SCALABILITY_AVAILABLE:
        # Fall back to regular analysis if modules not available
        return analyze_project(project_path)

    path = Path(project_path)

    if not path.exists():
        return FeatureCatalogResult(
            project_path=project_path,
            project_name=path.name,
            framework=Framework.UNKNOWN,
            errors=[f"Project path does not exist: {project_path}"]
        )

    result = FeatureCatalogResult(
        project_path=str(path),
        project_name=path.name,
        framework=detect_framework(path)
    )

    # Setup cache
    cache_dir = path / ".audit_cache" / "feature_catalog"
    cache = CacheManager(cache_dir)

    if force:
        cache.invalidate()

    # Setup progress tracking
    total_files = count_files(path)
    progress = None
    if show_progress and not quiet:
        progress = ProgressTracker(
            total=total_files,
            phase="Feature catalog analysis",
            quiet=quiet
        )

    # Configure chunked analyzer
    config = ChunkConfig(
        chunk_size=chunk_size,
        output_dir=cache_dir / "chunks",
        resume=resume,
        file_extensions={'.py', '.ts', '.js', '.tsx', '.jsx'}
    )

    analyzer = ChunkedAnalyzer(config)

    # Define analyzer function based on framework
    def analyze_route_file(file_path: Path) -> dict:
        """Analyze a single route file for endpoints."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            rel_path = str(file_path.relative_to(path))
            endpoints = []

            if result.framework == Framework.NESTJS:
                endpoints = extract_nestjs_routes(content, rel_path)
            elif result.framework in [Framework.EXPRESS, Framework.FASTIFY]:
                endpoints = extract_express_routes(content, rel_path)
            elif result.framework == Framework.FASTAPI:
                endpoints = extract_fastapi_routes(content, rel_path)
            elif result.framework == Framework.DJANGO:
                endpoints = extract_django_urls(content, rel_path)

            return {
                "file": str(file_path),
                "endpoints": [
                    {
                        "method": ep.method,
                        "path": ep.path,
                        "handler": ep.handler,
                        "file_path": ep.file_path,
                        "line_number": ep.line_number,
                        "middleware": [{"name": mw.name} for mw in ep.middleware],
                        "auth_required": ep.auth_required,
                        "request_schema": ep.request_schema,
                        "response_schema": ep.response_schema
                    }
                    for ep in endpoints
                ]
            }

        except Exception as e:
            return {"file": str(file_path), "error": str(e)}

    # Process in chunks
    all_endpoints = []

    src_dirs = find_source_directories(path)

    for chunk_result in analyzer.analyze_project(path, analyze_route_file):
        for file_result in chunk_result.results:
            if "endpoints" in file_result:
                for ep_data in file_result["endpoints"]:
                    ep = Endpoint(
                        method=ep_data["method"],
                        path=ep_data["path"],
                        handler=ep_data["handler"],
                        file_path=ep_data["file_path"],
                        line_number=ep_data.get("line_number", 0),
                        middleware=[Middleware(name=mw["name"]) for mw in ep_data.get("middleware", [])],
                        auth_required=ep_data.get("auth_required", False),
                        request_schema=ep_data.get("request_schema", ""),
                        response_schema=ep_data.get("response_schema", "")
                    )
                    all_endpoints.append(ep)
            if "error" in file_result:
                result.errors.append(f"Error in {file_result['file']}: {file_result['error']}")

        if progress:
            progress.update(chunk_result.files_processed)

    if progress:
        progress.complete()

    # Deduplicate endpoints
    seen = set()
    unique_endpoints = []
    for ep in all_endpoints:
        key = (ep.method, ep.path)
        if key not in seen:
            seen.add(key)
            unique_endpoints.append(ep)

    result.endpoints = unique_endpoints

    # Detect auth requirements
    detect_auth_requirements(result.endpoints, path)

    # Infer error codes
    for ep in result.endpoints:
        ep.error_codes = infer_error_codes(ep.method, ep.auth_required)

    # Build feature catalog
    result.features = build_feature_catalog(result.endpoints, path)

    # Trace route flows
    result.route_flows = trace_route_flows(result.endpoints, path)

    return result


# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Discover API endpoints and build feature catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --format markdown
  %(prog)s /path/to/project --endpoints --format markdown
  %(prog)s /path/to/project --flows
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
        "--endpoints",
        action="store_true",
        help="Output endpoint discovery only"
    )

    parser.add_argument(
        "--features",
        action="store_true",
        help="Output feature catalog only"
    )

    parser.add_argument(
        "--api-reference",
        action="store_true",
        help="Output API reference only"
    )

    parser.add_argument(
        "--flows",
        action="store_true",
        help="Output route flows with traces"
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
        "--resume",
        action="store_true",
        help="Resume from interrupted analysis"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-analysis (ignore cache)"
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

    args = parser.parse_args()

    # Analyze project - use chunked mode if requested
    if args.chunked:
        if not SCALABILITY_AVAILABLE:
            print("Warning: Scalability modules not available, falling back to standard mode", file=sys.stderr)
            result = analyze_project(args.project_path)
        else:
            result = analyze_project_chunked(
                args.project_path,
                chunk_size=args.chunk_size,
                resume=args.resume,
                force=args.force,
                show_progress=args.progress,
                quiet=args.quiet
            )
    else:
        result = analyze_project(args.project_path)

    # Determine sections to output
    sections = {
        "endpoints": True,
        "features": True,
        "api_reference": True,
        "flows": False
    }

    # Override if specific sections requested
    if args.endpoints or args.features or args.api_reference or args.flows:
        sections = {
            "endpoints": args.endpoints,
            "features": args.features,
            "api_reference": args.api_reference,
            "flows": args.flows
        }
        # If no sections explicitly set, show all
        if not any([args.endpoints, args.features, args.api_reference, args.flows]):
            sections = {"endpoints": True, "features": True, "api_reference": True, "flows": False}

    # Output results
    if args.format == "json":
        print(output_json(result))
    else:
        print(output_markdown(result, sections))

    # Return appropriate exit code
    has_critical_errors = len(result.errors) > 0 and len(result.endpoints) == 0
    sys.exit(1 if has_critical_errors else 0)


if __name__ == "__main__":
    main()
