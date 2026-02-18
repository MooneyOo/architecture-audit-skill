#!/usr/bin/env python3
"""
Mermaid Diagram Validation Script

Validates Mermaid diagram syntax to ensure all diagrams in the output
will render correctly.

Usage:
    python validate_mermaid.py <document_path> [options]

Options:
    --strict          Fail on any warning
    --format FORMAT   Output format (json/text)
    --help            Show usage

Exit Codes:
    0 - All diagrams valid
    1 - Some diagrams have errors
    2 - Document not found
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DiagramResult:
    """Result of validating a single diagram."""
    index: int
    diagram_type: str
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    title: Optional[str] = None
    node_count: int = 0
    relationship_count: int = 0


@dataclass
class ValidationResult:
    """Result of validating all diagrams in a document."""
    document: str
    diagrams: list[DiagramResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.diagrams)

    @property
    def valid(self) -> int:
        return len([d for d in self.diagrams if d.valid])

    @property
    def invalid(self) -> int:
        return len([d for d in self.diagrams if not d.valid])


def extract_mermaid_blocks(content: str) -> list[str]:
    """Extract all mermaid code blocks from markdown."""
    pattern = r'```mermaid\s*\n(.*?)```'
    matches = re.findall(pattern, content, re.DOTALL)
    return matches


def detect_diagram_type(content: str) -> str:
    """Detect the type of Mermaid diagram."""
    first_line = content.strip().split('\n')[0] if content.strip() else ""

    diagram_types = {
        'C4Context': 'c4-context',
        'C4Container': 'c4-container',
        'C4Component': 'c4-component',
        'C4Dynamic': 'c4-dynamic',
        'C4Deployment': 'c4-deployment',
        'erDiagram': 'er-diagram',
        'sequenceDiagram': 'sequence',
        'flowchart': 'flowchart',
        'graph': 'graph',
        'classDiagram': 'class',
        'stateDiagram': 'state',
        'gitGraph': 'git',
        'pie': 'pie',
        'gantt': 'gantt',
        'mindmap': 'mindmap',
        'timeline': 'timeline',
        'quadrantChart': 'quadrant',
        'requirementDiagram': 'requirement',
        'json': 'json',
    }

    for keyword, dtype in diagram_types.items():
        if keyword.lower() in first_line.lower():
            return dtype

    return 'unknown'


def extract_title(content: str) -> Optional[str]:
    """Extract diagram title if present."""
    # C4 diagram title
    title_match = re.search(r'^\s*title\s+(.+)$', content, re.MULTILINE)
    if title_match:
        return title_match.group(1).strip()

    # Flowchart/graph title (in quotes or after certain patterns)
    title_match = re.search(r'^\s*\[?["\']?(.+?)["\']?\]?\s*$', content.split('\n')[0] if content else '')
    if title_match and len(title_match.group(1)) > 3:
        return title_match.group(1).strip()

    return None


def validate_c4_diagram(content: str) -> tuple[list[str], list[str], int, int]:
    """Validate C4 diagram syntax."""
    errors = []
    warnings = []
    node_count = 0
    relationship_count = 0

    # Extract node definitions
    # C4 patterns: Person, Person_Ext, System, System_Ext, System_Boundary,
    # Container, Container_Ext, Container_Boundary, ContainerDb, Component, ComponentDb
    node_patterns = [
        r'(Person|Person_Ext|System|System_Ext|System_Boundary|Container|Container_Ext|Container_Boundary|ContainerDb|Component|ComponentDb)\s*\(\s*(\w+)',
        r'(Person|Person_Ext|System|System_Ext|Container|Container_Ext|ContainerDb|Component|ComponentDb)\s*\(\s*([a-zA-Z_]\w*)',
    ]

    defined_nodes = set()
    for pattern in node_patterns:
        nodes = re.findall(pattern, content)
        for node_type, node_name in nodes:
            defined_nodes.add(node_name)
            node_count += 1

    # Extract relationships
    # Rel, Rel_Back, Rel_Neighbor, Rel_Down, Rel_Up, Rel_Right, Rel_Left
    rel_patterns = [
        r'Rel(?:_Back|_Neighbor|_Down|_Up|_Right|_Left)?\s*\(\s*(\w+)\s*,\s*(\w+)',
        r'Rel(?:_Back|_Neighbor|_Down|_Up|_Right|_Left)?\s*\(\s*([a-zA-Z_]\w*)\s*,\s*([a-zA-Z_]\w*)',
    ]

    for pattern in rel_patterns:
        relationships = re.findall(pattern, content)
        for source, target in relationships:
            relationship_count += 1

            # Check that all referenced nodes exist
            if source not in defined_nodes:
                errors.append(f"Undefined node '{source}' in relationship")
            if target not in defined_nodes:
                errors.append(f"Undefined node '{target}' in relationship")

    # Check for required title
    if 'title' not in content.lower():
        warnings.append("Missing diagram title")

    # Check for unclosed parentheses in Rel statements
    rel_lines = re.findall(r'Rel[^(\n]*\([^)]*$', content, re.MULTILINE)
    for line in rel_lines:
        if line.count('(') > line.count(')'):
            errors.append(f"Unclosed parenthesis in relationship: {line[:50]}...")

    return errors, warnings, node_count, relationship_count


def validate_er_diagram(content: str) -> tuple[list[str], list[str], int, int]:
    """Validate ER diagram syntax."""
    errors = []
    warnings = []
    entity_count = 0
    relationship_count = 0

    # Extract entity definitions
    entity_pattern = r'^\s*([a-zA-Z_]\w*)\s*\{'
    entities = re.findall(entity_pattern, content, re.MULTILINE)
    defined_entities = set(entities)
    entity_count = len(defined_entities)

    # Extract relationships
    # Common ER relationship patterns: ||--o{, }|--|{, ||--||, }o--o{, etc.
    rel_pattern = r'([a-zA-Z_]\w*)\s*([\}\|][|o]--[\}\|]?[o]?[\{\|]?)\s*([a-zA-Z_]\w*)'
    relationships = re.findall(rel_pattern, content)

    for left, _, right in relationships:
        relationship_count += 1

        if left not in defined_entities:
            errors.append(f"Undefined entity '{left}' in relationship")
        if right not in defined_entities:
            errors.append(f"Undefined entity '{right}' in relationship")

    # Check for unclosed braces in entity definitions
    for entity in defined_entities:
        # Find entity block
        entity_block = re.search(rf'^\s*{re.escape(entity)}\s*\{{([^}}]*)\}}', content, re.MULTILINE | re.DOTALL)
        if entity_block:
            block_content = entity_block.group(1)
            # Check for unclosed braces in field definitions
            if block_content.count('{') != block_content.count('}'):
                errors.append(f"Unclosed braces in entity '{entity}'")

    return errors, warnings, entity_count, relationship_count


def validate_sequence_diagram(content: str) -> tuple[list[str], list[str], int, int]:
    """Validate sequence diagram syntax."""
    errors = []
    warnings = []
    participant_count = 0
    message_count = 0

    # Extract participants/actors
    participant_patterns = [
        r'participant\s+(\w+)',
        r'actor\s+(\w+)',
    ]

    participants = set()
    for pattern in participant_patterns:
        matches = re.findall(pattern, content)
        participants.update(matches)

    participant_count = len(participants)

    # Extract messages
    message_patterns = [
        r'(\w+)\s*->>?>(\w+)',
        r'(\w+)\s*-->>'+'>(\w+)',
        r'(\w+)\s*-x(\w+)',
        r'(\w+)\s*-\\\)'+'>\s*(\w+)',
    ]

    for pattern in message_patterns:
        messages = re.findall(pattern, content)
        for source, target in messages:
            message_count += 1
            if source not in participants:
                errors.append(f"Undefined participant '{source}' in message")
            if target not in participants:
                errors.append(f"Undefined participant '{target}' in message")

    return errors, warnings, participant_count, message_count


def validate_flowchart(content: str) -> tuple[list[str], list[str], int, int]:
    """Validate flowchart/graph diagram syntax."""
    errors = []
    warnings = []
    node_count = 0
    connection_count = 0

    # Extract node definitions (various formats)
    # id["label"], id["label"], id(label), id((label)), etc.
    node_pattern = r'([a-zA-Z_]\w*)\s*[\[\{\(\>]'
    nodes = re.findall(node_pattern, content)
    defined_nodes = set(nodes)
    node_count = len(defined_nodes)

    # Extract connections
    # A --> B, A -->|label| B, A -.-> B, A ==> B, etc.
    connection_pattern = r'([a-zA-Z_]\w*)\s*-[-.=>]+>?-?\s*([a-zA-Z_]\w*)'
    connections = re.findall(connection_pattern, content)

    for source, target in connections:
        connection_count += 1
        # Only check if both look like node references (not subgraph declarations)
        if source not in defined_nodes and not source.startswith('subgraph'):
            errors.append(f"Undefined node '{source}' in connection")
        if target not in defined_nodes and not target.startswith('subgraph'):
            errors.append(f"Undefined node '{target}' in connection")

    return errors, warnings, node_count, connection_count


def validate_diagram(content: str) -> DiagramResult:
    """Validate a single Mermaid diagram."""
    diagram_type = detect_diagram_type(content)
    title = extract_title(content)

    errors = []
    warnings = []
    node_count = 0
    relationship_count = 0

    if diagram_type.startswith('c4'):
        errors, warnings, node_count, relationship_count = validate_c4_diagram(content)
    elif diagram_type == 'er-diagram':
        errors, warnings, node_count, relationship_count = validate_er_diagram(content)
    elif diagram_type == 'sequence':
        errors, warnings, node_count, relationship_count = validate_sequence_diagram(content)
    elif diagram_type in ('flowchart', 'graph'):
        errors, warnings, node_count, relationship_count = validate_flowchart(content)
    else:
        warnings.append(f"Unknown diagram type, skipping detailed validation")

    return DiagramResult(
        index=0,  # Will be set by caller
        diagram_type=diagram_type,
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        title=title,
        node_count=node_count,
        relationship_count=relationship_count
    )


def validate_document(document_path: str) -> ValidationResult:
    """Validate all Mermaid diagrams in a document."""
    doc_path = Path(document_path)

    result = ValidationResult(document=str(doc_path.resolve()))

    # Check document exists
    if not doc_path.exists():
        print(f"Error: Document not found: {document_path}", file=sys.stderr)
        sys.exit(2)

    # Read document content
    try:
        content = doc_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading document: {e}", file=sys.stderr)
        sys.exit(2)

    # Extract mermaid blocks
    blocks = extract_mermaid_blocks(content)

    # Validate each block
    for idx, block in enumerate(blocks, 1):
        diagram_result = validate_diagram(block)
        diagram_result.index = idx
        result.diagrams.append(diagram_result)

    return result


def output_text(result: ValidationResult, strict: bool = False) -> str:
    """Format result as human-readable text."""
    lines = []
    lines.append(f"Validating Mermaid diagrams in {Path(result.document).name}...")
    lines.append("")

    for diagram in result.diagrams:
        lines.append(f"Diagram {diagram.index} ({diagram.diagram_type}):")

        if diagram.title:
            lines.append(f"  Title: {diagram.title}")

        if diagram.node_count > 0:
            lines.append(f"  ✓ {diagram.node_count} nodes defined")

        if diagram.relationship_count > 0:
            lines.append(f"  ✓ {diagram.relationship_count} relationships")

        if diagram.valid:
            lines.append("  ✓ Valid")
        else:
            for error in diagram.errors:
                lines.append(f"  ✗ Error: {error}")

        for warning in diagram.warnings:
            if strict:
                lines.append(f"  ✗ Warning: {warning}")
            else:
                lines.append(f"  ⚠ Warning: {warning}")

        lines.append("")

    lines.append("Summary:")
    lines.append(f"  Total diagrams: {result.total}")
    lines.append(f"  Valid: {result.valid}")
    lines.append(f"  Invalid: {result.invalid}")

    if result.invalid > 0:
        lines.append("")
        lines.append(f"ERROR: {result.invalid} diagram(s) have errors")

    return "\n".join(lines)


def output_json(result: ValidationResult) -> str:
    """Format result as JSON."""
    output = {
        "document": result.document,
        "summary": {
            "total": result.total,
            "valid": result.valid,
            "invalid": result.invalid
        },
        "diagrams": [
            {
                "index": d.index,
                "type": d.diagram_type,
                "title": d.title,
                "valid": d.valid,
                "node_count": d.node_count,
                "relationship_count": d.relationship_count,
                "errors": d.errors,
                "warnings": d.warnings
            }
            for d in result.diagrams
        ]
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Validate Mermaid diagram syntax in a document",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
    0 - All diagrams valid
    1 - Some diagrams have errors
    2 - Document not found

Examples:
    %(prog)s output.md
    %(prog)s output.md --strict
    %(prog)s output.md --format json
"""
    )

    parser.add_argument(
        "document_path",
        help="Path to the markdown document to validate"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )

    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    # Run validation
    result = validate_document(args.document_path)

    # Output results
    if args.format == "json":
        print(output_json(result))
    else:
        print(output_text(result, args.strict))

    # Return appropriate exit code
    has_errors = result.invalid > 0
    has_warnings = any(d.warnings for d in result.diagrams)

    if has_errors or (args.strict and has_warnings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
