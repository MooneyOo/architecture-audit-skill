#!/usr/bin/env python3
"""
Component Breakdown Script

Analyzes a codebase to identify architectural layers, components, modules,
and cross-cutting concerns. Generates C4 Component diagrams and structured reports.

Usage:
    python component_breakdown.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: json)
    --diagram                 Include Mermaid C4Component diagram
    --frontend                Include frontend analysis
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


class Layer(Enum):
    CONTROLLER = "Controller"
    SERVICE = "Service"
    REPOSITORY = "Repository"
    MODEL = "Model"
    MIDDLEWARE = "Middleware"
    UTILITY = "Utility"
    SCHEMA = "Schema"
    ROUTER = "Router"
    UNKNOWN = "Unknown"


class FrontendStateType(Enum):
    REDUX = "Redux"
    ZUSTAND = "Zustand"
    CONTEXT = "React Context"
    PINIA = "Pinia"
    VUEX = "Vuex"
    MOBX = "MobX"
    RECOIL = "Recoil"
    JOTAI = "Jotai"
    UNKNOWN = "Unknown"


@dataclass
class Component:
    name: str
    layer: Layer
    file_path: str
    responsibility: str = ""
    module: str = ""
    exports: list = field(default_factory=list)


@dataclass
class Module:
    name: str
    path: str
    components: list[Component] = field(default_factory=list)
    description: str = ""


@dataclass
class CrossCuttingConcern:
    name: str
    implementation: str
    file_path: str
    description: str = ""


@dataclass
class FrontendRoute:
    path: str
    component: str
    file_path: str
    is_protected: bool = False


@dataclass
class FrontendStore:
    name: str
    store_type: FrontendStateType
    file_path: str
    description: str = ""


@dataclass
class FrontendComponent:
    name: str
    group: str
    file_path: str
    description: str = ""


@dataclass
class BreakdownResult:
    project_path: str
    project_name: str
    framework: str = ""
    layers: dict[str, list[Component]] = field(default_factory=dict)
    modules: list[Module] = field(default_factory=list)
    cross_cutting_concerns: list[CrossCuttingConcern] = field(default_factory=list)
    frontend_routes: list[FrontendRoute] = field(default_factory=list)
    frontend_stores: list[FrontendStore] = field(default_factory=list)
    frontend_components: list[FrontendComponent] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Backend layer detection patterns
LAYER_PATTERNS = {
    Layer.CONTROLLER: {
        "dirs": ["controllers", "controller", "handlers", "handler"],
        "files": ["controller", "ctrl"],
        "code": ["@Controller", "@RestController", "router.METHOD", "app.METHOD"]
    },
    Layer.ROUTER: {
        "dirs": ["routes", "routers", "api"],
        "files": ["router", "route", "routes"],
        "code": ["APIRouter", "Router()", "express.Router"]
    },
    Layer.SERVICE: {
        "dirs": ["services", "service", "usecases", "usecase", "domain", "business"],
        "files": ["service", "svc", "usecase"],
        "code": ["@Service", "@Injectable"]
    },
    Layer.REPOSITORY: {
        "dirs": ["repositories", "repository", "dao", "data", "repos"],
        "files": ["repository", "repo", "dao", "crud"],
        "code": ["@Repository", "Repository["]
    },
    Layer.MODEL: {
        "dirs": ["models", "model", "entities", "entity", "schemas"],
        "files": ["model", "entity", "schema"],
        "code": ["@Entity", "Table(", "class.*Model", "SQLAlchemy"]
    },
    Layer.MIDDLEWARE: {
        "dirs": ["middleware", "middlewares", "interceptors", "interceptor"],
        "files": ["middleware", "interceptor"],
        "code": ["@middleware", "app.use(", "Middleware"]
    },
    Layer.UTILITY: {
        "dirs": ["utils", "util", "lib", "libs", "helpers", "helper", "common"],
        "files": ["util", "helper", "lib", "utils"],
        "code": []
    },
    Layer.SCHEMA: {
        "dirs": ["schemas", "dto", "dtos"],
        "files": ["schema", "dto", "schemas"],
        "code": ["BaseModel", "pydantic"]
    }
}

# Cross-cutting concern patterns
CROSS_CUTTING_PATTERNS = {
    "Authentication": {
        "patterns": ["auth", "authenticate", "jwt", "passport", "token", "login", "oauth"],
        "files": ["auth", "jwt", "token", "login"]
    },
    "Authorization": {
        "patterns": ["authorize", "permission", "guard", "role", "canActivate", "rbac"],
        "files": ["authorize", "permission", "guard", "roles"]
    },
    "Logging": {
        "patterns": ["logger", "winston", "pino", "bunyan", "log4js", "logging", "log"],
        "files": ["logger", "log", "logging"]
    },
    "Error Handling": {
        "patterns": ["errorHandler", "exception", "catch", "ErrorHandler", "Exception"],
        "files": ["error", "exception", "errors"]
    },
    "Validation": {
        "patterns": ["validate", "validator", "joi", "zod", "class-validator", "pydantic"],
        "files": ["validator", "validate", "validation"]
    },
    "Rate Limiting": {
        "patterns": ["rateLimit", "rate-limit", "throttle", "slowapi"],
        "files": ["rate", "throttle", "limit"]
    },
    "Caching": {
        "patterns": ["cache", "redis", "memcached"],
        "files": ["cache"]
    },
    "Encryption": {
        "patterns": ["encrypt", "crypto", "cryptography", "cipher"],
        "files": ["crypto", "encrypt", "encryption"]
    }
}

# Frontend framework detection
FRONTEND_FRAMEWORKS = {
    "react": {
        "package": "react",
        "router_packages": ["react-router", "react-router-dom"],
        "state_packages": {
            "redux": ["redux", "@reduxjs/toolkit"],
            "zustand": ["zustand"],
            "mobx": ["mobx"],
            "recoil": ["recoil"],
            "jotai": ["jotai"],
            "context": []  # Built-in
        }
    },
    "vue": {
        "package": "vue",
        "router_packages": ["vue-router"],
        "state_packages": {
            "pinia": ["pinia"],
            "vuex": ["vuex"]
        }
    },
    "angular": {
        "package": "@angular/core",
        "router_packages": ["@angular/router"],
        "state_packages": {
            "ngrx": ["@ngrx/store"],
            "ngxs": ["@ngxs/store"]
        }
    },
    "svelte": {
        "package": "svelte",
        "router_packages": ["svelte-routing", "@sveltejs/kit"],
        "state_packages": {}
    }
}


def detect_backend_framework(project_path: Path) -> str:
    """Detect the backend framework being used."""
    # Check for Python frameworks
    requirements_path = project_path / "requirements.txt"
    if requirements_path.exists():
        try:
            with open(requirements_path, 'r') as f:
                content = f.read().lower()
            if 'fastapi' in content:
                return "FastAPI"
            if 'django' in content:
                return "Django"
            if 'flask' in content:
                return "Flask"
        except:
            pass

    # Check for Node.js frameworks
    package_json_path = project_path / "package.json"
    if package_json_path.exists():
        try:
            with open(package_json_path, 'r') as f:
                data = json.load(f)
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

            if "@nestjs/core" in deps:
                return "NestJS"
            if "express" in deps:
                return "Express.js"
            if "fastify" in deps:
                return "Fastify"
        except:
            pass

    return "Unknown"


def detect_layer_from_path(file_path: str, content: str = "") -> Layer:
    """Determine the layer of a component from its file path and content."""
    path_lower = file_path.lower()
    file_name = Path(file_path).stem.lower()

    for layer, patterns in LAYER_PATTERNS.items():
        # Check directory patterns
        for dir_pattern in patterns["dirs"]:
            if f"/{dir_pattern}/" in path_lower or f"\\{dir_pattern}\\" in path_lower:
                return layer

        # Check file name patterns
        for file_pattern in patterns["files"]:
            if file_pattern in file_name:
                return layer

    # Check code patterns if content provided
    if content:
        content_lower = content.lower()
        for layer, patterns in LAYER_PATTERNS.items():
            for code_pattern in patterns["code"]:
                if code_pattern.lower() in content_lower:
                    return layer

    return Layer.UNKNOWN


def extract_exports_python(content: str) -> list[str]:
    """Extract exports (classes, functions) from Python code."""
    exports = []

    # Find class definitions
    class_pattern = r'^class\s+(\w+)'
    for match in re.finditer(class_pattern, content, re.MULTILINE):
        exports.append(match.group(1))

    # Find top-level function definitions
    func_pattern = r'^def\s+(\w+)'
    for match in re.finditer(func_pattern, content, re.MULTILINE):
        exports.append(match.group(1))

    return exports


def extract_exports_typescript(content: str) -> list[str]:
    """Extract exports from TypeScript/JavaScript code."""
    exports = []

    # Find export class/function/const
    patterns = [
        r'export\s+(?:default\s+)?class\s+(\w+)',
        r'export\s+(?:default\s+)?function\s+(\w+)',
        r'export\s+const\s+(\w+)',
        r'export\s+interface\s+(\w+)',
        r'export\s+type\s+(\w+)',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content):
            exports.append(match.group(1))

    return exports


def extract_docstring_python(content: str) -> str:
    """Extract the module-level docstring from Python code."""
    # Look for module-level docstring
    match = re.search(r'^("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', content)
    if match:
        docstring = match.group(1).strip('"\'')
        # Get first line or first sentence
        first_line = docstring.split('\n')[0].strip()
        return first_line[:100] if len(first_line) > 100 else first_line
    return ""


def analyze_backend_components(project_path: Path, framework: str) -> tuple[dict[str, list[Component]], list[Module], list[str]]:
    """Analyze backend components and group by layer."""
    layers: dict[str, list[Component]] = {layer.value: [] for layer in Layer}
    modules_dict: dict[str, Module] = {}
    errors = []

    # Find source directory
    src_dirs = ["src", "app", "backend/src", "server/src", "api/src"]
    src_path = None
    for sd in src_dirs:
        candidate = project_path / sd
        if candidate.exists():
            src_path = candidate
            break

    if not src_path:
        src_path = project_path

    # Scan for Python files
    for py_file in src_path.rglob("*.py"):
        # Skip __pycache__, test files, etc.
        if "__pycache__" in str(py_file) or "test" in py_file.name.lower():
            continue

        rel_path = str(py_file.relative_to(project_path))

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue

        # Detect layer
        layer = detect_layer_from_path(rel_path, content)
        if layer == Layer.UNKNOWN:
            continue

        # Extract exports
        exports = extract_exports_python(content)
        if not exports:
            continue

        # Extract description
        description = extract_docstring_python(content)

        # Determine module from path
        parts = Path(rel_path).parts
        module_name = ""
        if len(parts) > 1:
            # For FastAPI-style: src/module/router.py -> module
            if "src" in parts:
                src_idx = parts.index("src")
                if len(parts) > src_idx + 1:
                    module_name = parts[src_idx + 1]

        # Create components for each export
        file_stem = py_file.stem
        for export_name in exports[:5]:  # Limit to first 5 exports
            component = Component(
                name=export_name,
                layer=layer,
                file_path=rel_path,
                responsibility=description,
                module=module_name,
                exports=exports
            )
            layers[layer.value].append(component)

        # Add to module if applicable
        if module_name:
            if module_name not in modules_dict:
                modules_dict[module_name] = Module(
                    name=module_name,
                    path=str(Path(rel_path).parent)
                )
            for export_name in exports[:5]:
                modules_dict[module_name].components.append(Component(
                    name=export_name,
                    layer=layer,
                    file_path=rel_path,
                    responsibility=description,
                    module=module_name
                ))

    # Scan for TypeScript/JavaScript files
    for ts_file in src_path.rglob("*.ts"):
        if "node_modules" in str(ts_file) or ".d.ts" in str(ts_file):
            continue

        rel_path = str(ts_file.relative_to(project_path))

        try:
            with open(ts_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue

        # Detect layer
        layer = detect_layer_from_path(rel_path, content)
        if layer == Layer.UNKNOWN:
            continue

        # Extract exports
        exports = extract_exports_typescript(content)
        if not exports:
            continue

        file_stem = ts_file.stem
        for export_name in exports[:5]:
            component = Component(
                name=export_name,
                layer=layer,
                file_path=rel_path,
                module="",
                exports=exports
            )
            layers[layer.value].append(component)

    modules = list(modules_dict.values())
    return layers, modules, errors


def detect_cross_cutting_concerns(project_path: Path) -> list[CrossCuttingConcern]:
    """Detect cross-cutting concerns in the codebase."""
    concerns = []

    src_dirs = ["src", "app", "backend/src", "server/src", "api/src"]
    src_path = None
    for sd in src_dirs:
        candidate = project_path / sd
        if candidate.exists():
            src_path = candidate
            break

    if not src_path:
        src_path = project_path

    for py_file in src_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        rel_path = str(py_file.relative_to(project_path))
        file_name = py_file.stem.lower()

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue

        content_lower = content.lower()

        for concern_name, patterns in CROSS_CUTTING_PATTERNS.items():
            # Check file name
            file_match = any(fp in file_name for fp in patterns["files"])

            # Check content
            content_match = any(p in content_lower for p in patterns["patterns"])

            if file_match or content_match:
                # Avoid duplicates
                if not any(c.name == concern_name and c.file_path == rel_path for c in concerns):
                    concerns.append(CrossCuttingConcern(
                        name=concern_name,
                        implementation=py_file.stem,
                        file_path=rel_path,
                        description=f"{concern_name} implementation"
                    ))

    return concerns


def detect_frontend_framework(package_json_path: Path) -> tuple[Optional[str], dict]:
    """Detect frontend framework from package.json."""
    if not package_json_path.exists():
        return None, {}

    try:
        with open(package_json_path, 'r') as f:
            data = json.load(f)
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

        for fw_name, fw_config in FRONTEND_FRAMEWORKS.items():
            if fw_config["package"] in deps:
                return fw_name, deps
    except:
        pass

    return None, {}


def analyze_frontend_routing(project_path: Path, framework: str) -> list[FrontendRoute]:
    """Analyze frontend routing structure."""
    routes = []

    # Find router file
    router_files = ["router.tsx", "router.ts", "routes.tsx", "routes.ts", "App.tsx"]
    src_path = project_path / "src" if (project_path / "src").exists() else project_path

    for router_file in router_files:
        router_path = src_path / router_file
        if router_path.exists():
            try:
                with open(router_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # React Router patterns
                if framework == "react":
                    # Match <Route path="..." element={<Component />} />
                    pattern = r'<Route\s+path=["\']([^"\']+)["\'].*?element=\{<(?:React\.)?(\w+)'
                    for match in re.finditer(pattern, content, re.DOTALL):
                        routes.append(FrontendRoute(
                            path=match.group(1),
                            component=match.group(2),
                            file_path=str(router_path.relative_to(project_path))
                        ))

                    # Match <Route path="..." component={Component} />
                    pattern = r'<Route\s+path=["\']([^"\']+)["\'].*?component=\{(\w+)'
                    for match in re.finditer(pattern, content, re.DOTALL):
                        routes.append(FrontendRoute(
                            path=match.group(1),
                            component=match.group(2),
                            file_path=str(router_path.relative_to(project_path))
                        ))

            except:
                pass

    # Also check for Next.js-style file-based routing
    pages_dir = src_path / "pages"
    if pages_dir.exists():
        for page_file in pages_dir.rglob("*.tsx"):
            rel_path = str(page_file.relative_to(pages_dir))
            # Convert file path to route path
            route_path = "/" + rel_path.replace("\\", "/").replace("index.tsx", "").replace(".tsx", "")
            if route_path.endswith("/"):
                route_path = route_path[:-1]
            if not route_path:
                route_path = "/"

            routes.append(FrontendRoute(
                path=route_path,
                component=page_file.stem,
                file_path=str(page_file.relative_to(project_path))
            ))

    # Also check for app directory (Next.js 13+)
    app_dir = src_path / "app"
    if app_dir.exists():
        for page_file in app_dir.rglob("page.tsx"):
            rel_path = str(page_file.parent.relative_to(app_dir))
            route_path = "/" + rel_path.replace("\\", "/")
            if route_path == "/.":
                route_path = "/"

            routes.append(FrontendRoute(
                path=route_path,
                component="Page",
                file_path=str(page_file.relative_to(project_path))
            ))

    return routes


def analyze_frontend_state(project_path: Path, framework: str, deps: dict) -> list[FrontendStore]:
    """Analyze frontend state management."""
    stores = []

    src_path = project_path / "src" if (project_path / "src").exists() else project_path

    # Detect state management type
    state_type = FrontendStateType.UNKNOWN

    if framework == "react":
        if "zustand" in deps:
            state_type = FrontendStateType.ZUSTAND
        elif any(p in deps for p in ["redux", "@reduxjs/toolkit"]):
            state_type = FrontendStateType.REDUX
        elif "mobx" in deps:
            state_type = FrontendStateType.MOBX
        elif "recoil" in deps:
            state_type = FrontendStateType.RECOIL
        elif "jotai" in deps:
            state_type = FrontendStateType.JOTAI
    elif framework == "vue":
        if "pinia" in deps:
            state_type = FrontendStateType.PINIA
        elif "vuex" in deps:
            state_type = FrontendStateType.VUEX

    # Find store files
    store_dirs = ["store", "stores", "state", "redux", "flux"]
    for store_dir in store_dirs:
        store_path = src_path / store_dir
        if store_path.exists():
            for store_file in store_path.rglob("*"):
                if store_file.suffix in [".ts", ".tsx", ".js", ".jsx"]:
                    store_name = store_file.stem
                    if store_name.endswith("Store"):
                        store_name = store_name[:-5]
                    elif store_name.endswith("store"):
                        store_name = store_name[:-5]

                    stores.append(FrontendStore(
                        name=store_name,
                        store_type=state_type,
                        file_path=str(store_file.relative_to(project_path))
                    ))

    return stores


def analyze_frontend_components(project_path: Path) -> list[FrontendComponent]:
    """Analyze frontend component organization."""
    components = []

    src_path = project_path / "src" if (project_path / "src").exists() else project_path
    components_path = src_path / "components"

    if not components_path.exists():
        return components

    for comp_file in components_path.rglob("*.tsx"):
        if ".test." in str(comp_file) or ".spec." in str(comp_file):
            continue

        rel_path = str(comp_file.relative_to(components_path))
        parts = Path(rel_path).parts

        # Determine group
        if len(parts) > 1:
            group = parts[0]
        else:
            group = "Shared"

        components.append(FrontendComponent(
            name=comp_file.stem,
            group=group,
            file_path=str(comp_file.relative_to(project_path))
        ))

    # Also check pages
    pages_path = src_path / "pages"
    if pages_path.exists():
        for page_file in pages_path.rglob("*.tsx"):
            components.append(FrontendComponent(
                name=page_file.stem,
                group="Pages",
                file_path=str(page_file.relative_to(project_path))
            ))

    return components


def analyze_project(project_path: str, include_frontend: bool = False) -> BreakdownResult:
    """Analyze a project to discover components."""
    path = Path(project_path)

    if not path.exists():
        return BreakdownResult(
            project_path=project_path,
            project_name=path.name,
            errors=[f"Project path does not exist: {project_path}"]
        )

    result = BreakdownResult(
        project_path=str(path),
        project_name=path.name
    )

    # Detect backend framework
    result.framework = detect_backend_framework(path)

    # Analyze backend components
    layers, modules, errors = analyze_backend_components(path, result.framework)
    result.layers = layers
    result.modules = modules
    result.errors.extend(errors)

    # Detect cross-cutting concerns
    result.cross_cutting_concerns = detect_cross_cutting_concerns(path)

    # Frontend analysis
    if include_frontend:
        # Look for frontend directory
        frontend_dirs = ["frontend", "web", "client", "ui"]
        for fd in frontend_dirs:
            frontend_path = path / fd
            if frontend_path.exists():
                fw_name, deps = detect_frontend_framework(frontend_path / "package.json")
                if fw_name:
                    result.frontend_routes = analyze_frontend_routing(frontend_path, fw_name)
                    result.frontend_stores = analyze_frontend_state(frontend_path, fw_name, deps)
                    result.frontend_components = analyze_frontend_components(frontend_path)
                break

    return result


# ============================================================================
# Chunked Analysis Support (Epic 4)
# ============================================================================

def analyze_project_chunked(
    project_path: str,
    include_frontend: bool = False,
    chunk_size: int = 100,
    resume: bool = True,
    force: bool = False,
    show_progress: bool = False,
    quiet: bool = False
) -> BreakdownResult:
    """
    Analyze a project using chunked processing for large codebases.

    Args:
        project_path: Path to the project
        include_frontend: Include frontend analysis
        chunk_size: Number of files per chunk
        resume: Resume from interrupted analysis
        force: Force re-analysis (ignore cache)
        show_progress: Show progress bar
        quiet: Suppress progress output

    Returns:
        BreakdownResult with analysis results
    """
    if not SCALABILITY_AVAILABLE:
        # Fall back to regular analysis if modules not available
        return analyze_project(project_path, include_frontend)

    path = Path(project_path)

    if not path.exists():
        return BreakdownResult(
            project_path=project_path,
            project_name=path.name,
            errors=[f"Project path does not exist: {project_path}"]
        )

    result = BreakdownResult(
        project_path=str(path),
        project_name=path.name
    )

    # Detect backend framework
    result.framework = detect_backend_framework(path)

    # Setup cache
    cache_dir = path / ".audit_cache" / "component_breakdown"
    cache = CacheManager(cache_dir)

    if force:
        cache.invalidate()

    # Setup progress tracking
    total_files = count_files(path)
    progress = None
    if show_progress and not quiet:
        progress = ProgressTracker(
            total=total_files,
            phase="Component breakdown analysis",
            quiet=quiet
        )

    # Configure chunked analyzer
    config = ChunkConfig(
        chunk_size=chunk_size,
        output_dir=cache_dir / "chunks",
        resume=resume,
        file_extensions={'.py', '.ts', '.tsx', '.js', '.jsx'}
    )

    analyzer = ChunkedAnalyzer(config)

    # Find source directory
    src_dirs = ["src", "app", "backend/src", "server/src", "api/src"]
    src_path = None
    for sd in src_dirs:
        candidate = path / sd
        if candidate.exists():
            src_path = candidate
            break
    if not src_path:
        src_path = path

    # Define analyzer function
    def analyze_component_file(file_path: Path) -> dict:
        """Analyze a single file for components."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            rel_path = str(file_path.relative_to(path))
            components = []
            exports = []

            # Detect layer
            layer = detect_layer_from_path(rel_path, content)
            if layer == Layer.UNKNOWN:
                return {"file": str(file_path), "components": []}

            # Extract exports based on file type
            if file_path.suffix == '.py':
                exports = extract_exports_python(content)
                description = extract_docstring_python(content)
            elif file_path.suffix in {'.ts', '.tsx', '.js', '.jsx'}:
                exports = extract_exports_typescript(content)
                description = ""
            else:
                return {"file": str(file_path), "components": []}

            if not exports:
                return {"file": str(file_path), "components": []}

            # Determine module from path
            parts = Path(rel_path).parts
            module_name = ""
            if len(parts) > 1:
                if "src" in parts:
                    src_idx = parts.index("src")
                    if len(parts) > src_idx + 1:
                        module_name = parts[src_idx + 1]

            # Create component data
            for export_name in exports[:5]:
                components.append({
                    "name": export_name,
                    "layer": layer.value,
                    "file_path": rel_path,
                    "responsibility": description,
                    "module": module_name
                })

            # Check for cross-cutting concerns
            concerns = []
            file_name = file_path.stem.lower()
            content_lower = content.lower()

            for concern_name, patterns in CROSS_CUTTING_PATTERNS.items():
                file_match = any(fp in file_name for fp in patterns["files"])
                content_match = any(p in content_lower for p in patterns["patterns"])
                if file_match or content_match:
                    concerns.append({
                        "name": concern_name,
                        "implementation": file_path.stem,
                        "file_path": rel_path
                    })

            return {
                "file": str(file_path),
                "components": components,
                "concerns": concerns,
                "module": module_name
            }

        except Exception as e:
            return {"file": str(file_path), "error": str(e)}

    # Process in chunks
    all_components = []
    all_concerns = []
    modules_dict = {}

    for chunk_result in analyzer.analyze_project(path, analyze_component_file):
        for file_result in chunk_result.results:
            if "components" in file_result:
                for comp_data in file_result["components"]:
                    layer = comp_data["layer"]
                    if layer not in result.layers:
                        result.layers[layer] = []

                    component = Component(
                        name=comp_data["name"],
                        layer=Layer(comp_data["layer"]),
                        file_path=comp_data["file_path"],
                        responsibility=comp_data.get("responsibility", ""),
                        module=comp_data.get("module", "")
                    )
                    result.layers[layer].append(component)
                    all_components.append(component)

                    # Add to module
                    module_name = comp_data.get("module", "")
                    if module_name:
                        if module_name not in modules_dict:
                            modules_dict[module_name] = Module(
                                name=module_name,
                                path=str(Path(comp_data["file_path"]).parent)
                            )
                        modules_dict[module_name].components.append(component)

            if "concerns" in file_result:
                for concern_data in file_result["concerns"]:
                    concern = CrossCuttingConcern(
                        name=concern_data["name"],
                        implementation=concern_data["implementation"],
                        file_path=concern_data["file_path"]
                    )
                    # Avoid duplicates
                    if not any(c.name == concern.name and c.file_path == concern.file_path for c in all_concerns):
                        all_concerns.append(concern)

            if "error" in file_result:
                result.errors.append(f"Error in {file_result['file']}: {file_result['error']}")

        if progress:
            progress.update(chunk_result.files_processed)

    if progress:
        progress.complete()

    result.modules = list(modules_dict.values())
    result.cross_cutting_concerns = all_concerns

    # Frontend analysis (if requested)
    if include_frontend:
        frontend_dirs = ["frontend", "web", "client", "ui"]
        for fd in frontend_dirs:
            frontend_path = path / fd
            if frontend_path.exists():
                fw_name, deps = detect_frontend_framework(frontend_path / "package.json")
                if fw_name:
                    result.frontend_routes = analyze_frontend_routing(frontend_path, fw_name)
                    result.frontend_stores = analyze_frontend_state(frontend_path, fw_name, deps)
                    result.frontend_components = analyze_frontend_components(frontend_path)
                break

    return result


