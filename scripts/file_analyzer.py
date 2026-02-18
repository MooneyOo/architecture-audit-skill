#!/usr/bin/env python3
"""
File Analyzer Script

Performs per-file analysis of entire project to build comprehensive component registry.
Classifies files, extracts exports, parses docstrings, and tracks dependencies.

Usage:
    python file_analyzer.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: json)
    --output FILE             Output file path
    --include PATTERN         Include files matching pattern
    --exclude PATTERN         Exclude files matching pattern
    --category CAT            Analyze only specific category
    --chunk-size N            Process in chunks of N files
    --progress                Show progress bar
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Generator


class FileCategory(Enum):
    CONTROLLER = "controller"
    SERVICE = "service"
    REPOSITORY = "repository"
    MODEL = "model"
    MIDDLEWARE = "middleware"
    UTIL = "util"
    CONFIG = "config"
    TEST = "test"
    FRONTEND = "frontend"
    SCHEMA = "schema"
    UNKNOWN = "unknown"


class Language(Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    VUE = "vue"
    SVELTE = "svelte"
    UNKNOWN = "unknown"


@dataclass
class Export:
    """Represents an exported symbol from a file."""
    name: str
    type: str  # class|function|constant|interface|type
    line: int
    description: str = ""
    signature: str = ""


@dataclass
class Parameter:
    """Represents a function parameter."""
    name: str
    type: str = ""
    default: Optional[str] = None


@dataclass
class ClassInfo:
    """Detailed class information."""
    name: str
    bases: list[str] = field(default_factory=list)
    methods: list[dict] = field(default_factory=list)
    description: str = ""
    line: int = 0


@dataclass
class FunctionInfo:
    """Detailed function information."""
    name: str
    parameters: list[Parameter] = field(default_factory=list)
    return_type: str = ""
    description: str = ""
    line: int = 0
    is_async: bool = False


@dataclass
class FileAnalysis:
    """Complete analysis of a single file."""
    path: str
    category: str
    language: str
    exports: list[Export] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    description: str = ""
    loc: int = 0
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Complete analysis result for a project."""
    project_path: str
    total_files: int = 0
    files_by_category: dict[str, list[FileAnalysis]] = field(default_factory=dict)
    files: list[FileAnalysis] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Directories to skip during traversal
SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", "venv", ".venv", "env", ".env",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    "migrations", ".mypy_cache", "egg-info", "__pypackages__"
}

# File patterns to skip
SKIP_PATTERNS = {
    "*.pyc", "*.pyo", "*.so", "*.dll", "*.dylib", "*.exe",
    "*.min.js", "*.min.css", "*.map", "*.lock", "*.log"
}

# Category detection patterns
CATEGORY_PATTERNS = {
    FileCategory.CONTROLLER: {
        "dirs": ["controllers", "controller", "handlers", "handler", "views"],
        "files": ["*controller*", "*router*", "*handler*", "*view*"],
    },
    FileCategory.SERVICE: {
        "dirs": ["services", "service", "usecases", "usecase", "domain", "business"],
        "files": ["*service*", "*usecase*"],
    },
    FileCategory.REPOSITORY: {
        "dirs": ["repositories", "repository", "dao", "data", "repos", "store"],
        "files": ["*repository*", "*repo*", "*dao*", "*crud*", "*store*"],
    },
    FileCategory.MODEL: {
        "dirs": ["models", "model", "entities", "entity"],
        "files": ["*model*", "*entity*"],
    },
    FileCategory.MIDDLEWARE: {
        "dirs": ["middleware", "middlewares", "interceptors", "interceptor", "guards"],
        "files": ["*middleware*", "*interceptor*", "*guard*"],
    },
    FileCategory.UTIL: {
        "dirs": ["utils", "util", "lib", "libs", "helpers", "helper", "common"],
        "files": ["*util*", "*helper*", "*lib*"],
    },
    FileCategory.CONFIG: {
        "dirs": ["config", "configs", "settings"],
        "files": ["*config*", "*settings*", ".env*"],
    },
    FileCategory.TEST: {
        "dirs": ["tests", "test", "__tests__", "spec", "specs"],
        "files": ["*test*", "*spec*"],
    },
    FileCategory.FRONTEND: {
        "dirs": ["components", "pages", "layouts", "app"],
        "files": ["*.tsx", "*.jsx", "*.vue", "*.svelte", "*.component.*"],
    },
    FileCategory.SCHEMA: {
        "dirs": ["schemas", "dto", "dtos", "types"],
        "files": ["*schema*", "*dto*", "*types*"],
    },
}


