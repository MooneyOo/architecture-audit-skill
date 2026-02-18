#!/usr/bin/env python3
"""
Container Discovery Script

Analyzes a codebase to identify deployable/runnable units (containers) and their
communication patterns. Generates C4 Container diagrams and structured reports.

Usage:
    python container_discovery.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: json)
    --diagram                 Include Mermaid C4Container diagram
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


class ContainerType(Enum):
    FRONTEND_SPA = "Frontend SPA"
    FRONTEND_SSR = "Frontend SSR"
    BACKEND_API = "Backend API"
    BACKEND_WORKER = "Background Worker"
    DATABASE = "Database"
    CACHE = "Cache"
    REVERSE_PROXY = "Reverse Proxy"
    CDN = "CDN/Static"
    MESSAGE_QUEUE = "Message Queue"
    UNKNOWN = "Unknown"


class Protocol(Enum):
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    REST = "REST"
    GRAPHQL = "GraphQL"
    WEBSOCKET = "WebSocket"
    GRPC = "gRPC"
    TCP = "TCP"
    AMQP = "AMQP"


@dataclass
class Container:
    name: str
    container_type: ContainerType
    technology: str
    port: Optional[str] = None
    url: Optional[str] = None
    description: str = ""
    config_source: str = ""
    image: Optional[str] = None
    build_context: Optional[str] = None
    environment: dict = field(default_factory=dict)
    depends_on: list = field(default_factory=list)


@dataclass
class Communication:
    from_container: str
    to_container: str
    protocol: Protocol
    description: str = ""


@dataclass
class DiscoveryResult:
    project_path: str
    project_name: str
    containers: list[Container] = field(default_factory=list)
    communications: list[Communication] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Frontend detection patterns
FRONTEND_PATTERNS = {
    "react": {"deps": ["react", "react-dom"], "files": ["src/index.js", "src/main.jsx", "src/main.tsx"]},
    "next.js": {"deps": ["next"], "files": ["next.config.js", "pages/", "app/"]},
    "vue": {"deps": ["vue"], "files": ["src/main.js", ".vue"]},
    "nuxt": {"deps": ["nuxt"], "files": ["nuxt.config.js"]},
    "angular": {"deps": ["@angular/core"], "files": ["angular.json", "src/main.ts"]},
    "svelte": {"deps": ["svelte"], "files": [".svelte"]},
    "vite": {"deps": ["vite"], "files": ["vite.config.ts", "vite.config.js"]},
}

# Backend detection patterns
BACKEND_PATTERNS = {
    "express": {"deps": ["express"], "files": ["server.js", "app.js"], "code": ["express()", "app.listen"]},
    "fastify": {"deps": ["fastify"], "files": [], "code": ["fastify()", "app.listen"]},
    "nestjs": {"deps": ["@nestjs/core"], "files": [], "code": ["@Module", "@Controller"]},
    "fastapi": {"deps": ["fastapi"], "files": ["main.py"], "code": ["FastAPI()", "@app.get", "@router.get"]},
    "django": {"deps": ["django"], "files": ["settings.py", "wsgi.py", "asgi.py"], "code": []},
    "flask": {"deps": ["flask"], "files": ["app.py"], "code": ["Flask(", "app.run"]},
    "gin": {"deps": ["github.com/gin-gonic/gin"], "files": [], "code": []},
}

# Database detection patterns
DATABASE_PATTERNS = {
    "postgresql": {"images": ["postgres"], "deps": ["pg", "psycopg", "psycopg2", "asyncpg"]},
    "mysql": {"images": ["mysql", "mariadb"], "deps": ["mysql", "mysql2", "pymysql"]},
    "mongodb": {"images": ["mongo"], "deps": ["mongoose", "pymongo", "mongodb"]},
    "redis": {"images": ["redis"], "deps": ["redis", "ioredis"]},
    "elasticsearch": {"images": ["elasticsearch"], "deps": ["elasticsearch"]},
}

# Worker detection patterns
WORKER_PATTERNS = {
    "celery": {"deps": ["celery"], "files": ["celery.py", "tasks.py"]},
    "bull": {"deps": ["bull", "bee-queue"], "files": []},
    "sidekiq": {"deps": ["sidekiq"], "files": []},
}


def parse_yaml_simple(content: str) -> dict:
    """Simple YAML parser for docker-compose.yml (handles basic cases)."""
    result = {"services": {}, "volumes": {}}
    current_section = None
    current_service = None
    current_key = None  # Track current key like 'ports', 'depends_on', 'build'
    indent_stack = []

    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith('#'):
            i += 1
            continue

        # Calculate indentation
        indent = len(line) - len(line.lstrip())

        # Pop from stack if dedented
        while indent_stack and indent <= indent_stack[-1][0]:
            popped = indent_stack.pop()
            # Reset current_key when popping out of a key section
            if len(indent_stack) > 0:
                current_key = None

        # Top-level sections
        if indent == 0:
            if stripped.endswith(':'):
                section_name = stripped[:-1]
                if section_name in ['services', 'volumes', 'networks']:
                    current_section = section_name
                    indent_stack.append((indent, section_name))
            else:
                current_section = None
            current_key = None
            i += 1
            continue

        # Handle nested content
        if current_section == "services":
            if ':' in stripped and indent == 2:
                service_name = stripped.split(':')[0].strip()
                current_service = service_name
                result["services"][service_name] = {
                    "ports": [], "environment": {}, "depends_on": [],
                    "volumes": [], "build": None, "image": None
                }
                indent_stack.append((indent, service_name))
                current_key = None
            elif current_service:
                # Check for key-value pairs at indent 4
                if indent == 4 and ':' in stripped:
                    key_part = stripped.split(':', 1)[0].strip()

                    if key_part == 'image':
                        val = stripped.split(':', 1)[1].strip().strip('"\'')
                        result["services"][current_service]["image"] = val
                        current_key = None
                    elif key_part == 'build':
                        val = stripped.split(':', 1)[1].strip().strip('"\'')
                        if val:  # build: ./path
                            result["services"][current_service]["build"] = val
                            current_key = None
                        else:
                            current_key = 'build'
                    elif key_part == 'ports':
                        current_key = 'ports'
                    elif key_part == 'depends_on':
                        current_key = 'depends_on'
                    elif key_part == 'environment':
                        current_key = 'environment'
                    elif key_part == 'volumes':
                        current_key = 'volumes'
                    else:
                        current_key = key_part

                # Handle nested keys like 'context:' under 'build:'
                elif indent == 6 and ':' in stripped and current_key == 'build':
                    key_part = stripped.split(':', 1)[0].strip()
                    if key_part == 'context':
                        val = stripped.split(':', 1)[1].strip().strip('"\'')
                        result["services"][current_service]["build"] = val

                # Handle list items
                elif stripped.startswith('-'):
                    item = stripped.lstrip('- ').strip().strip('"\'')

                    if current_key == 'ports':
                        # Port mapping - extract just the host port
                        port_match = re.match(r'["\']?(\d+):(\d+)["\']?', item)
                        if port_match:
                            result["services"][current_service]["ports"].append(f"{port_match.group(1)}:{port_match.group(2)}")
                    elif current_key == 'depends_on':
                        # Handle depends_on with condition (just extract the service name)
                        dep_name = item.split(':')[0].strip()
                        result["services"][current_service]["depends_on"].append(dep_name)
                    elif current_key == 'volumes':
                        result["services"][current_service]["volumes"].append(item)

                # Handle environment variables with =
                elif '=' in stripped and current_key == 'environment':
                    parts = stripped.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().strip('"\'')
                        result["services"][current_service]["environment"][key] = val

        elif current_section == "volumes":
            if ':' in stripped and indent == 2 and not stripped.startswith('-'):
                vol_name = stripped.split(':')[0].strip()
                result["volumes"][vol_name] = {}

        i += 1

    return result


def parse_docker_compose(project_path: Path) -> tuple[list[Container], list[str]]:
    """Parse docker-compose.yml for container definitions."""
    containers = []
    errors = []

    compose_path = project_path / "docker-compose.yml"
    if not compose_path.exists():
        compose_path = project_path / "docker-compose.yaml"

    if not compose_path.exists():
        return containers, ["No docker-compose.yml found"]

    try:
        with open(compose_path, 'r') as f:
            content = f.read()

        compose_data = parse_yaml_simple(content)

        for service_name, service_config in compose_data.get("services", {}).items():
            container = Container(
                name=service_name,
                container_type=ContainerType.UNKNOWN,
                technology="",
                config_source=str(compose_path.relative_to(project_path))
            )

            # Detect container type from service name or image
            image = service_config.get("image") or ""
            build = service_config.get("build") or ""

            # Database detection (only if image exists)
            if image:
                for db_name, patterns in DATABASE_PATTERNS.items():
                    if any(img in image.lower() for img in patterns["images"]):
                        container.container_type = ContainerType.DATABASE
                        # Proper capitalization for databases
                        db_display_names = {
                            "postgresql": "PostgreSQL",
                            "mysql": "MySQL",
                            "mongodb": "MongoDB",
                            "redis": "Redis",
                            "elasticsearch": "Elasticsearch"
                        }
                        container.technology = db_display_names.get(db_name, db_name.title())
                        container.image = image
                        break

                # Cache detection
                if container.container_type == ContainerType.UNKNOWN and "redis" in image.lower():
                    container.container_type = ContainerType.CACHE
                    container.technology = "Redis"

            # If still unknown, infer from service name
            if container.container_type == ContainerType.UNKNOWN:
                name_lower = service_name.lower()
                if any(x in name_lower for x in ["frontend", "web", "ui", "client"]):
                    container.container_type = ContainerType.FRONTEND_SPA
                    container.build_context = build
                elif any(x in name_lower for x in ["backend", "api", "server"]):
                    container.container_type = ContainerType.BACKEND_API
                    container.build_context = build
                elif any(x in name_lower for x in ["worker", "job", "queue"]):
                    container.container_type = ContainerType.BACKEND_WORKER
                    container.build_context = build
                elif any(x in name_lower for x in ["db", "database", "postgres", "mysql", "mongo"]):
                    container.container_type = ContainerType.DATABASE
                    container.image = image
                elif any(x in name_lower for x in ["cache", "redis"]):
                    container.container_type = ContainerType.CACHE
                    container.image = image
                else:
                    # Default to API if has build context
                    if build:
                        container.container_type = ContainerType.BACKEND_API
                        container.build_context = build
                    elif image:
                        container.image = image

            # Extract ports
            for port_mapping in service_config.get("ports", []):
                if ':' in port_mapping:
                    host_port = port_mapping.split(':')[0]
                    container.port = host_port
                    break

            # Extract dependencies
            container.depends_on = service_config.get("depends_on", [])

            containers.append(container)

    except Exception as e:
        errors.append(f"Error parsing docker-compose.yml: {e}")

    return containers, errors


def detect_frontend_framework(project_path: Path) -> tuple[Optional[str], list[str]]:
    """Detect frontend framework from package.json and file structure."""
    package_json_path = project_path / "package.json"

    if not package_json_path.exists():
        return None, ["No package.json found"]

    try:
        with open(package_json_path, 'r') as f:
            data = json.load(f)

        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

        # Check for Next.js first (it includes React)
        if "next" in deps:
            return f"Next.js {deps['next'].lstrip('^~')}", []

        # Check for Nuxt
        if "nuxt" in deps:
            return f"Nuxt.js {deps['nuxt'].lstrip('^~')}", []

        # Check for Vue
        if "vue" in deps:
            vue_version = deps['vue'].lstrip('^~')
            return f"Vue {vue_version}", []

        # Check for Angular
        if "@angular/core" in deps:
            return f"Angular {deps['@angular/core'].lstrip('^~')}", []

        # Check for Svelte
        if "svelte" in deps:
            return f"Svelte {deps['svelte'].lstrip('^~')}", []

        # Check for React
        if "react" in deps:
            react_version = deps['react'].lstrip('^~')
            build_tool = "Vite" if "vite" in deps else "Webpack" if "webpack" in deps else ""
            return f"React {react_version}" + (f" + {build_tool}" if build_tool else ""), []

        return None, ["No recognized frontend framework found"]

    except Exception as e:
        return None, [f"Error reading package.json: {e}"]


def detect_backend_framework(project_path: Path) -> tuple[Optional[str], list[str]]:
    """Detect backend framework from dependencies and file structure."""
    # Check for Python backends
    requirements_path = project_path / "requirements.txt"
    pyproject_path = project_path / "pyproject.toml"

    python_deps = []

    if requirements_path.exists():
        try:
            with open(requirements_path, 'r') as f:
                python_deps = [line.strip().split('==')[0].split('>=')[0].split('<')[0].lower()
                              for line in f if line.strip() and not line.startswith('#')]
        except:
            pass

    if pyproject_path.exists():
        try:
            with open(pyproject_path, 'r') as f:
                content = f.read()
                # Simple extraction of dependencies from pyproject.toml
                for line in content.split('\n'):
                    if '=' in line and not line.strip().startswith('#'):
                        parts = line.split('=')[0].strip().strip('"\'')
                        if parts and not parts.startswith('['):
                            python_deps.append(parts.lower())
        except:
            pass

    # Check for FastAPI
    if any('fastapi' in d for d in python_deps):
        return "FastAPI", []

    # Check for Django
    if any('django' in d for d in python_deps):
        return "Django", []

    # Check for Flask
    if any('flask' in d for d in python_deps):
        return "Flask", []

    # Check for Node.js backends
    package_json_path = project_path / "package.json"
    if package_json_path.exists():
        try:
            with open(package_json_path, 'r') as f:
                data = json.load(f)
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

            if "express" in deps:
                return f"Express.js {deps['express'].lstrip('^~')}", []
            if "fastify" in deps:
                return f"Fastify {deps['fastify'].lstrip('^~')}", []
            if "@nestjs/core" in deps:
                return f"NestJS {deps['@nestjs/core'].lstrip('^~')}", []
        except:
            pass

    # Check for Go backends
    go_mod_path = project_path / "go.mod"
    if go_mod_path.exists():
        try:
            with open(go_mod_path, 'r') as f:
                content = f.read()
            if "gin-gonic/gin" in content:
                return "Gin", []
            if "labstack/echo" in content:
                return "Echo", []
            return "Go", []
        except:
            pass

    return None, ["No recognized backend framework found"]


def detect_containers_from_structure(project_path: Path) -> tuple[list[Container], list[str]]:
    """Detect containers from project structure when docker-compose is not available."""
    containers = []
    errors = []

    # Look for frontend
    frontend_dirs = ["frontend", "web", "client", "ui", "app"]
    for fd in frontend_dirs:
        frontend_path = project_path / fd
        if frontend_path.exists() and (frontend_path / "package.json").exists():
            framework, ferr = detect_frontend_framework(frontend_path)
            if framework:
                container = Container(
                    name="Frontend",
                    container_type=ContainerType.FRONTEND_SPA,
                    technology=framework,
                    config_source=f"{fd}/package.json"
                )

                # Try to detect port
                if (frontend_path / "vite.config.ts").exists() or (frontend_path / "vite.config.js").exists():
                    container.port = "3000"  # Default Vite port
                elif (frontend_path / "next.config.js").exists():
                    container.port = "3000"  # Default Next.js port

                containers.append(container)
                break

    # Look for backend
    backend_dirs = ["backend", "server", "api", "src"]
    for bd in backend_dirs:
        backend_path = project_path / bd
        if backend_path.exists():
            framework, berr = detect_backend_framework(backend_path)
            if framework:
                container = Container(
                    name="Backend",
                    container_type=ContainerType.BACKEND_API,
                    technology=framework,
                    config_source=f"{bd}/"
                )

                # Try to detect port from common entry files
                for entry_file in ["main.py", "app.py", "server.js", "index.js"]:
                    entry_path = backend_path / entry_file
                    if entry_path.exists():
                        try:
                            with open(entry_path, 'r') as f:
                                content = f.read()
                            # Look for port definitions
                            port_match = re.search(r'port["\']?\s*[:=]\s*(\d+)', content, re.I)
                            if port_match:
                                container.port = port_match.group(1)
                                break
                            port_match = re.search(r':(\d{4})', content)
                            if port_match:
                                container.port = port_match.group(1)
                                break
                        except:
                            pass

                # Default ports
                if not container.port:
                    if "FastAPI" in framework:
                        container.port = "8000"
                    elif "Django" in framework:
                        container.port = "8000"
                    elif "Express" in framework:
                        container.port = "3000"

                containers.append(container)
                break

    # Check root level for backend if not found in subdirectory
    if not any(c.container_type == ContainerType.BACKEND_API for c in containers):
        if (project_path / "main.py").exists() or (project_path / "app.py").exists():
            framework, _ = detect_backend_framework(project_path)
            if framework:
                containers.append(Container(
                    name="Backend",
                    container_type=ContainerType.BACKEND_API,
                    technology=framework,
                    config_source="root"
                ))

    return containers, errors


def detect_communications(containers: list[Container]) -> list[Communication]:
    """Detect communication patterns between containers."""
    communications = []

    # Find frontend, backend, and database containers
    frontend = next((c for c in containers if c.container_type in [ContainerType.FRONTEND_SPA, ContainerType.FRONTEND_SSR]), None)
    backend = next((c for c in containers if c.container_type == ContainerType.BACKEND_API), None)
    databases = [c for c in containers if c.container_type == ContainerType.DATABASE]
    caches = [c for c in containers if c.container_type == ContainerType.CACHE]

    # Frontend -> Backend
    if frontend and backend:
        communications.append(Communication(
            from_container=frontend.name,
            to_container=backend.name,
            protocol=Protocol.HTTPS,
            description="API requests"
        ))

    # Backend -> Databases
    for db in databases:
        communications.append(Communication(
            from_container=backend.name if backend else "Backend",
            to_container=db.name,
            protocol=Protocol.TCP,
            description="Database queries"
        ))

    # Backend -> Caches
    for cache in caches:
        communications.append(Communication(
            from_container=backend.name if backend else "Backend",
            to_container=cache.name,
            protocol=Protocol.TCP,
            description="Caching"
        ))

    # Handle dependencies from docker-compose
    for container in containers:
        for dep in container.depends_on:
            # Check if this dependency isn't already documented
            existing = [c for c in communications
                       if c.from_container == container.name and c.to_container == dep]
            if not existing:
                communications.append(Communication(
                    from_container=container.name,
                    to_container=dep,
                    protocol=Protocol.TCP,
                    description="Service dependency"
                ))

    return communications


def analyze_project(project_path: str) -> DiscoveryResult:
    """Analyze a project to discover containers."""
    path = Path(project_path)

    if not path.exists():
        return DiscoveryResult(
            project_path=project_path,
            project_name=path.name,
            errors=[f"Project path does not exist: {project_path}"]
        )

    result = DiscoveryResult(
        project_path=str(path),
        project_name=path.name
    )

    # Parse docker-compose first
    containers, errors = parse_docker_compose(path)
    result.errors.extend(errors)

    # If no containers from docker-compose, try structure-based detection
    if not containers:
        containers, errors = detect_containers_from_structure(path)
        result.errors.extend(errors)

    # Enhance container detection with framework detection
    for container in containers:
        if container.build_context:
            build_path = path / container.build_context

            if container.container_type in [ContainerType.FRONTEND_SPA, ContainerType.FRONTEND_SSR]:
                framework, _ = detect_frontend_framework(build_path)
                if framework:
                    container.technology = framework

            elif container.container_type == ContainerType.BACKEND_API:
                framework, _ = detect_backend_framework(build_path)
                if framework:
                    container.technology = framework

    result.containers = containers

    # Detect communications
    result.communications = detect_communications(containers)

    return result


def generate_mermaid_diagram(result: DiscoveryResult) -> str:
    """Generate C4Container Mermaid diagram."""
    lines = ["```mermaid", "C4Container"]
    lines.append(f'    title Container Diagram - {result.project_name}')
    lines.append("")

    # Add user
    lines.append('    Person(user, "User", "End user of the system")')
    lines.append("")

    # Group containers by type
    frontend_containers = [c for c in result.containers
                          if c.container_type in [ContainerType.FRONTEND_SPA, ContainerType.FRONTEND_SSR]]
    backend_containers = [c for c in result.containers
                         if c.container_type in [ContainerType.BACKEND_API, ContainerType.BACKEND_WORKER]]
    db_containers = [c for c in result.containers if c.container_type == ContainerType.DATABASE]
    cache_containers = [c for c in result.containers if c.container_type == ContainerType.CACHE]
    other_containers = [c for c in result.containers
                       if c.container_type not in [ContainerType.FRONTEND_SPA, ContainerType.FRONTEND_SSR,
                                                   ContainerType.BACKEND_API, ContainerType.BACKEND_WORKER,
                                                   ContainerType.DATABASE, ContainerType.CACHE]]

    # Add frontend containers
    for c in frontend_containers:
        desc = c.description or "User-facing application"
        lines.append(f'    Container({c.name.lower().replace("-", "_")}, "{c.name}", "{c.technology}", "{desc}")')

    # Add backend containers
    for c in backend_containers:
        desc = c.description or "Business logic and API"
        lines.append(f'    Container({c.name.lower().replace("-", "_")}, "{c.name}", "{c.technology}", "{desc}")')

    # Add database containers
    for c in db_containers:
        desc = c.description or "Persistent data storage"
        lines.append(f'    ContainerDb({c.name.lower().replace("-", "_")}, "{c.name}", "{c.technology}", "{desc}")')

    # Add cache containers
    for c in cache_containers:
        desc = c.description or "Session and data cache"
        lines.append(f'    ContainerDb({c.name.lower().replace("-", "_")}, "{c.name}", "{c.technology}", "{desc}")')

    # Add other containers
    for c in other_containers:
        desc = c.description or c.container_type.value
        lines.append(f'    Container({c.name.lower().replace("-", "_")}, "{c.name}", "{c.technology}", "{desc}")')

    lines.append("")

    # Add relationships
    # User -> Frontend
    for c in frontend_containers:
        lines.append(f'    Rel(user, {c.name.lower().replace("-", "_")}, "Uses", "HTTPS")')

    # Frontend -> Backend
    for fc in frontend_containers:
        for bc in backend_containers:
            if bc.container_type == ContainerType.BACKEND_API:
                lines.append(f'    Rel({fc.name.lower().replace("-", "_")}, {bc.name.lower().replace("-", "_")}, "API calls", "REST/HTTPS")')

    # Backend -> Database
    for bc in backend_containers:
        for dc in db_containers:
            lines.append(f'    Rel({bc.name.lower().replace("-", "_")}, {dc.name.lower().replace("-", "_")}, "Reads/Writes", "TCP")')

    # Backend -> Cache
    for bc in backend_containers:
        for cc in cache_containers:
            lines.append(f'    Rel({bc.name.lower().replace("-", "_")}, {cc.name.lower().replace("-", "_")}, "Caches", "TCP")')

    # Add communications from detection
    for comm in result.communications:
        from_id = comm.from_container.lower().replace("-", "_")
        to_id = comm.to_container.lower().replace("-", "_")
        protocol = comm.protocol.value
        desc = comm.description

        # Check if this relationship already exists
        rel_line = f'    Rel({from_id}, {to_id}, "{desc}", "{protocol}")'
        if rel_line not in lines:
            lines.append(rel_line)

    lines.append("```")
    return "\n".join(lines)


def output_json(result: DiscoveryResult, include_diagram: bool = False) -> str:
    """Format results as JSON."""
    output = {
        "project_path": result.project_path,
        "project_name": result.project_name,
        "containers": [
            {
                "name": c.name,
                "type": c.container_type.value,
                "technology": c.technology,
                "port": c.port,
                "url": c.url,
                "description": c.description,
                "config_source": c.config_source,
                "image": c.image,
                "build_context": c.build_context,
                "depends_on": c.depends_on
            }
            for c in result.containers
        ],
        "communications": [
            {
                "from": c.from_container,
                "to": c.to_container,
                "protocol": c.protocol.value,
                "description": c.description
            }
            for c in result.communications
        ],
        "errors": result.errors
    }

    if include_diagram:
        output["mermaid_diagram"] = generate_mermaid_diagram(result)

    return json.dumps(output, indent=2)


def output_markdown(result: DiscoveryResult, include_diagram: bool = False) -> str:
    """Format results as Markdown."""
    lines = [f"# Container Discovery Report\n"]
    lines.append(f"**Project:** `{result.project_path}`\n")
    lines.append(f"**Project Name:** {result.project_name}\n")

    if result.errors:
        lines.append("## Errors\n")
        for error in result.errors:
            lines.append(f"- {error}\n")
        lines.append("")

    # Container table
    lines.append("## Containers Identified\n")
    lines.append("| Container | Type | Technology | Port | Config Source |")
    lines.append("|-----------|------|------------|------|---------------|")
    for c in result.containers:
        lines.append(f"| {c.name} | {c.container_type.value} | {c.technology} | {c.port or '-'} | {c.config_source} |")
    lines.append("")

    # Container details table
    lines.append("## Container Details\n")
    lines.append("| Container | Technology | Responsibility | Communicates With |")
    lines.append("|-----------|------------|----------------|-------------------|")

    # Build communication map
    comm_map = {}
    for comm in result.communications:
        if comm.from_container not in comm_map:
            comm_map[comm.from_container] = []
        comm_map[comm.from_container].append(comm.to_container)

    for c in result.containers:
        communicates = ", ".join(comm_map.get(c.name, [])) or "-"
        resp = c.description or f"{c.container_type.value}"
        lines.append(f"| {c.name} | {c.technology} | {resp} | {communicates} |")
    lines.append("")

    # Communication protocols table
    lines.append("## Communication Protocols\n")
    lines.append("| From | To | Protocol | Purpose |")
    lines.append("|------|-----|----------|---------|")
    for c in result.communications:
        lines.append(f"| {c.from_container} | {c.to_container} | {c.protocol.value} | {c.description} |")
    lines.append("")

    # Mermaid diagram
    if include_diagram:
        lines.append("## C4 Container Diagram\n")
        lines.append(generate_mermaid_diagram(result))
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Discover containers in a codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --format markdown
  %(prog)s /path/to/project --format markdown --diagram
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
        "--diagram",
        action="store_true",
        help="Include Mermaid C4Container diagram"
    )

    args = parser.parse_args()

    # Analyze project
    result = analyze_project(args.project_path)

    # Output results
    if args.format == "json":
        print(output_json(result, include_diagram=args.diagram))
    else:
        print(output_markdown(result, include_diagram=args.diagram))

    # Return appropriate exit code
    has_critical_errors = len(result.errors) > 0 and len(result.containers) == 0
    sys.exit(1 if has_critical_errors else 0)


if __name__ == "__main__":
    main()