# ============================================================================


def generate_mermaid_diagram(result: BreakdownResult) -> str:
    """Generate C4Component Mermaid diagram."""
    lines = ["```mermaid", "C4Component"]
    lines.append(f'    title Component Diagram - {result.project_name}')
    lines.append("")

    # Create container boundary for the backend
    lines.append('    Container_Boundary(backend, "Backend API") {')

    # Group components by layer
    layer_order = [Layer.ROUTER, Layer.CONTROLLER, Layer.SERVICE, Layer.REPOSITORY, Layer.MODEL, Layer.MIDDLEWARE, Layer.UTILITY]

    for layer in layer_order:
        components = result.layers.get(layer.value, [])
        if components:
            # Get unique component names
            unique_names = list(set(c.name for c in components[:10]))  # Limit
            layer_name = layer.value.lower()

            for i, name in enumerate(unique_names[:5]):  # Max 5 per layer
                comp_id = f"{layer_name}_{i}".replace(" ", "_").lower()
                lines.append(f'        Component({comp_id}, "{name}", "{layer.value}", "")')

    lines.append("    }")
    lines.append("")

    # Add relationships (simplified)
    lines.append('    Rel(router_0, service_0, "Uses")')
    lines.append('    Rel(service_0, repository_0, "Uses")')
    lines.append('    Rel(repository_0, model_0, "Uses")')

    lines.append("```")
    return "\n".join(lines)