def detect_language(file_path: Path) -> Language:
    """Detect the programming language from file extension."""
    suffix = file_path.suffix.lower()
    if suffix == ".py":
        return Language.PYTHON
    elif suffix == ".ts":
        return Language.TYPESCRIPT
    elif suffix == ".js":
        return Language.JAVASCRIPT
    elif suffix == ".vue":
        return Language.VUE
    elif suffix == ".svelte":
        return Language.SVELTE
    return Language.UNKNOWN


def detect_category(file_path: Path, project_root: Path) -> FileCategory:
    """Detect the file category from path and filename patterns."""
    rel_path = file_path.relative_to(project_root)
    path_str = str(rel_path).lower()
    file_name = file_path.name.lower()
    file_stem = file_path.stem.lower()

    # Check each category's patterns
    for category, patterns in CATEGORY_PATTERNS.items():
        # Check directory patterns
        for dir_pattern in patterns["dirs"]:
            if f"/{dir_pattern}/" in f"/{path_str}/" or f"\\{dir_pattern}\\" in f"\\{path_str}\\":
                return category

        # Check file patterns
        for file_pattern in patterns["files"]:
            if fnmatch.fnmatch(file_name, file_pattern) or fnmatch.fnmatch(file_stem, file_pattern):
                return category

    # Check by extension for frontend
    if file_path.suffix.lower() in [".tsx", ".jsx", ".vue", ".svelte"]:
        return FileCategory.FRONTEND

    return FileCategory.UNKNOWN


def should_skip_dir(dir_name: str) -> bool:
    """Check if directory should be skipped."""
    return dir_name.lower() in SKIP_DIRS or dir_name.startswith(".")


