#!/usr/bin/env python3
"""
Path Verification Script

Verifies all file paths mentioned in a generated output document actually
exist in the codebase.

Usage:
    python verify_paths.py <document_path> <codebase_path> [options]

Options:
    --strict         Fail on any missing path
    --ignore PATTERN Skip paths matching pattern (can be used multiple times)
    --format FORMAT  Output format (json/text)
    --help           Show usage

Exit Codes:
    0 - All paths verified
    1 - Some paths missing
    2 - Document not found
    3 - Codebase not found
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PathResult:
    """Result of verifying a single path."""
    path: str
    line: int
    status: str  # 'found', 'missing', 'ignored'
    resolved: Optional[str] = None


@dataclass
class VerificationResult:
    """Result of verifying all paths in a document."""
    document: str
    codebase: str
    results: list[PathResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def found(self) -> int:
        return len([r for r in self.results if r.status == 'found'])

    @property
    def missing(self) -> int:
        return len([r for r in self.results if r.status == 'missing'])

    @property
    def ignored(self) -> int:
        return len([r for r in self.results if r.status == 'ignored'])


# Default patterns to ignore
DEFAULT_IGNORE_PATTERNS = [
    r'node_modules/.*',
    r'\.git/.*',
    r'dist/.*',
    r'build/.*',
    r'__pycache__/.*',
    r'\.next/.*',
    r'\.nuxt/.*',
    r'coverage/.*',
    r'\.pytest_cache/.*',
    r'venv/.*',
    r'\.venv/.*',
    r'env/.*',
    r'\.env/.*',
]


def is_likely_file(path: str) -> bool:
    """Determine if a string is likely a file path."""
    # Has common code file extension
    if re.search(r'\.(ts|tsx|js|jsx|py|go|rs|java|rb|php|cs|swift|kt|scala|c|cpp|h|hpp)$', path, re.IGNORECASE):
        return True

    # Has config file extension
    if re.search(r'\.(json|yaml|yml|toml|ini|cfg|conf|xml|env|md)$', path, re.IGNORECASE):
        return True

    # Starts with common source directories
    if any(path.startswith(p) for p in ['src/', 'lib/', 'app/', 'tests/', 'test/', 'backend/', 'frontend/']):
        return True

    # Contains path separators and has extension
    if ('/' in path or '\\' in path) and '.' in path:
        return True

    return False


def should_ignore(path: str, ignore_patterns: list[str]) -> bool:
    """Check if path should be ignored."""
    for pattern in ignore_patterns:
        if re.search(pattern, path):
            return True
    return False


def resolve_path(base_path: Path, file_path: str) -> Optional[str]:
    """Resolve a file path relative to codebase root."""
    # Clean the path
    file_path = file_path.strip()

    # Try exact path first
    full_path = base_path / file_path
    if full_path.exists():
        return str(full_path.resolve())

    # Try common variations
    variations = [
        file_path.lstrip('/'),           # Remove leading slash
        file_path.lstrip('./'),          # Remove ./
        f"src/{file_path.lstrip('/')}",  # Add src prefix
        f"backend/{file_path.lstrip('/')}",  # Add backend prefix
        f"frontend/{file_path.lstrip('/')}",  # Add frontend prefix
    ]

    for variant in variations:
        full_path = base_path / variant
        if full_path.exists():
            return str(full_path.resolve())

    return None


def extract_paths_from_markdown(content: str) -> list[tuple[str, int]]:
    """Extract file paths from markdown content with line numbers."""
    paths = []

    # Pattern for file paths in backticks
    # Matches: `path/to/file.ext` or `./path/to/file.ext`
    backtick_pattern = r'`([^`\s]+\.[a-zA-Z]{1,4})`'

    for line_num, line in enumerate(content.split('\n'), 1):
        # Find all matches in the line
        matches = re.findall(backtick_pattern, line)
        for match in matches:
            # Clean up the path
            path = match.strip()
            if is_likely_file(path):
                paths.append((path, line_num))

    return paths


def verify_paths(
    document_path: str,
    codebase_path: str,
    ignore_patterns: list[str],
    strict: bool = False
) -> VerificationResult:
    """Verify all paths in a document against a codebase."""
    doc_path = Path(document_path)
    base_path = Path(codebase_path)

    result = VerificationResult(
        document=str(doc_path.resolve()),
        codebase=str(base_path.resolve())
    )

    # Check document exists
    if not doc_path.exists():
        print(f"Error: Document not found: {document_path}", file=sys.stderr)
        sys.exit(2)

    # Check codebase exists
    if not base_path.exists():
        print(f"Error: Codebase not found: {codebase_path}", file=sys.stderr)
        sys.exit(3)

    # Read document content
    try:
        content = doc_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading document: {e}", file=sys.stderr)
        sys.exit(2)

    # Extract paths
    paths = extract_paths_from_markdown(content)

    # Track seen paths to avoid duplicates
    seen_paths = set()

    for path, line_num in paths:
        # Skip duplicates
        if path in seen_paths:
            continue
        seen_paths.add(path)

        # Check if should ignore
        if should_ignore(path, ignore_patterns):
            result.results.append(PathResult(
                path=path,
                line=line_num,
                status='ignored'
            ))
            continue

        # Try to resolve path
        resolved = resolve_path(base_path, path)

        if resolved:
            result.results.append(PathResult(
                path=path,
                line=line_num,
                status='found',
                resolved=resolved
            ))
        else:
            result.results.append(PathResult(
                path=path,
                line=line_num,
                status='missing'
            ))

    return result


def output_text(result: VerificationResult) -> str:
    """Format result as human-readable text."""
    lines = []
    lines.append(f"Verifying paths in {Path(result.document).name} against {Path(result.codebase).name}...")
    lines.append("")

    for r in result.results:
        if r.status == 'found':
            lines.append(f"✓ {r.path}")
        elif r.status == 'missing':
            lines.append(f"✗ {r.path} (line {r.line}) - File not found")
        # Ignored paths are not shown in text output

    lines.append("")
    lines.append("Summary:")
    lines.append(f"  Total paths: {result.total}")
    lines.append(f"  Found: {result.found}")
    lines.append(f"  Missing: {result.missing}")

    if result.missing > 0:
        lines.append("")
        lines.append(f"ERROR: {result.missing} missing path(s) found")

    return "\n".join(lines)


def output_json(result: VerificationResult) -> str:
    """Format result as JSON."""
    output = {
        "document": result.document,
        "codebase": result.codebase,
        "summary": {
            "total": result.total,
            "found": result.found,
            "missing": result.missing,
            "ignored": result.ignored
        },
        "results": [
            {
                "path": r.path,
                "line": r.line,
                "status": r.status,
                **({"resolved": r.resolved} if r.resolved else {})
            }
            for r in result.results
        ]
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Verify file paths in a document exist in a codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
    0 - All paths verified
    1 - Some paths missing
    2 - Document not found
    3 - Codebase not found

Examples:
    %(prog)s output.md ./my-project
    %(prog)s output.md ./my-project --strict
    %(prog)s output.md ./my-project --format json
    %(prog)s output.md ./my-project --ignore "vendor/.*" --ignore "legacy/.*"
"""
    )

    parser.add_argument(
        "document_path",
        help="Path to the markdown document to verify"
    )

    parser.add_argument(
        "codebase_path",
        help="Path to the codebase root directory"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any missing path"
    )

    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Regex pattern for paths to ignore (can be used multiple times)"
    )

    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    # Combine default and custom ignore patterns
    ignore_patterns = DEFAULT_IGNORE_PATTERNS + args.ignore

    # Run verification
    result = verify_paths(
        args.document_path,
        args.codebase_path,
        ignore_patterns,
        args.strict
    )

    # Output results
    if args.format == "json":
        print(output_json(result))
    else:
        print(output_text(result))

    # Return appropriate exit code
    if result.missing > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