def output_json(result: BreakdownResult, include_diagram: bool = False) -> str:
    """Format results as JSON."""
    output = {
        "project_path": result.project_path,
        "project_name": result.project_name,
        "framework": result.framework,
        "layers": {
            layer: [
                {
                    "name": c.name,
                    "file_path": c.file_path,
                    "responsibility": c.responsibility,
                    "module": c.module
                }
                for c in components
            ]
            for layer, components in result.layers.items()
            if components
        },
        "modules": [
            {
                "name": m.name,
                "path": m.path,
                "component_count": len(m.components)
            }
            for m in result.modules
        ],
        "cross_cutting_concerns": [
            {
                "name": c.name,
                "implementation": c.implementation,
                "file_path": c.file_path
            }
            for c in result.cross_cutting_concerns
        ],
        "errors": result.errors
    }

    if result.frontend_routes:
        output["frontend"] = {
            "routes": [
                {
                    "path": r.path,
                    "component": r.component,
                    "file_path": r.file_path
                }
                for r in result.frontend_routes
            ],
            "stores": [
                {
                    "name": s.name,
                    "type": s.store_type.value,
                    "file_path": s.file_path
                }
                for s in result.frontend_stores
            ],
            "components": [
                {
                    "name": c.name,
                    "group": c.group,
                    "file_path": c.file_path
                }
                for c in result.frontend_components
            ]
        }

    if include_diagram:
        output["mermaid_diagram"] = generate_mermaid_diagram(result)

    return json.dumps(output, indent=2)