def should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped."""
    file_name = file_path.name.lower()
    for pattern in SKIP_PATTERNS:
        if fnmatch.fnmatch(file_name, pattern.lower()):
            return True
    return False


def collect_source_files(project_path: Path,
                         include_patterns: list[str] = None,
                         exclude_patterns: list[str] = None,
                         category_filter: str = None) -> Generator[Path, None, None]:
    """Recursively collect source files for analysis."""
    include_patterns = include_patterns or []
    exclude_patterns = exclude_patterns or []

    source_extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte"}

    for root, dirs, files in os.walk(project_path):
        # Filter out skip directories in-place
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]

        for file_name in files:
            file_path = Path(root) / file_name

            # Skip certain files
            if should_skip_file(file_path):
                continue

            # Check extension
            if file_path.suffix.lower() not in source_extensions:
                continue

            # Check include patterns
            if include_patterns:
                matches_include = any(
                    fnmatch.fnmatch(str(file_path), pattern) or
                    fnmatch.fnmatch(file_name, pattern)
                    for pattern in include_patterns
                )
                if not matches_include:
                    continue

            # Check exclude patterns
            if exclude_patterns:
                matches_exclude = any(
                    fnmatch.fnmatch(str(file_path), pattern) or
                    fnmatch.fnmatch(file_name, pattern)
                    for pattern in exclude_patterns
                )
                if matches_exclude:
                    continue

            # Category filter
            if category_filter:
                category = detect_category(file_path, project_path)
                if category.value != category_filter.lower():
                    continue

            yield file_path


# =============================================================================
# Python Parsing
# =============================================================================

def extract_python_docstring(content: str) -> tuple[str, str]:
    """Extract module-level and first meaningful docstring."""
    # Module docstring
    module_doc = ""
    match = re.search(r'^("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', content)
    if match:
        module_doc = match.group(1).strip('"\'').strip()
        first_line = module_doc.split('\n')[0].strip()
        return first_line[:150], module_doc

    return "", ""


def extract_python_classes(content: str) -> list[ClassInfo]:
    """Extract class definitions from Python code."""
    classes = []

    # Pattern for class with optional bases
    class_pattern = r'^class\s+(\w+)(?:\(([^)]*)\))?:\s*(?:("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'))?'

    for match in re.finditer(class_pattern, content, re.MULTILINE):
        class_name = match.group(1)
        bases_str = match.group(2) or ""
        docstring = match.group(3) or ""

        # Parse bases
        bases = [b.strip() for b in bases_str.split(",") if b.strip()]

        # Clean docstring
        description = docstring.strip('"\'').strip()
        if description:
            description = description.split('\n')[0].strip()

        classes.append(ClassInfo(
            name=class_name,
            bases=bases,
            description=description[:150] if description else "",
            line=content[:match.start()].count('\n') + 1
        ))

    return classes


def extract_python_functions(content: str) -> list[FunctionInfo]:
    """Extract top-level function definitions from Python code."""
    functions = []

    # Pattern for function with optional type hints
    func_pattern = r'^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^:]+))?:\s*(?:("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'))?'

    for match in re.finditer(func_pattern, content, re.MULTILINE):
        func_name = match.group(1)
        params_str = match.group(2) or ""
        return_type = (match.group(3) or "").strip()
        docstring = match.group(4) or ""
        is_async = "async" in match.group(0)[:20]

        # Parse parameters
        parameters = parse_python_params(params_str)

        # Clean docstring
        description = docstring.strip('"\'').strip()
        if description:
            description = description.split('\n')[0].strip()

        functions.append(FunctionInfo(
            name=func_name,
            parameters=parameters,
            return_type=return_type,
            description=description[:150] if description else "",
            line=content[:match.start()].count('\n') + 1,
            is_async=is_async
        ))

    return functions


def parse_python_params(params_str: str) -> list[Parameter]:
    """Parse Python function parameters."""
    parameters = []

    if not params_str.strip():
        return parameters

    # Split by comma, handling nested brackets
    depth = 0
    current = ""
    parts = []

    for char in params_str:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        current += char

    if current.strip():
        parts.append(current.strip())

    for part in parts:
        if not part or part == "self" or part == "cls":
            continue

        # Handle *args and **kwargs
        if part.startswith("*"):
            name = part.replace("*", "").split(":")[0].split("=")[0].strip()
            parameters.append(Parameter(name=f"*{name}", type="any"))
            continue

        # Parse name, type, default
        param = parse_single_python_param(part)
        if param:
            parameters.append(param)

    return parameters


def parse_single_python_param(part: str) -> Optional[Parameter]:
    """Parse a single Python parameter."""
    default = None

    # Check for default value
    if "=" in part:
        type_part, default = part.split("=", 1)
        default = default.strip()
        part = type_part

    # Check for type annotation
    if ":" in part:
        name, type_hint = part.split(":", 1)
        name = name.strip()
        type_hint = type_hint.strip()
    else:
        name = part.strip()
        type_hint = ""

    if not name:
        return None

    return Parameter(name=name, type=type_hint, default=default)


def extract_python_imports(content: str) -> tuple[list[str], list[str]]:
    """Extract imports and dependencies from Python code."""
    imports = []
    dependencies = []

    # Import patterns
    patterns = [
        r'^import\s+([\w.]+)',
        r'^from\s+([\w.]+)\s+import',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content, re.MULTILINE):
            module = match.group(1)
            imports.append(module)

            # Get top-level module for dependency
            top_level = module.split(".")[0]
            if top_level not in dependencies:
                dependencies.append(top_level)

    return imports, dependencies


def extract_python_exports(content: str, classes: list[ClassInfo], functions: list[FunctionInfo]) -> list[Export]:
    """Build exports list from classes and functions."""
    exports = []

    for cls in classes:
        signature = f"class {cls.name}"
        if cls.bases:
            signature += f"({', '.join(cls.bases)})"
        exports.append(Export(
            name=cls.name,
            type="class",
            line=cls.line,
            description=cls.description,
            signature=signature
        ))

    for func in functions:
        params_str = ", ".join(
            f"{p.name}" + (f": {p.type}" if p.type else "") + (f" = {p.default}" if p.default else "")
            for p in func.parameters
        )
        signature = f"{'async ' if func.is_async else ''}def {func.name}({params_str})"
        if func.return_type:
            signature += f" -> {func.return_type}"
        exports.append(Export(
            name=func.name,
            type="function",
            line=func.line,
            description=func.description,
            signature=signature
        ))

    # Also check for constants (ALL_CAPS at module level)
    const_pattern = r'^([A-Z_][A-Z0-9_]*)\s*=\s*'
    for match in re.finditer(const_pattern, content, re.MULTILINE):
        const_name = match.group(1)
        if not any(e.name == const_name for e in exports):
            exports.append(Export(
                name=const_name,
                type="constant",
                line=content[:match.start()].count('\n') + 1,
                signature=f"{const_name} = ..."
            ))

    return exports


def analyze_python_file(file_path: Path, project_root: Path) -> FileAnalysis:
    """Perform complete analysis of a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return FileAnalysis(
            path=str(file_path.relative_to(project_root)),
            category=FileCategory.UNKNOWN.value,
            language=Language.PYTHON.value,
            errors=[str(e)]
        )

    # Extract all information
    description, full_doc = extract_python_docstring(content)
    classes = extract_python_classes(content)
    functions = extract_python_functions(content)
    imports, dependencies = extract_python_imports(content)
    exports = extract_python_exports(content, classes, functions)

    return FileAnalysis(
        path=str(file_path.relative_to(project_root)),
        category=detect_category(file_path, project_root).value,
        language=Language.PYTHON.value,
        exports=exports,
        imports=imports,
        dependencies=dependencies,
        description=description,
        loc=len(content.splitlines()),
        classes=classes,
        functions=functions
    )


