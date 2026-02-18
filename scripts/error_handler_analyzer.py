#!/usr/bin/env python3
"""
Error Handling Analysis Script

Analyzes error handling patterns in a codebase and documents
custom exceptions, global handlers, and error response formats.

Usage:
    python error_handler_analyzer.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: json)
    --help                    Show usage information

Detection capabilities:
    - Custom exception classes and hierarchies
    - Global error handlers (FastAPI, Express, etc.)
    - Error response format patterns
    - Input validation patterns (Pydantic, Zod, etc.)
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CustomException:
    """Represents a custom exception class."""
    name: str
    base_class: str
    file_path: str
    line_number: int
    status_code: int = 500
    description: str = ""


@dataclass
class ErrorHandler:
    """Represents a global error handler."""
    name: str
    file_path: str
    line_number: int
    handles: list[str] = field(default_factory=list)  # Exception types handled
    response_format: str = ""


@dataclass
class ErrorResponseFormat:
    """Represents error response format."""
    fields: list[str] = field(default_factory=list)
    example: str = ""


@dataclass
class ValidationPattern:
    """Represents an input validation pattern."""
    library: str
    file_path: str
    description: str = ""


@dataclass
class ErrorHandlingResult:
    """Result of error handling analysis."""
    project_path: str
    custom_exceptions: list[CustomException] = field(default_factory=list)
    global_handlers: list[ErrorHandler] = field(default_factory=list)
    response_format: Optional[ErrorResponseFormat] = None
    validation_patterns: list[ValidationPattern] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Exception class patterns
EXCEPTION_PATTERNS = {
    'python': [
        # class CustomError(Exception):
        (r'class\s+(\w+Error|\w+Exception)\s*\(\s*(\w+)\s*\):', 'Custom exception'),
        # class Custom(Exception, another):
        (r'class\s+(\w+)\s*\(\s*(\w+Exception|\w+Error)[^)]*\):', 'Exception subclass'),
    ],
    'nodejs': [
        # class CustomError extends Error
        (r'class\s+(\w+Error|\w+Exception)\s+extends\s+(\w+)', 'Custom error'),
        # export class CustomError
        (r'export\s+class\s+(\w+Error)\s+extends', 'Exported error'),
    ],
}

# Global handler patterns
HANDLER_PATTERNS = {
    'python': [
        # FastAPI: @app.exception_handler(CustomException)
        (r'@app\.exception_handler\((\w+)\)', 'FastAPI exception handler'),
        (r'@router\.exception_handler\((\w+)\)', 'Router exception handler'),
        # FastAPI: app.add_exception_handler
        (r'app\.add_exception_handler\((\w+)', 'FastAPI add handler'),
        # Generic function handlers
        (r'def\s+(?:handle_)?(\w+).*?exception', 'Exception handler function'),
    ],
    'nodejs': [
        # Express: app.use(errorHandler)
        (r'app\.use\((\w*[Ee]rror\w*)\)', 'Express error middleware'),
        # NestJS: @Catch(Exception)
        (r'@Catch\((\w+)\)', 'NestJS exception filter'),
        (r'@Catch\(\s*\)', 'NestJS catch-all filter'),
    ],
}

# Response format patterns
RESPONSE_FORMAT_PATTERNS = [
    # JSON response patterns
    (r'JSONResponse\s*\([^)]*content\s*=\s*\{([^}]+)\}', 'JSON response'),
    (r'return\s+(?:Response\()?["\']?\{[^}]*error[^}]*\}', 'JSON error'),
    (r'"error"\s*:\s*["\']', 'Error field'),
    (r'"message"\s*:\s*["\']', 'Message field'),
    (r'"details"\s*:\s*', 'Details field'),
    (r'"code"\s*:\s*["\']', 'Error code field'),
]

# Validation library patterns
VALIDATION_PATTERNS = {
    'python': [
        (r'from pydantic import', 'Pydantic'),
        (r'from pydantic\.v1 import', 'Pydantic v1'),
        (r'class\s+\w+\(BaseModel\):', 'Pydantic model'),
        (r'@validator\(', 'Pydantic validator'),
        (r'@field_validator\(', 'Pydantic v2 validator'),
        (r'from marshmallow import', 'Marshmallow'),
        (r'from cerberus import', 'Cerberus'),
        (r'from voluptuous import', 'Voluptuous'),
    ],
    'nodejs': [
        (r'from ["\']zod["\']', 'Zod'),
        (r'from ["\']yup["\']', 'Yup'),
        (r'from ["\']joi["\']', 'Joi'),
        (r'from ["\']class-validator["\']', 'class-validator'),
        (r'@IsString|@IsEmail|@IsNumber|@MinLength', 'class-validator decorators'),
        (r'express-validator', 'Express Validator'),
        (r'from ["\']ajv["\']', 'AJV'),
    ],
}

# HTTP status code patterns
STATUS_CODE_PATTERNS = [
    (r'status_code\s*=\s*(\d+)', 'Status code assignment'),
    (r'status\s*=\s*(\d+)', 'Status assignment'),
    (r'HTTP_(\d{3})', 'HTTP status constant'),
    (r'return\s+Response\s*\([^)]*status\s*=\s*(\d+)', 'Response status'),
]


def find_custom_exceptions(project_path: Path) -> list[CustomException]:
    """Find custom exception classes in the codebase."""
    exceptions = []

    for ext in ['.py', '.ts', '.js']:
        for file_path in project_path.rglob(f"*{ext}"):
            if any(part in file_path.parts for part in ['node_modules', '__pycache__', 'venv', '.venv', 'dist']):
                continue

            # Focus on exception/error files
            file_name = file_path.name.lower()
            if 'exception' not in file_name and 'error' not in file_name:
                # Also check common directories
                if 'common' not in str(file_path).lower() and 'utils' not in str(file_path).lower():
                    continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')

                relative_path = str(file_path.relative_to(project_path))
                lang = 'python' if ext == '.py' else 'nodejs'

                for pattern, desc in EXCEPTION_PATTERNS.get(lang, []):
                    for match in re.finditer(pattern, content, re.MULTILINE):
                        name = match.group(1)
                        base_class = match.group(2) if len(match.groups()) > 1 else "Exception"

                        line_num = content[:match.start()].count('\n') + 1

                        # Try to find status code in the class
                        status_code = 500
                        class_body_start = match.end()
                        class_body = content[class_body_start:class_body_start + 500]

                        for status_pattern, _ in STATUS_CODE_PATTERNS:
                            status_match = re.search(status_pattern, class_body)
                            if status_match:
                                status_code = int(status_match.group(1))
                                break

                        # Try to find description (docstring or comment)
                        description = ""
                        doc_match = re.search(r'"""([^"]+)"""', class_body)
                        if doc_match:
                            description = doc_match.group(1).strip()
                        else:
                            comment_match = re.search(r'#\s*(.+)$', lines[line_num - 1] if line_num <= len(lines) else "")
                            if comment_match:
                                description = comment_match.group(1).strip()

                        exceptions.append(CustomException(
                            name=name,
                            base_class=base_class,
                            file_path=relative_path,
                            line_number=line_num,
                            status_code=status_code,
                            description=description,
                        ))

            except Exception:
                continue

    # Deduplicate
    seen = set()
    unique = []
    for exc in exceptions:
        if exc.name not in seen:
            seen.add(exc.name)
            unique.append(exc)

    return unique


def find_global_handlers(project_path: Path) -> list[ErrorHandler]:
    """Find global error handlers in the codebase."""
    handlers = []

    for ext in ['.py', '.ts', '.js']:
        for file_path in project_path.rglob(f"*{ext}"):
            if any(part in file_path.parts for part in ['node_modules', '__pycache__', 'venv', '.venv', 'dist']):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                relative_path = str(file_path.relative_to(project_path))
                lang = 'python' if ext == '.py' else 'nodejs'

                for pattern, desc in HANDLER_PATTERNS.get(lang, []):
                    for match in re.finditer(pattern, content, re.MULTILINE):
                        line_num = content[:match.start()].count('\n') + 1
                        name = match.group(1) if match.groups() else "error_handler"

                        # Find what exceptions it handles
                        handles = []
                        if match.groups():
                            handles.append(match.group(1))

                        # Look for response format in handler body
                        handler_body = content[match.start():match.start() + 1000]
                        response_format = ""
                        if 'JSONResponse' in handler_body:
                            response_format = "JSON"
                        elif 'Response' in handler_body:
                            response_format = "Response object"

                        handlers.append(ErrorHandler(
                            name=name,
                            file_path=relative_path,
                            line_number=line_num,
                            handles=handles,
                            response_format=response_format,
                        ))

            except Exception:
                continue

    # Deduplicate
    seen = set()
    unique = []
    for h in handlers:
        key = (h.name, h.file_path)
        if key not in seen:
            seen.add(key)
            unique.append(h)

    return unique


def extract_response_format(project_path: Path, handlers: list[ErrorHandler]) -> Optional[ErrorResponseFormat]:
    """Extract error response format from handlers."""
    fields = set()

    # Look at main application file for error responses
    main_files = [
        project_path / "main.py",
        project_path / "app.py",
        project_path / "src" / "main.py",
        project_path / "src" / "app.py",
    ]

    for main_file in main_files:
        if not main_file.exists():
            continue

        try:
            with open(main_file, 'r') as f:
                content = f.read()

            # Look for response format patterns
            for pattern, _ in RESPONSE_FORMAT_PATTERNS:
                if re.search(pattern, content, re.I):
                    field_match = re.search(r'"(\w+)"\s*:', pattern)
                    if field_match:
                        fields.add(field_match.group(1))

            # Extract common fields
            if '"error"' in content or "'error'" in content:
                fields.add("error")
            if '"message"' in content or "'message'" in content:
                fields.add("message")
            if '"details"' in content or "'details'" in content:
                fields.add("details")
            if '"code"' in content or "'code'" in content:
                fields.add("code")

        except Exception:
            continue

    # Also check handler files
    for handler in handlers:
        handler_file = project_path / handler.file_path
        if handler_file.exists():
            try:
                with open(handler_file, 'r') as f:
                    content = f.read()

                if '"error"' in content or "'error'" in content:
                    fields.add("error")
                if '"message"' in content or "'message'" in content:
                    fields.add("message")
                if '"details"' in content or "'details'" in content:
                    fields.add("details")
                if '"code"' in content or "'code'" in content:
                    fields.add("code")

            except Exception:
                continue

    if fields:
        # Generate example
        example_parts = []
        for field in sorted(fields):
            if field == "error":
                example_parts.append(f'"{field}": "Error type"')
            elif field == "message":
                example_parts.append(f'"{field}": "Human-readable message"')
            elif field == "details":
                example_parts.append(f'"{field}": {{}}')
            elif field == "code":
                example_parts.append(f'"{field}": "ERROR_CODE"')
            else:
                example_parts.append(f'"{field}": "..."')

        return ErrorResponseFormat(
            fields=list(fields),
            example="{\n  " + ",\n  ".join(example_parts) + "\n}"
        )

    return None


def detect_validation_patterns(project_path: Path) -> list[ValidationPattern]:
    """Detect input validation libraries and patterns."""
    patterns = []

    for ext in ['.py', '.ts', '.js']:
        for file_path in project_path.rglob(f"*{ext}"):
            if any(part in file_path.parts for part in ['node_modules', '__pycache__', 'venv', '.venv', 'dist']):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                relative_path = str(file_path.relative_to(project_path))
                lang = 'python' if ext == '.py' else 'nodejs'

                for pattern, library in VALIDATION_PATTERNS.get(lang, []):
                    if re.search(pattern, content):
                        # Check if this library is already detected
                        existing = next((p for p in patterns if p.library == library), None)
                        if not existing:
                            patterns.append(ValidationPattern(
                                library=library,
                                file_path=relative_path,
                                description=f"Uses {library} for input validation"
                            ))

            except Exception:
                continue

    return patterns


def analyze_project(project_path: str) -> ErrorHandlingResult:
    """Analyze a project for error handling patterns."""
    path = Path(project_path)
    result = ErrorHandlingResult(project_path=project_path)

    if not path.exists():
        result.errors.append(f"Project path does not exist: {project_path}")
        return result

    # 1. Find custom exceptions
    result.custom_exceptions = find_custom_exceptions(path)

    # 2. Find global handlers
    result.global_handlers = find_global_handlers(path)

    # 3. Extract response format
    result.response_format = extract_response_format(path, result.global_handlers)

    # 4. Detect validation patterns
    result.validation_patterns = detect_validation_patterns(path)

    return result


def output_json(result: ErrorHandlingResult) -> str:
    """Format result as JSON."""
    output = {
        "project_path": result.project_path,
        "custom_exceptions": [
            {
                "name": e.name,
                "base_class": e.base_class,
                "file_path": e.file_path,
                "line_number": e.line_number,
                "status_code": e.status_code,
                "description": e.description,
            }
            for e in result.custom_exceptions
        ],
        "global_handlers": [
            {
                "name": h.name,
                "file_path": h.file_path,
                "line_number": h.line_number,
                "handles": h.handles,
                "response_format": h.response_format,
            }
            for h in result.global_handlers
        ],
        "response_format": {
            "fields": result.response_format.fields,
            "example": result.response_format.example,
        } if result.response_format else None,
        "validation_patterns": [
            {
                "library": p.library,
                "file_path": p.file_path,
                "description": p.description,
            }
            for p in result.validation_patterns
        ],
        "errors": result.errors,
    }
    return json.dumps(output, indent=2)


def output_markdown(result: ErrorHandlingResult) -> str:
    """Format result as Markdown."""
    lines = ["# Error Handling Analysis Report\n"]
    lines.append(f"**Project:** `{result.project_path}`\n")

    if result.errors and not result.custom_exceptions:
        lines.append("## Errors\n")
        for error in result.errors:
            lines.append(f"- {error}\n")
        lines.append("\n")

    # Custom Exceptions
    if result.custom_exceptions:
        lines.append("## Custom Exceptions\n")
        lines.append("| Exception | Base Class | Status Code | File |")
        lines.append("|-----------|------------|-------------|------|")
        for exc in sorted(result.custom_exceptions, key=lambda x: x.status_code):
            file_ref = f"`{exc.file_path}:{exc.line_number}`"
            lines.append(f"| `{exc.name}` | {exc.base_class} | {exc.status_code} | {file_ref} |")
        lines.append("")

        # Exception hierarchy
        lines.append("### Exception Hierarchy\n")
        lines.append("```")
        # Build hierarchy
        bases = {}
        for exc in result.custom_exceptions:
            if exc.base_class not in bases:
                bases[exc.base_class] = []
            bases[exc.base_class].append(exc.name)

        for base, children in bases.items():
            lines.append(f"{base}")
            for child in children:
                lines.append(f"  └── {child}")
        lines.append("```\n")

    # Global Handlers
    if result.global_handlers:
        lines.append("## Global Error Handlers\n")
        lines.append("| Handler | File | Handles | Format |")
        lines.append("|---------|------|---------|--------|")
        for handler in result.global_handlers:
            file_ref = f"`{handler.file_path}:{handler.line_number}`"
            handles = ", ".join(handler.handles) if handler.handles else "All"
            lines.append(f"| {handler.name} | {file_ref} | {handles} | {handler.response_format or '-'} |")
        lines.append("")

    # Response Format
    if result.response_format:
        lines.append("## Error Response Format\n")
        lines.append(f"**Fields:** {', '.join(result.response_format.fields)}\n")
        lines.append("**Example:**\n")
        lines.append("```json")
        lines.append(result.response_format.example)
        lines.append("```\n")

    # Validation Patterns
    if result.validation_patterns:
        lines.append("## Input Validation\n")
        lines.append("| Library | File | Description |")
        lines.append("|---------|------|-------------|")
        for pattern in result.validation_patterns:
            lines.append(f"| {pattern.library} | `{pattern.file_path}` | {pattern.description} |")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze project error handling patterns",
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
    sys.exit(1 if result.errors and not result.custom_exceptions else 0)


if __name__ == "__main__":
    main()
