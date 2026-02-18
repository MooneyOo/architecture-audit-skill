#!/usr/bin/env python3
"""
Happy Path Tracing Script

Traces primary user flows through a codebase, documenting each step with
file paths and line references.

Usage:
    python happy_path_tracer.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: json)
    --flow login|crud|main    Flow to trace (default: auto-detect)
    --help                    Show usage information

Flow types:
    - login: User authentication flow (login form -> API -> session)
    - crud: Core CRUD operation (list -> create -> update -> delete)
    - main: Primary business operation (auto-detected)
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class FlowType(Enum):
    """Flow type enumeration."""
    LOGIN = "login"
    CRUD = "crud"
    MAIN = "main"
    AUTO = "auto"


@dataclass
class FlowStep:
    """Represents a step in a user flow."""
    step_number: int
    component_type: str  # UI, API_Client, Route, Controller, Service, Repository
    component_name: str
    file_path: str
    line_number: int
    description: str
    details: str = ""  # Additional context (HTTP method, endpoint, etc.)


@dataclass
class HappyPath:
    """Represents a complete user flow."""
    name: str
    description: str
    steps: list[FlowStep] = field(default_factory=list)
    entry_point: str = ""  # UI route/page


@dataclass
class HappyPathResult:
    """Result of happy path tracing."""
    project_path: str
    primary_flows: list[HappyPath] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Frontend patterns for detecting UI components
UI_PATTERNS = {
    'react': {
        'page': [
            (r'(pages|views)/(\w+)\.(tsx|jsx)', 'Page component'),
            (r'function\s+(\w+Page)\s*\(', 'Page component'),
            (r'const\s+(\w+Page)\s*[=:]', 'Page component'),
        ],
        'form': [
            (r'<form[^>]*onSubmit', 'Form submission'),
            (r'handleSubmit', 'Form handler'),
            (r'mutate\(', 'Mutation trigger'),
        ],
        'api_call': [
            (r'(api[A-Z]\w+|\w+Api)\.(\w+)', 'API client method'),
            (r'axios\.(get|post|put|delete|patch)', 'Axios call'),
            (r'fetch\(["\']([^"\']+)["\']', 'Fetch call'),
            (r'useQuery\(["\']([^"\']+)["\']', 'React Query'),
            (r'useMutation\(', 'React Query mutation'),
        ],
    },
}

# Backend patterns for tracing API -> DB flow
BACKEND_PATTERNS = {
    'python': {
        'route': [
            (r'@(?:router|app)\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', 'FastAPI route'),
            (r'@app\.route\(["\']([^"\']+)["\']', 'Flask route'),
        ],
        'handler': [
            (r'(?:async\s+)?def\s+(\w+)\s*\([^)]*\)\s*:', 'Handler function'),
        ],
        'service': [
            (r'class\s+(\w+Service)\s*:', 'Service class'),
            (r'def\s+(create|get|update|delete|list)\w*\s*\(', 'Service method'),
        ],
        'repository': [
            (r'class\s+(\w+Repository)\s*:', 'Repository class'),
            (r'(session|db)\.(execute|query|add|commit)', 'Database operation'),
            (r'SELECT|INSERT|UPDATE|DELETE', 'SQL operation'),
        ],
    },
    'nodejs': {
        'route': [
            (r'(router|app)\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', 'Express route'),
            (r'@(?:Get|Post|Put|Delete|Patch)\(["\']([^"\']+)["\']', 'NestJS route'),
        ],
        'handler': [
            (r'(?:async\s+)?function\s+(\w+)', 'Handler function'),
            (r'const\s+(\w+)\s*=\s*(?:async\s+)?\(', 'Handler function'),
        ],
        'service': [
            (r'class\s+(\w+Service)', 'Service class'),
            (r'export\s+const\s+(\w+Service)', 'Service module'),
        ],
    },
}

# Common flow patterns to look for
FLOW_INDICATORS = {
    'login': [
        r'login|signin|authenticate',
        r'password',
        r'credential',
    ],
    'crud': [
        r'create|add|new',
        r'read|list|get|find',
        r'update|edit|modify',
        r'delete|remove',
    ],
}


def find_frontend_entry_points(project_path: Path) -> list[tuple[str, str, str]]:
    """Find frontend entry points (pages, routes)."""
    entry_points = []

    # Check for React Router
    router_files = list(project_path.rglob("router.tsx")) + list(project_path.rglob("router.ts"))
    router_files += list(project_path.rglob("App.tsx")) + list(project_path.rglob("routes.tsx"))

    for router_file in router_files:
        if any(part in router_file.parts for part in ['node_modules', 'dist', 'build']):
            continue

        try:
            with open(router_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            relative_path = str(router_file.relative_to(project_path))

            # Find Route definitions
            route_pattern = r'<Route[^>]*path=["\']([^"\']+)["\'][^>]*element=\{(?:<(\w+)|(\w+))'
            for match in re.finditer(route_pattern, content):
                path = match.group(1)
                component = match.group(2) or match.group(3) or 'Unknown'
                entry_points.append((path, component, relative_path))

            # Also look for createBrowserRouter patterns
            browser_pattern = r'path:\s*["\']([^"\']+)["\'].*?element:\s*<(?:\w+\.)?(\w+)'
            for match in re.finditer(browser_pattern, content, re.DOTALL):
                path = match.group(1)
                component = match.group(2)
                entry_points.append((path, component, relative_path))

        except Exception:
            continue

    return entry_points


def find_api_endpoints(project_path: Path) -> list[tuple[str, str, str, int]]:
    """Find API endpoint definitions."""
    endpoints = []

    for ext in ['.py', '.ts', '.js']:
        for file_path in project_path.rglob(f"*{ext}"):
            if any(part in file_path.parts for part in ['node_modules', '__pycache__', 'venv', '.venv', 'dist']):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                relative_path = str(file_path.relative_to(project_path))

                # FastAPI routes
                for match in re.finditer(r'@(?:router|app)\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', content, re.I):
                    method = match.group(1).upper()
                    path = match.group(2)
                    line_num = content[:match.start()].count('\n') + 1

                    # Find handler function name
                    func_match = re.search(r'(?:async\s+)?def\s+(\w+)\s*\(', content[match.end():match.end() + 200])
                    handler = func_match.group(1) if func_match else "unknown"

                    endpoints.append((method, path, f"{relative_path}:{line_num}", handler))

                # Express routes
                for match in re.finditer(r'(router|app)\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', content):
                    method = match.group(2).upper()
                    path = match.group(3)
                    line_num = content[:match.start()].count('\n') + 1
                    endpoints.append((method, path, f"{relative_path}:{line_num}", "handler"))

            except Exception:
                continue

    return endpoints


def trace_login_flow(project_path: Path, entry_points: list, endpoints: list) -> HappyPath:
    """Trace the login authentication flow."""
    flow = HappyPath(
        name="User Login Flow",
        description="User authentication: credentials submission -> validation -> session/token creation",
        entry_point="/login",
    )

    step_num = 1

    # 1. Find login page
    for path, component, file_path in entry_points:
        if 'login' in path.lower() or 'signin' in path.lower():
            flow.steps.append(FlowStep(
                step_number=step_num,
                component_type="UI",
                component_name=component or "LoginPage",
                file_path=file_path,
                line_number=1,
                description="User navigates to login page",
                details=f"Route: {path}"
            ))
            step_num += 1
            break

    # 2. Find login form submission
    for ext in ['.tsx', '.jsx', '.ts']:
        for file_path in project_path.rglob(f"*login*{ext}"):
            if any(part in file_path.parts for part in ['node_modules', 'dist']):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')

                relative_path = str(file_path.relative_to(project_path))

                # Find form submission or API call
                for i, line in enumerate(lines):
                    if re.search(r'(handleSubmit|mutate\(|login\(|authApi)', line):
                        flow.steps.append(FlowStep(
                            step_number=step_num,
                            component_type="UI",
                            component_name="LoginForm",
                            file_path=relative_path,
                            line_number=i + 1,
                            description="User submits login credentials",
                            details="Form submission triggers API call"
                        ))
                        step_num += 1
                        break
                if step_num > 2:
                    break

            except Exception:
                continue
        if step_num > 2:
            break

    # 3. Find login API endpoint
    for method, path, file_ref, handler in endpoints:
        if 'login' in path.lower() or 'signin' in path.lower():
            flow.steps.append(FlowStep(
                step_number=step_num,
                component_type="Route",
                component_name=handler,
                file_path=file_ref.split(':')[0],
                line_number=int(file_ref.split(':')[1]) if ':' in file_ref else 1,
                description=f"API receives login request",
                details=f"{method} {path}"
            ))
            step_num += 1

            # Find the service/auth file
            auth_file = Path(project_path) / file_ref.split(':')[0]
            if auth_file.exists():
                try:
                    with open(auth_file, 'r') as f:
                        content = f.read()
                        lines = content.split('\n')

                    # Find service call
                    for i, line in enumerate(lines):
                        if re.search(r'(authenticate|verify_password|create.*token)', line, re.I):
                            flow.steps.append(FlowStep(
                                step_number=step_num,
                                component_type="Service",
                                component_name="AuthService",
                                file_path=file_ref.split(':')[0],
                                line_number=i + 1,
                                description="Validate credentials and create token",
                                details="Password verification and token generation"
                            ))
                            step_num += 1
                            break
                except Exception:
                    pass
            break

    # 4. Find token/session storage
    for ext in ['.ts', '.tsx']:
        for file_path in project_path.rglob(f"authStore*{ext}"):
            if any(part in file_path.parts for part in ['node_modules', 'dist']):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')

                relative_path = str(file_path.relative_to(project_path))

                for i, line in enumerate(lines):
                    if re.search(r'(setToken|setAuth|login)', line, re.I):
                        flow.steps.append(FlowStep(
                            step_number=step_num,
                            component_type="State",
                            component_name="AuthStore",
                            file_path=relative_path,
                            line_number=i + 1,
                            description="Store authentication state",
                            details="Token/user info stored in client state"
                        ))
                        step_num += 1
                        break
                if step_num > 4:
                    break

            except Exception:
                continue
        if step_num > 4:
            break

    return flow


def trace_crud_flow(project_path: Path, entry_points: list, endpoints: list) -> Optional[HappyPath]:
    """Trace a core CRUD flow (list -> create)."""
    flow = HappyPath(
        name="Core CRUD Flow",
        description="List resources -> Create new resource",
    )

    step_num = 1

    # Find the main resource by looking at endpoints
    resource_paths = {}
    for method, path, file_ref, handler in endpoints:
        # Skip auth and utility endpoints
        if any(x in path.lower() for x in ['auth', 'login', 'health', 'me', 'password']):
            continue

        # Extract resource name
        parts = path.strip('/').split('/')
        if parts:
            resource = parts[0]
            if resource not in resource_paths:
                resource_paths[resource] = []
            resource_paths[resource].append((method, path, file_ref, handler))

    # Find the most common resource (likely the main entity)
    if not resource_paths:
        return None

    main_resource = max(resource_paths.keys(), key=lambda r: len(resource_paths[r]))
    flow.name = f"{main_resource.title()} CRUD Flow"
    flow.description = f"Manage {main_resource}: list -> create"

    # Trace GET (list)
    for method, path, file_ref, handler in resource_paths[main_resource]:
        if method == 'GET' and '{' not in path:  # List endpoint
            flow.steps.append(FlowStep(
                step_number=step_num,
                component_type="Route",
                component_name=handler,
                file_path=file_ref.split(':')[0],
                line_number=int(file_ref.split(':')[1]) if ':' in file_ref else 1,
                description=f"List {main_resource}",
                details=f"GET {path}"
            ))
            step_num += 1

            # Find corresponding service
            handler_file = Path(project_path) / file_ref.split(':')[0]
            service_dir = handler_file.parent / "services"
            if not service_dir.exists():
                service_dir = handler_file.parent

            for service_file in service_dir.rglob("*.py"):
                try:
                    with open(service_file, 'r') as f:
                        content = f.read()

                    if re.search(rf'(get|list).*{main_resource}', content, re.I):
                        relative = str(service_file.relative_to(project_path))
                        match = re.search(r'def\s+(get|list)\w*', content)
                        if match:
                            line_num = content[:match.start()].count('\n') + 1
                            flow.steps.append(FlowStep(
                                step_number=step_num,
                                component_type="Service",
                                component_name=match.group(0),
                                file_path=relative,
                                line_number=line_num,
                                description=f"Fetch {main_resource} from database",
                            ))
                            step_num += 1
                        break
                except Exception:
                    continue
            break

    # Trace POST (create)
    for method, path, file_ref, handler in resource_paths[main_resource]:
        if method == 'POST':
            flow.steps.append(FlowStep(
                step_number=step_num,
                component_type="Route",
                component_name=handler,
                file_path=file_ref.split(':')[0],
                line_number=int(file_ref.split(':')[1]) if ':' in file_ref else 1,
                description=f"Create new {main_resource}",
                details=f"POST {path}"
            ))
            step_num += 1
            break

    return flow if len(flow.steps) >= 2 else None


def identify_primary_flows(project_path: Path) -> list[HappyPath]:
    """Identify primary user flows in the project."""
    flows = []

    # Find entry points and endpoints
    entry_points = find_frontend_entry_points(project_path)
    endpoints = find_api_endpoints(project_path)

    # Always trace login if it exists
    login_flow = trace_login_flow(project_path, entry_points, endpoints)
    if login_flow and len(login_flow.steps) >= 2:
        flows.append(login_flow)

    # Try to find main CRUD flow
    crud_flow = trace_crud_flow(project_path, entry_points, endpoints)
    if crud_flow and len(crud_flow.steps) >= 2:
        flows.append(crud_flow)

    return flows


def analyze_project(project_path: str, flow_type: FlowType = FlowType.AUTO) -> HappyPathResult:
    """Analyze a project for happy paths."""
    path = Path(project_path)
    result = HappyPathResult(project_path=project_path)

    if not path.exists():
        result.errors.append(f"Project path does not exist: {project_path}")
        return result

    result.primary_flows = identify_primary_flows(path)

    if not result.primary_flows:
        result.errors.append("No primary flows detected")

    return result


def output_json(result: HappyPathResult) -> str:
    """Format result as JSON."""
    output = {
        "project_path": result.project_path,
        "primary_flows": [
            {
                "name": flow.name,
                "description": flow.description,
                "entry_point": flow.entry_point,
                "steps": [
                    {
                        "step": step.step_number,
                        "component_type": step.component_type,
                        "component_name": step.component_name,
                        "file_path": step.file_path,
                        "line_number": step.line_number,
                        "description": step.description,
                        "details": step.details,
                    }
                    for step in flow.steps
                ]
            }
            for flow in result.primary_flows
        ],
        "errors": result.errors,
    }
    return json.dumps(output, indent=2)


def output_markdown(result: HappyPathResult) -> str:
    """Format result as Markdown."""
    lines = ["# Happy Path Analysis Report\n"]
    lines.append(f"**Project:** `{result.project_path}`\n")

    if result.errors and not result.primary_flows:
        lines.append("## Errors\n")
        for error in result.errors:
            lines.append(f"- {error}\n")
        return "\n".join(lines)

    for flow in result.primary_flows:
        lines.append(f"## {flow.name}\n")
        lines.append(f"*{flow.description}*\n")

        if flow.entry_point:
            lines.append(f"**Entry Point:** `{flow.entry_point}`\n")

        lines.append("| Step | Component | File | Description |")
        lines.append("|------|-----------|------|-------------|")

        for step in flow.steps:
            file_ref = f"`{step.file_path}:{step.line_number}`" if step.line_number else f"`{step.file_path}`"
            details = f" ({step.details})" if step.details else ""
            lines.append(f"| {step.step_number} | {step.component_type} | {file_ref} | {step.description}{details} |")

        lines.append("")

    if result.errors:
        lines.append("## Warnings\n")
        for error in result.errors:
            lines.append(f"- {error}\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Trace happy paths through a codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --format markdown
  %(prog)s /path/to/project --flow login
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
        "--flow",
        choices=["login", "crud", "main", "auto"],
        default="auto",
        help="Flow to trace (default: auto)"
    )

    args = parser.parse_args()

    # Map flow argument to enum
    flow_map = {
        "login": FlowType.LOGIN,
        "crud": FlowType.CRUD,
        "main": FlowType.MAIN,
        "auto": FlowType.AUTO,
    }
    flow_type = flow_map.get(args.flow, FlowType.AUTO)

    # Analyze project
    result = analyze_project(args.project_path, flow_type)

    # Output results
    if args.format == "json":
        print(output_json(result))
    else:
        print(output_markdown(result))

    # Return appropriate exit code
    sys.exit(1 if result.errors and not result.primary_flows else 0)


if __name__ == "__main__":
    main()