# =============================================================================
# TypeScript/JavaScript Parsing
# =============================================================================

def extract_typescript_docstring(content: str, position: int) -> str:
    """Extract JSDoc/TSDoc comment before a position."""
    # Look backwards for comment
    before = content[:position].rstrip()

    # Check for multi-line comment
    if before.endswith("*/"):
        end = before.rfind("*/")
        start = before.rfind("/**", 0, end)
        if start != -1:
            comment = before[start+3:end].strip()
            # Clean up comment
            lines = [l.strip().lstrip("* ").strip() for l in comment.split('\n')]
            return lines[0] if lines else ""

    # Check for single-line comment
    lines = before.split('\n')
    if lines:
        last_line = lines[-1].strip()
        if last_line.startswith("//"):
            return last_line[2:].strip()

    return ""


def extract_typescript_classes(content: str) -> list[ClassInfo]:
    """Extract class definitions from TypeScript/JavaScript code."""
    classes = []

    # Pattern for class with extends/implements
    class_pattern = r'(?:/\*\*[\s\S]*?\*/\s*)?(?:export\s+(?:default\s+)?)?class\s+(\w+)(?:\s+extends\s+(\w+(?:<[^>]+>)?))?(?:\s+implements\s+([^{]+))?'

    for match in re.finditer(class_pattern, content):
        class_name = match.group(1)
        extends = match.group(2) or ""
        implements = match.group(3) or ""

        # Build bases list
        bases = []
        if extends:
            bases.append(extends.strip())
        if implements:
            bases.extend([i.strip() for i in implements.split(",") if i.strip()])

        # Get description from JSDoc
        description = extract_typescript_docstring(content, match.start())

        classes.append(ClassInfo(
            name=class_name,
            bases=bases,
            description=description[:150] if description else "",
            line=content[:match.start()].count('\n') + 1
        ))

    return classes