def output_markdown(result: BreakdownResult, include_diagram: bool = False) -> str:
    """Format results as Markdown."""
    lines = [f"# Component Breakdown Report\n"]
    lines.append(f"**Project:** `{result.project_path}`\n")
    lines.append(f"**Project Name:** {result.project_name}\n")
    lines.append(f"**Framework:** {result.framework}\n")

    if result.errors:
        lines.append("## Errors\n")
        for error in result.errors:
            lines.append(f"- {error}\n")
        lines.append("")

    # Architectural Layers
    lines.append("## Architectural Layers\n")

    layer_order = [Layer.ROUTER, Layer.CONTROLLER, Layer.SERVICE, Layer.REPOSITORY, Layer.MODEL, Layer.MIDDLEWARE, Layer.SCHEMA, Layer.UTILITY]

    for layer in layer_order:
        components = result.layers.get(layer.value, [])
        if components:
            lines.append(f"### {layer.value} Layer\n")
            lines.append("| Component | File Path | Responsibility |")
            lines.append("|-----------|-----------|----------------|")

            # Deduplicate by name
            seen = set()
            for c in components:
                if c.name not in seen:
                    seen.add(c.name)
                    resp = c.responsibility[:50] + "..." if len(c.responsibility) > 50 else c.responsibility
                    lines.append(f"| {c.name} | `{c.file_path}` | {resp or '-'} |")
            lines.append("")

    # Modules/Domains
    if result.modules:
        lines.append("## Modules/Domains\n")
        lines.append("| Module | Path | Components |")
        lines.append("|--------|------|------------|")
        for m in sorted(result.modules, key=lambda x: x.name):
            unique_layers = list(set(c.layer.value for c in m.components))
            layers_str = ", ".join(unique_layers[:3])
            lines.append(f"| {m.name} | `{m.path}` | {layers_str} |")
        lines.append("")

    # Component Registry
    lines.append("## Component Registry\n")
    lines.append("| Component | Layer | File Path | Responsibility |")
    lines.append("|-----------|-------|-----------|----------------|")

    all_components = []
    for layer in layer_order:
        for c in result.layers.get(layer.value, []):
            all_components.append(c)

    seen = set()
    for c in all_components[:50]:  # Limit output
        if c.name not in seen:
            seen.add(c.name)
            resp = c.responsibility[:40] + "..." if len(c.responsibility) > 40 else c.responsibility
            lines.append(f"| {c.name} | {c.layer.value} | `{c.file_path}` | {resp or '-'} |")
    lines.append("")

    # Cross-Cutting Concerns
    if result.cross_cutting_concerns:
        lines.append("## Cross-Cutting Concerns\n")
        lines.append("| Concern | Implementation | File Path |")
        lines.append("|---------|----------------|-----------|")
        for c in result.cross_cutting_concerns:
            lines.append(f"| {c.name} | {c.implementation} | `{c.file_path}` |")
        lines.append("")

    # Frontend Analysis
    if result.frontend_routes:
        lines.append("## Frontend Architecture\n")

        if result.frontend_routes:
            lines.append("### Routing Structure\n")
            lines.append("| Route | Component | File |")
            lines.append("|-------|-----------|------|")
            for r in result.frontend_routes[:20]:
                lines.append(f"| {r.path} | {r.component} | `{r.file_path}` |")
            lines.append("")

        if result.frontend_stores:
            lines.append("### State Management\n")
            lines.append("| Store | Type | File |")
            lines.append("|-------|------|------|")
            for s in result.frontend_stores:
                lines.append(f"| {s.name} | {s.store_type.value} | `{s.file_path}` |")
            lines.append("")

        if result.frontend_components:
            lines.append("### Component Groups\n")
            groups: dict[str, list] = {}
            for c in result.frontend_components:
                if c.group not in groups:
                    groups[c.group] = []
                groups[c.group].append(c.name)

            lines.append("| Group | Components |")
            lines.append("|-------|------------|")
            for group, comps in sorted(groups.items()):
                comps_str = ", ".join(comps[:5])
                if len(comps) > 5:
                    comps_str += f" (+{len(comps) - 5} more)"
                lines.append(f"| {group} | {comps_str} |")
            lines.append("")

    # Mermaid diagram
    if include_diagram:
        lines.append("## C4 Component Diagram\n")
        lines.append(generate_mermaid_diagram(result))
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Break down components in a codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --format markdown
  %(prog)s /path/to/project --format markdown --diagram --frontend
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
        help="Include Mermaid C4Component diagram"
    )

    parser.add_argument(
        "--frontend",
        action="store_true",
        help="Include frontend analysis"
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
            result = analyze_project(args.project_path, include_frontend=args.frontend)
        else:
            result = analyze_project_chunked(
                args.project_path,
                include_frontend=args.frontend,
                chunk_size=args.chunk_size,
                resume=args.resume,
                force=args.force,
                show_progress=args.progress,
                quiet=args.quiet
            )
    else:
        result = analyze_project(args.project_path, include_frontend=args.frontend)

    # Output results
    if args.format == "json":
        print(output_json(result, include_diagram=args.diagram))
    else:
        print(output_markdown(result, include_diagram=args.diagram))

    # Return appropriate exit code
    has_critical_errors = len(result.errors) > 0 and not any(result.layers.values())
    sys.exit(1 if has_critical_errors else 0)


if __name__ == "__main__":
    main()