def extract_typescript_functions(content: str) -> list[FunctionInfo]:
    """Extract function definitions from TypeScript/JavaScript code."""
    functions = []

    # Pattern for exported functions
    func_patterns = [
        # Regular function
        r'(?:/\*\*[\s\S]*?\*/\s*)?(?:export\s+(?:async\s+)?)?function\s+(\w+)\s*(?:<[^>]+>)?\s*\(([^)]*)\)(?:\s*:\s*([^\{=]+))?',
        # Arrow function
        r'(?:/\*\*[\s\S]*?\*/\s*)?(?:export\s+)?(?:async\s+)?(?:const|let)\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-z_]\w*)\s*(?::\s*[^=]+)?\s*=>',
    ]

    for pattern in func_patterns:
        for match in re.finditer(pattern, content):
            func_name = match.group(1)
            params_str = match.group(2) if len(match.groups()) > 1 else ""
            return_type = match.group(3).strip() if len(match.groups()) > 2 and match.group(3) else ""
            is_async = "async" in match.group(0)[:30]

            # Parse parameters
            parameters = parse_typescript_params(params_str or "")

            # Get description
            description = extract_typescript_docstring(content, match.start())

            functions.append(FunctionInfo(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                description=description[:150] if description else "",
                line=content[:match.start()].count('\n') + 1,
                is_async=is_async
            ))

    return functions


def parse_typescript_params(params_str: str) -> list[Parameter]:
    """Parse TypeScript function parameters."""
    parameters = []

    if not params_str.strip():
        return parameters

    # Split by comma, handling nested brackets
    depth = 0
    current = ""
    parts = []

    for char in params_str:
        if char in "([{<":
            depth += 1
        elif char in ")]}>":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        current += char

    if current.strip():
        parts.append(current.strip())

    for part in parts:
        if not part:
            continue

        param = parse_single_typescript_param(part)
        if param:
            parameters.append(param)

    return parameters


def parse_single_typescript_param(part: str) -> Optional[Parameter]:
    """Parse a single TypeScript parameter."""
    part = part.strip()
    if not part:
        return None

    # Handle destructuring
    if part.startswith("{") or part.startswith("["):
        return Parameter(name=part, type="destructured")

    # Handle rest parameters
    is_rest = part.startswith("...")
    if is_rest:
        part = part[3:]

    default = None

    # Check for default value
    if "=" in part and not ":" in part.split("=")[0]:
        name_part, default = part.split("=", 1)
        default = default.strip()
        part = name_part

    # Check for type annotation
    if ":" in part:
        # Handle optional marker
        name, type_hint = part.split(":", 1)
        name = name.strip().rstrip("?")
        type_hint = type_hint.strip()
    else:
        name = part.strip().rstrip("?")
        type_hint = ""

    if not name:
        return None

    if is_rest:
        name = f"...{name}"

    return Parameter(name=name, type=type_hint, default=default)


def extract_typescript_imports(content: str) -> tuple[list[str], list[str]]:
    """Extract imports and dependencies from TypeScript/JavaScript code."""
    imports = []
    dependencies = []

    # Import patterns
    patterns = [
        r'import\s+(?:\{[^}]+\}|\*\s+as\s+\w+|\w+)\s+from\s+["\']([^"\']+)["\']',
        r'import\s+["\']([^"\']+)["\']',
        r'require\s*\(\s*["\']([^"\']+)["\']\s*\)',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content):
            module = match.group(1)
            imports.append(module)

            # Get dependency name (not path)
            if module.startswith(".") or module.startswith("/"):
                continue

            dep = module.split("/")[0]
            if dep.startswith("@"):
                parts = module.split("/", 2)
                dep = "/".join(parts[:2]) if len(parts) > 1 else dep

            if dep not in dependencies:
                dependencies.append(dep)

    return imports, dependencies


def extract_typescript_exports(content: str, classes: list[ClassInfo], functions: list[FunctionInfo]) -> list[Export]:
    """Build exports list from classes, functions, interfaces, and types."""
    exports = []

    # Add classes
    for cls in classes:
        signature = f"class {cls.name}"
        if cls.bases:
            signature += f" extends {cls.bases[0]}"
        exports.append(Export(
            name=cls.name,
            type="class",
            line=cls.line,
            description=cls.description,
            signature=signature
        ))

    # Add functions
    for func in functions:
        params_str = ", ".join(
            f"{p.name}" + (f": {p.type}" if p.type else "") + (f" = {p.default}" if p.default else "")
            for p in func.parameters
        )
        signature = f"{'async ' if func.is_async else ''}function {func.name}({params_str})"
        if func.return_type:
            signature += f": {func.return_type}"
        exports.append(Export(
            name=func.name,
            type="function",
            line=func.line,
            description=func.description,
            signature=signature
        ))

    # Extract interfaces
    interface_pattern = r'(?:/\*\*[\s\S]*?\*/\s*)?(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+(\w+))?'
    for match in re.finditer(interface_pattern, content):
        interface_name = match.group(1)
        extends = match.group(2) or ""
        description = extract_typescript_docstring(content, match.start())

        exports.append(Export(
            name=interface_name,
            type="interface",
            line=content[:match.start()].count('\n') + 1,
            description=description[:150] if description else "",
            signature=f"interface {interface_name}" + (f" extends {extends}" if extends else "")
        ))

    # Extract types
    type_pattern = r'(?:/\*\*[\s\S]*?\*/\s*)?(?:export\s+)?type\s+(\w+)\s*='
    for match in re.finditer(type_pattern, content):
        type_name = match.group(1)
        description = extract_typescript_docstring(content, match.start())

        exports.append(Export(
            name=type_name,
            type="type",
            line=content[:match.start()].count('\n') + 1,
            description=description[:150] if description else "",
            signature=f"type {type_name} = ..."
        ))

    # Extract constants
    const_pattern = r'(?:/\*\*[\s\S]*?\*/\s*)?(?:export\s+)?(?:const|let)\s+(\w+)\s*(?::\s*[^=]+)?\s*='
    for match in re.finditer(const_pattern, content):
        const_name = match.group(1)
        # Skip if already added as function (arrow function)
        if any(e.name == const_name for e in exports):
            continue

        description = extract_typescript_docstring(content, match.start())
        exports.append(Export(
            name=const_name,
            type="constant",
            line=content[:match.start()].count('\n') + 1,
            description=description[:150] if description else "",
            signature=f"const {const_name} = ..."
        ))

    return exports


def analyze_typescript_file(file_path: Path, project_root: Path) -> FileAnalysis:
    """Perform complete analysis of a TypeScript/JavaScript file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return FileAnalysis(
            path=str(file_path.relative_to(project_root)),
            category=FileCategory.UNKNOWN.value,
            language=Language.TYPESCRIPT.value,
            errors=[str(e)]
        )

    # Determine language
    language = Language.TYPESCRIPT if file_path.suffix == ".ts" else Language.JAVASCRIPT

    # Extract all information
    classes = extract_typescript_classes(content)
    functions = extract_typescript_functions(content)
    imports, dependencies = extract_typescript_imports(content)
    exports = extract_typescript_exports(content, classes, functions)

    # Get file description from first JSDoc comment
    description = ""
    first_jsdoc = re.search(r'/\*\*[\s\S]*?\*/', content)
    if first_jsdoc:
        desc_match = re.search(r'/\*\*\s*\n?\s*\*\s*(.+)', first_jsdoc.group(0))
        if desc_match:
            description = desc_match.group(1).strip()[:150]

    return FileAnalysis(
        path=str(file_path.relative_to(project_root)),
        category=detect_category(file_path, project_root).value,
        language=language.value,
        exports=exports,
        imports=imports,
        dependencies=dependencies,
        description=description,
        loc=len(content.splitlines()),
        classes=classes,
        functions=functions
    )


# =============================================================================
# Vue Parsing
# =============================================================================

def analyze_vue_file(file_path: Path, project_root: Path) -> FileAnalysis:
    """Perform analysis of a Vue single-file component."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return FileAnalysis(
            path=str(file_path.relative_to(project_root)),
            category=FileCategory.FRONTEND.value,
            language=Language.VUE.value,
            errors=[str(e)]
        )

    exports = []
    imports = []
    dependencies = []
    description = ""

    # Extract script section
    script_match = re.search(r'<script[^>]*>([\s\S]*?)</script>', content)
    if script_match:
        script_content = script_match.group(1)

        # Get imports
        imports, dependencies = extract_typescript_imports(script_content)

        # Get component name
        name_match = re.search(r'name\s*:\s*["\'](\w+)["\']', script_content)
        if name_match:
            exports.append(Export(
                name=name_match.group(1),
                type="component",
                line=1,
                description="Vue component"
            ))

    # Get description from first comment
    desc_match = re.search(r'<!--\s*(.+?)\s*-->', content)
    if desc_match:
        description = desc_match.group(1).strip()[:150]

    # If no exports, use filename as component name
    if not exports:
        exports.append(Export(
            name=file_path.stem,
            type="component",
            line=1,
            description="Vue component"
        ))

    return FileAnalysis(
        path=str(file_path.relative_to(project_root)),
        category=FileCategory.FRONTEND.value,
        language=Language.VUE.value,
        exports=exports,
        imports=imports,
        dependencies=dependencies,
        description=description,
        loc=len(content.splitlines())
    )


# =============================================================================
# Main Analysis Functions
# =============================================================================

def analyze_file(file_path: Path, project_root: Path) -> FileAnalysis:
    """Analyze a single file based on its language."""
    suffix = file_path.suffix.lower()

    if suffix == ".py":
        return analyze_python_file(file_path, project_root)
    elif suffix in [".ts", ".tsx", ".js", ".jsx"]:
        return analyze_typescript_file(file_path, project_root)
    elif suffix == ".vue":
        return analyze_vue_file(file_path, project_root)
    elif suffix == ".svelte":
        # Basic Svelte support
        return analyze_svelte_file(file_path, project_root)
    else:
        return FileAnalysis(
            path=str(file_path.relative_to(project_root)),
            category=FileCategory.UNKNOWN.value,
            language=Language.UNKNOWN.value
        )


def analyze_svelte_file(file_path: Path, project_root: Path) -> FileAnalysis:
    """Basic analysis of a Svelte component."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return FileAnalysis(
            path=str(file_path.relative_to(project_root)),
            category=FileCategory.FRONTEND.value,
            language=Language.SVELTE.value,
            errors=[str(e)]
        )

    exports = [Export(
        name=file_path.stem,
        type="component",
        line=1,
        description="Svelte component"
    )]

    return FileAnalysis(
        path=str(file_path.relative_to(project_root)),
        category=FileCategory.FRONTEND.value,
        language=Language.SVELTE.value,
        exports=exports,
        loc=len(content.splitlines())
    )


def analyze_project(project_path: Path,
                    include_patterns: list[str] = None,
                    exclude_patterns: list[str] = None,
                    category_filter: str = None,
                    chunk_size: int = 0,
                    show_progress: bool = False) -> AnalysisResult:
    """Analyze entire project."""
    result = AnalysisResult(project_path=str(project_path))

    # Collect files
    files = list(collect_source_files(
        project_path,
        include_patterns,
        exclude_patterns,
        category_filter
    ))
    result.total_files = len(files)

    # Process files
    if show_progress:
        try:
            from tqdm import tqdm
            files_iter = tqdm(files, desc="Analyzing files", unit="file")
        except ImportError:
            files_iter = files
            print(f"Analyzing {len(files)} files...")
    else:
        files_iter = files

    for file_path in files_iter:
        try:
            analysis = analyze_file(file_path, project_path)
            result.files.append(analysis)

            # Group by category
            category = analysis.category
            if category not in result.files_by_category:
                result.files_by_category[category] = []
            result.files_by_category[category].append(analysis)

        except Exception as e:
            result.errors.append(f"Error analyzing {file_path}: {str(e)}")

    return result


def output_json(result: AnalysisResult) -> str:
    """Format results as JSON."""
    output = {
        "project_path": result.project_path,
        "total_files": result.total_files,
        "files_by_category": {
            cat: [asdict(f) for f in files]
            for cat, files in result.files_by_category.items()
        },
        "files": [asdict(f) for f in result.files],
        "errors": result.errors
    }
    return json.dumps(output, indent=2, default=str)


def output_markdown(result: AnalysisResult) -> str:
    """Format results as Markdown."""
    lines = [f"# File Analysis Report\n"]
    lines.append(f"**Project:** `{result.project_path}`\n")
    lines.append(f"**Total Files:** {result.total_files}\n")

    # Category summary
    lines.append("## Files by Category\n")
    lines.append("| Category | File Count |")
    lines.append("|----------|------------|")
    for category, files in sorted(result.files_by_category.items()):
        lines.append(f"| {category} | {len(files)} |")
    lines.append("")

    # Details per category
    for category, files in sorted(result.files_by_category.items()):
        lines.append(f"## {category.title()} Files\n")

        for f in files[:50]:  # Limit output
            lines.append(f"### {f.path}\n")
            lines.append(f"- **Language:** {f.language}")
            lines.append(f"- **LOC:** {f.loc}")
            if f.description:
                lines.append(f"- **Description:** {f.description}")

            if f.exports:
                lines.append("\n**Exports:**\n")
                lines.append("| Name | Type | Line | Description |")
                lines.append("|------|------|------|-------------|")
                for e in f.exports[:10]:
                    lines.append(f"| {e.name} | {e.type} | {e.line} | {e.description[:50] or '-'} |")
            lines.append("")

    if result.errors:
        lines.append("## Errors\n")
        for error in result.errors:
            lines.append(f"- {error}\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze files in a project for component discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --format markdown --output analysis.md
  %(prog)s /path/to/project --category controller --format json
  %(prog)s /path/to/project --include "src/**/*.py" --progress
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
        "--output", "-o",
        help="Output file path (default: stdout)"
    )

    parser.add_argument(
        "--include",
        action="append",
        help="Include files matching pattern (can be used multiple times)"
    )

    parser.add_argument(
        "--exclude",
        action="append",
        help="Exclude files matching pattern (can be used multiple times)"
    )

    parser.add_argument(
        "--category",
        choices=[c.value for c in FileCategory],
        help="Analyze only specific category"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=0,
        help="Process in chunks of N files for large projects"
    )

    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bar"
    )

    args = parser.parse_args()

    # Validate project path
    project_path = Path(args.project_path)
    if not project_path.exists():
        print(f"Error: Project path does not exist: {args.project_path}", file=sys.stderr)
        sys.exit(1)

    # Analyze project
    result = analyze_project(
        project_path,
        include_patterns=args.include,
        exclude_patterns=args.exclude,
        category_filter=args.category,
        chunk_size=args.chunk_size,
        show_progress=args.progress
    )

    # Format output
    if args.format == "json":
        output = output_json(result)
    else:
        output = output_markdown(result)

    # Write output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Output written to {args.output}")
    else:
        print(output)

    # Exit code
    sys.exit(1 if result.errors else 0)


if __name__ == "__main__":
    main()
