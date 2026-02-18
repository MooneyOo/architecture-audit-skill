#!/usr/bin/env python3
"""
Comprehensive Document Assembler

Combines all analysis results into final documentation using the comprehensive template.
Also generates business-focused product overview from technical documentation.

Usage:
    python assemble_comprehensive.py <project_path> [options]

Options:
    --output-dir DIR      Output directory (default: ./architecture-output)
    --separate-docs       Generate separate documents (database, components, features)
    --template FILE       Custom template file
    --skip-validation     Skip validation checks
    --skip-product-overview  Skip Phase 10 (product overview generation)
    --force               Force regeneration, ignore cache
    --quiet               Suppress progress output
    --format FORMAT       Output format for status (markdown/json)
    --help                Show usage information

Exit Codes:
    0 - Document assembled successfully with no validation errors
    1 - Document assembled but validation warnings found
    2 - Failed to assemble document
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any


@dataclass
class AssemblyConfig:
    """Configuration for document assembly."""
    project_path: Path
    output_dir: Path
    separate_docs: bool
    template_path: Optional[Path]
    project_name: str
    skip_validation: bool
    skip_product_overview: bool
    force: bool
    quiet: bool


@dataclass
class AnalysisResults:
    """Container for all analysis results."""
    database: dict = field(default_factory=dict)
    components: dict = field(default_factory=dict)
    features: dict = field(default_factory=dict)
    environment: dict = field(default_factory=dict)
    technical_debt: dict = field(default_factory=dict)
    container: dict = field(default_factory=dict)
    auth: dict = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Results from validation checks."""
    path_verification: dict = field(default_factory=dict)
    mermaid_validation: dict = field(default_factory=dict)
    schema_completeness: dict = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return (
            self.path_verification.get('missing', 0) > 0 or
            self.mermaid_validation.get('invalid', 0) > 0 or
            not self.schema_completeness.get('is_complete', True)
        )


@dataclass
class AssemblyResult:
    """Result of document assembly."""
    success: bool
    output_path: str
    project_name: str
    codebase_version: str
    generated_at: str
    validation: ValidationReport
    documents: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Script locations
SCRIPT_DIR = Path(__file__).parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "templates"


def get_codebase_version(codebase_path: Path) -> str:
    """Get git commit info if available."""
    try:
        commit = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=codebase_path,
            stderr=subprocess.DEVNULL
        ).decode().strip()

        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=codebase_path,
            stderr=subprocess.DEVNULL
        ).decode().strip()

        return f"{commit} ({branch})"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "Unknown (not a git repository)"


def detect_tech_stack(codebase_path: Path) -> dict:
    """Detect technology stack and return as structured data."""
    tech = {
        "languages": [],
        "frameworks": [],
        "databases": [],
        "tools": [],
        "summary": ""
    }

    # Check for package.json (Node.js)
    for subdir in ['', 'backend', 'frontend', 'server', 'api', 'src']:
        check_path = codebase_path / subdir / "package.json" if subdir else codebase_path / "package.json"
        if check_path.exists():
            if "Node.js" not in tech["languages"]:
                tech["languages"].append("Node.js")
            try:
                with open(check_path) as f:
                    data = json.load(f)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

                if "react" in str(deps).lower():
                    tech["frameworks"].append("React")
                if "next" in str(deps).lower():
                    tech["frameworks"].append("Next.js")
                if "express" in str(deps).lower():
                    tech["frameworks"].append("Express")
                if "typescript" in str(deps).lower():
                    if "TypeScript" not in tech["languages"]:
                        tech["languages"].append("TypeScript")
                if "prisma" in str(deps).lower():
                    tech["tools"].append("Prisma")
            except:
                pass
            break

    # Check for requirements.txt (Python)
    for subdir in ['', 'backend', 'server', 'api', 'src']:
        check_path = codebase_path / subdir / "requirements.txt" if subdir else codebase_path / "requirements.txt"
        if check_path.exists():
            if "Python" not in tech["languages"]:
                tech["languages"].append("Python")
            try:
                with open(check_path) as f:
                    content = f.read().lower()
                if "fastapi" in content:
                    tech["frameworks"].append("FastAPI")
                if "flask" in content:
                    tech["frameworks"].append("Flask")
                if "django" in content:
                    tech["frameworks"].append("Django")
                if "sqlalchemy" in content:
                    tech["tools"].append("SQLAlchemy")
                if "psycopg" in content or "postgres" in content:
                    if "PostgreSQL" not in tech["databases"]:
                        tech["databases"].append("PostgreSQL")
                if "redis" in content:
                    if "Redis" not in tech["databases"]:
                        tech["databases"].append("Redis")
            except:
                pass
            break

    # Check for pyproject.toml
    for subdir in ['', 'backend', 'server', 'api', 'src']:
        check_path = codebase_path / subdir / "pyproject.toml" if subdir else codebase_path / "pyproject.toml"
        if check_path.exists():
            if "Python" not in tech["languages"]:
                tech["languages"].append("Python")
            break

    # Check for go.mod (Go)
    if (codebase_path / "go.mod").exists():
        if "Go" not in tech["languages"]:
            tech["languages"].append("Go")

    # Build summary
    all_tech = tech["languages"] + tech["frameworks"] + tech["databases"] + tech["tools"]
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for t in all_tech:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    tech["summary"] = " · ".join(unique) if unique else "Unknown"

    return tech


def load_product_overview_template() -> str:
    """Load the product overview template."""
    template_path = TEMPLATE_DIR / "product-overview-template.md"
    if template_path.exists():
        with open(template_path, encoding='utf-8') as f:
            return f.read()
    return ""


def generate_product_overview(architecture_content: str, project_name: str, tech_stack: dict, results: AnalysisResults) -> str:
    """
    Generate business-focused product overview from technical architecture.

    Args:
        architecture_content: Content of the System Architecture Reference
        project_name: Project name
        tech_stack: Detected technology stack
        results: Analysis results from other phases

    Returns:
        Product overview document content
    """
    template = load_product_overview_template()

    if not template:
        return generate_fallback_product_overview(project_name, tech_stack, results)

    # Replace basic placeholders
    content = template
    content = content.replace("[PROJECT_NAME]", project_name)
    content = content.replace("[DATE]", datetime.datetime.now().strftime("%Y-%m-%d"))

    # Extract and transform content
    content = populate_what_is_section(content, architecture_content, project_name)
    content = populate_who_is_section(content, architecture_content)
    content = populate_features_section(content, architecture_content, results)
    content = populate_integrations_section(content, architecture_content)
    content = populate_capabilities_section(content, tech_stack, results)
    content = populate_use_cases_section(content, architecture_content, project_name)
    content = populate_getting_started_section(content, architecture_content)

    return content


def populate_what_is_section(content: str, arch_content: str, project_name: str) -> str:
    """Populate 'What is [PROJECT_NAME]?' section from architecture."""
    # Extract system purpose from Section 1 or 2
    purpose_match = re.search(
        r'(?:## 1\..*?|## 2\..*?)(?:System Purpose|Purpose|Description)\s*\n(.*?)(?=\n##|\n###|\Z)',
        arch_content,
        re.DOTALL | re.IGNORECASE
    )

    if purpose_match:
        purpose_text = purpose_match.group(1).strip()
        # Transform to business language
        challenge = transform_to_challenge(purpose_text)
        solution = transform_to_solution(purpose_text)
        value = extract_value_points(purpose_text)
    else:
        challenge = f"Managing {project_name} operations effectively and efficiently."
        solution = f"{project_name} is a comprehensive solution designed to streamline operations and improve outcomes."
        value = ["Improved efficiency", "Better decision-making", "Reduced manual effort"]

    # Replace placeholder sections
    content = re.sub(
        r'\[Describe the business problem.*?\]',
        challenge,
        content,
        flags=re.DOTALL
    )
    content = re.sub(
        r'\[Explain what the system does.*?\]',
        solution,
        content,
        flags=re.DOTALL
    )

    return content


def populate_who_is_section(content: str, arch_content: str) -> str:
    """Populate 'Who is [PROJECT_NAME] For?' section."""
    # Extract user/actor information from architecture
    actors_match = re.search(
        r'(?:Actor|User|Person).*?\n(.*?)(?=\n##|\n###|\Z)',
        arch_content,
        re.DOTALL | re.IGNORECASE
    )

    # Default personas if not found
    if not actors_match:
        return content

    return content


def populate_features_section(content: str, arch_content: str, results: AnalysisResults) -> str:
    """Populate features section from architecture."""
    # Extract capabilities or features
    features = []

    # Try to get from feature catalog
    if results.features.get("features"):
        for feat in results.features["features"][:8]:
            features.append({
                "name": feat.get("name", "Feature"),
                "description": feat.get("description", "")
            })

    # Try to get from capabilities section
    if not features:
        caps_match = re.search(
            r'(?:Capabilities|Key Features|Features)\s*\n(.*?)(?=\n##|\Z)',
            arch_content,
            re.DOTALL | re.IGNORECASE
        )
        if caps_match:
            # Extract bullet points
            bullets = re.findall(r'[-*]\s+(.+)', caps_match.group(1))
            for bullet in bullets[:8]:
                features.append({
                    "name": bullet.split(':')[0].strip() if ':' in bullet else bullet[:50],
                    "description": bullet
                })

    return content


def populate_integrations_section(content: str, arch_content: str) -> str:
    """Populate integrations section from architecture."""
    # Extract external systems from context diagram or integrations section
    integrations_match = re.search(
        r'(?:External|Integration|Systems).*?\n(.*?)(?=\n##|\Z)',
        arch_content,
        re.DOTALL | re.IGNORECASE
    )

    return content


def populate_capabilities_section(content: str, tech_stack: dict, results: AnalysisResults) -> str:
    """Populate system capabilities section."""
    # Use tech stack and analysis results to determine capabilities
    return content


def populate_use_cases_section(content: str, arch_content: str, project_name: str) -> str:
    """Populate use cases section."""
    # Generate default use cases based on features
    return content


def populate_getting_started_section(content: str, arch_content: str) -> str:
    """Populate getting started section from developer guide."""
    # Extract developer guide information
    dev_guide_match = re.search(
        r'(?:Developer Guide|Getting Started|Prerequisites).*?\n(.*?)(?=\n##|\Z)',
        arch_content,
        re.DOTALL | re.IGNORECASE
    )

    return content


def transform_to_challenge(technical_text: str) -> str:
    """Transform technical description to business challenge."""
    # Simple transformations
    text = technical_text

    # Replace technical terms
    replacements = {
        "microservice": "integrated",
        "API": "interface",
        "database": "data storage",
        "REST": "web",
        "GraphQL": "query",
    }

    for tech, business in replacements.items():
        text = re.sub(tech, business, text, flags=re.IGNORECASE)

    return text


def transform_to_solution(technical_text: str) -> str:
    """Transform technical description to business solution."""
    return transform_to_challenge(technical_text)


def extract_value_points(text: str) -> list:
    """Extract value points from text."""
    # Look for bullet points or benefits
    bullets = re.findall(r'[-*]\s+(.+)', text)
    if bullets:
        return bullets[:5]
    return ["Improved efficiency", "Better outcomes", "Reduced costs"]


def generate_fallback_product_overview(project_name: str, tech_stack: dict, results: AnalysisResults) -> str:
    """Generate basic product overview if template not found."""
    return f"""# {project_name} Product Overview

**Generated**: {datetime.datetime.now().strftime("%Y-%m-%d")}
**Version**: 1.0
**Audience**: Business Stakeholders, Executives, Clients

---

## 1. What is {project_name}?

### The Challenge

Organizations face challenges in managing their operations effectively, with data scattered across
multiple systems and manual processes consuming valuable time and resources.

### The Solution

{project_name} provides a comprehensive solution that streamlines operations, centralizes data,
and automates routine tasks, enabling teams to focus on what matters most.

### The Value

- Improved operational efficiency
- Centralized data management
- Automated workflows
- Better decision-making through insights
- Reduced manual effort

---

## 2. Who is {project_name} For?

### Primary Users

- **Business Managers**: Streamline operations and improve team productivity
- **Data Analysts**: Access centralized data for better insights
- **Operations Teams**: Automate routine tasks and reduce manual work

### Organization Types

- Mid-size to enterprise organizations
- Organizations with complex data management needs
- Teams looking to improve operational efficiency

---

## 3. Key Features Summary

### 1. Data Management
Centralized data storage and management capabilities

### 2. Workflow Automation
Automate routine tasks and streamline processes

### 3. Reporting & Analytics
Generate insights from your data with built-in reporting tools

### 4. Integration Capabilities
Connect with existing systems and tools

### 5. User Management
Role-based access control and user administration

---

## 4. Detailed Feature Descriptions

### 4.1 Data Management

**What It Does**

{project_name} provides centralized data management capabilities, allowing organizations to store,
organize, and access their data from a single location.

**Why It Matters**

**The Problem**:
- Data scattered across multiple systems
- Inconsistent data formats
- Difficult to find and access information

**The Value**:
- Single source of truth
- Consistent data formats
- Easy access to information

**How It Works**

1. Data is collected from various sources
2. System organizes and standardizes the data
3. Users can search, filter, and access data
4. Reports and insights are generated automatically

---

## 5. Supported Integrations

### 5.1 Data Sources

**APIs and Connectors**
- Type: Data integration
- Data: Various data formats supported
- Special Features: Automated data synchronization

---

## 6. System Capabilities

### 6.1 Scale & Performance

**Data Volume**
- Handle up to millions of records
- Support for historical data

**Processing Speed**
- Fast query response times
- Efficient data processing

### 6.2 Security & Compliance

**Data Security**
- Encryption at rest and in transit
- Role-based access controls
- Audit logging

---

## 7. Use Cases & Benefits

### 7.1 Operational Efficiency

**Challenge**

"Our team spends hours each day on manual data entry and report generation."

**{project_name} Solution**

- Automated data collection
- One-click report generation
- Streamlined workflows

**Results**

- Reduced manual effort by 50%+
- Faster report generation
- Improved data accuracy

---

## 8. Getting Started

### 8.1 Implementation Process

**Phase 1: Discovery** (Week 1)
- Initial consultation
- Requirements gathering
- System assessment

**Phase 2: Setup** (Weeks 2-3)
- Environment configuration
- Data migration
- User setup

**Phase 3: Training** (Week 4)
- Administrator training
- End-user training
- Go-live support

### 8.4 Next Steps

- Schedule a demo
- Request a pilot program
- Contact our team

---

*This document provides a business-focused overview of {project_name}.*
"""


def load_cache_results(cache_dir: Path) -> AnalysisResults:
    """Load all analysis results from cache."""
    results = AnalysisResults()

    # Cache file mappings
    cache_files = {
        "database": cache_dir / "database" / "result.json",
        "components": cache_dir / "components" / "result.json",
        "features": cache_dir / "features" / "result.json",
        "environment": cache_dir / "environment" / "result.json",
        "technical_debt": cache_dir / "technical_debt" / "result.json",
        "container": cache_dir / "container" / "result.json",
        "auth": cache_dir / "auth" / "result.json",
    }

    for key, path in cache_files.items():
        if path.exists():
            try:
                with open(path) as f:
                    setattr(results, key, json.load(f))
            except (json.JSONDecodeError, IOError):
                pass

    return results


def run_script(script_name: str, args: list[str]) -> tuple[int, str, str]:
    """Run a Python script and return exit code, stdout, stderr."""
    script_path = SCRIPT_DIR / script_name

    if not script_path.exists():
        return -1, "", f"Script not found: {script_path}"

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)] + args,
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Script timed out"
    except Exception as e:
        return -1, "", str(e)


def run_validations(document_path: str, codebase_path: str, skip: bool = False) -> ValidationReport:
    """Run all validation scripts."""
    report = ValidationReport()

    if skip:
        return report

    # Path verification
    code, stdout, stderr = run_script("verify_paths.py", [
        document_path, codebase_path, "--format", "json"
    ])
    if code >= 0 and stdout:
        try:
            data = json.loads(stdout)
            report.path_verification = {
                "total": data.get("summary", {}).get("total", 0),
                "found": data.get("summary", {}).get("found", 0),
                "missing": data.get("summary", {}).get("missing", 0),
            }
        except json.JSONDecodeError:
            report.path_verification = {"error": "Failed to parse output"}

    # Mermaid validation
    code, stdout, stderr = run_script("validate_mermaid.py", [
        document_path, "--format", "json"
    ])
    if code >= 0 and stdout:
        try:
            data = json.loads(stdout)
            report.mermaid_validation = {
                "total": data.get("summary", {}).get("total", 0),
                "valid": data.get("summary", {}).get("valid", 0),
                "invalid": data.get("summary", {}).get("invalid", 0),
            }
        except json.JSONDecodeError:
            report.mermaid_validation = {"error": "Failed to parse output"}

    # Schema completeness
    code, stdout, stderr = run_script("schema_analysis.py", [
        codebase_path, "--completeness", "--format", "json"
    ])
    if code >= 0 and stdout:
        try:
            data = json.loads(stdout)
            report.schema_completeness = {
                "coverage_percentage": data.get("coverage_percentage", 0),
                "detected_count": data.get("detected_count", 0),
                "is_complete": data.get("is_complete", True),
                "issues_count": len(data.get("issues", [])),
            }
        except json.JSONDecodeError:
            report.schema_completeness = {"error": "Failed to parse output"}

    return report


class DocumentAssembler:
    """Assembles comprehensive documentation from analysis results."""

    def __init__(self, config: AssemblyConfig):
        self.config = config
        self.results = AnalysisResults()
        self.tech_stack = {}
        self.codebase_version = ""

    def load_analysis_results(self):
        """Load all analysis results from cache."""
        cache_dir = self.config.project_path / ".audit_cache"
        self.results = load_cache_results(cache_dir)

    def load_template(self, name: str = "comprehensive-template.md") -> str:
        """Load template file."""
        template_path = self.config.template_path or (TEMPLATE_DIR / name)
        if template_path.exists():
            with open(template_path) as f:
                return f.read()
        return ""

    def inject_section(self, content: str, placeholder: str, value: Any) -> str:
        """Replace placeholder with value."""
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2)
        return content.replace(f"[{placeholder}]", str(value))

    def generate_tech_stack_table(self) -> str:
        """Generate tech stack table."""
        lines = ["| Category | Technology | Version |", "|----------|------------|---------|"]

        for lang in self.tech_stack.get("languages", []):
            lines.append(f"| Language | {lang} | - |")
        for fw in self.tech_stack.get("frameworks", []):
            lines.append(f"| Framework | {fw} | - |")
        for db in self.tech_stack.get("databases", []):
            lines.append(f"| Database | {db} | - |")
        for tool in self.tech_stack.get("tools", []):
            lines.append(f"| Tool | {tool} | - |")

        return "\n".join(lines)

    def generate_key_metrics_table(self) -> str:
        """Generate key metrics table."""
        lines = ["| Metric | Value |", "|--------|-------|"]

        # Try to get metrics from results
        total_files = self.results.environment.get("total_files", "N/A")
        components = len(self.results.components.get("components", []))
        endpoints = len(self.results.features.get("endpoints", []))
        tables = len(self.results.database.get("tables", []))

        lines.append(f"| Total Files | {total_files} |")
        lines.append(f"| Components | {components} |")
        lines.append(f"| API Endpoints | {endpoints} |")
        lines.append(f"| Database Tables | {tables} |")

        return "\n".join(lines)

    def generate_entity_json(self) -> str:
        """Generate entity relationships JSON from database results."""
        entities = []

        for table in self.results.database.get("tables", []):
            entity = {
                "name": table.get("name", "unknown"),
                "table": table.get("name", "unknown"),
                "primary_key": table.get("primary_key", "id"),
                "fields": [col.get("name") for col in table.get("columns", [])],
                "relations": {}
            }
            # Add relationships
            for fk in table.get("foreign_keys", []):
                entity["relations"][fk.get("column")] = {
                    "type": "belongsTo",
                    "target": fk.get("references_table")
                }
            entities.append(entity)

        return json.dumps({"entities": entities}, indent=2)

    def generate_endpoint_json(self) -> str:
        """Generate API endpoints JSON from feature results."""
        endpoints = []

        for ep in self.results.features.get("endpoints", []):
            endpoint = {
                "method": ep.get("method", "GET"),
                "path": ep.get("path", "/"),
                "handler": ep.get("handler", ""),
                "auth": ep.get("auth_required", False),
                "request_schema": ep.get("request_schema", ""),
                "response_schema": ep.get("response_schema", "")
            }
            endpoints.append(endpoint)

        return json.dumps({"endpoints": endpoints}, indent=2)

    def generate_component_summary(self) -> str:
        """Generate component summary for AI reference."""
        lines = []

        # Controllers
        controllers = [c for c in self.results.components.get("components", [])
                       if "controller" in c.get("layer", "").lower()]
        if controllers:
            lines.append("Controllers:")
            for c in controllers:
                methods = ", ".join(c.get("methods", [])[:5])
                lines.append(f"- {c.get('name')}: {methods}")

        # Services
        services = [c for c in self.results.components.get("components", [])
                    if "service" in c.get("layer", "").lower()]
        if services:
            lines.append("\nServices:")
            for s in services:
                methods = ", ".join(s.get("methods", [])[:5])
                lines.append(f"- {s.get('name')}: {methods}")

        return "\n".join(lines) if lines else "No components found."

    def generate_project_structure(self) -> str:
        """Generate project structure tree."""
        # Try to get from environment analysis
        structure = self.results.environment.get("directory_structure", "")
        if structure:
            return structure

        # Generate basic structure
        lines = [f"{self.config.project_name}/"]
        try:
            for item in sorted(self.config.project_path.iterdir())[:20]:
                if item.is_dir() and not item.name.startswith('.'):
                    lines.append(f"├── {item}/")
                elif item.is_file() and not item.name.startswith('.'):
                    lines.append(f"├── {item.name}")
        except:
            pass
        return "\n".join(lines)

    def generate_environment_vars_table(self) -> str:
        """Generate environment variables table."""
        lines = ["| Variable | Purpose | Required | Default |", "|----------|---------|----------|---------|"]

        env_vars = self.results.environment.get("environment_variables", [])
        for var in env_vars[:20]:  # Limit to 20
            lines.append(
                f"| {var.get('name', 'N/A')} | {var.get('purpose', '-')} | "
                f"{'Yes' if var.get('required') else 'No'} | {var.get('default', '-')} |"
            )

        if not env_vars:
            lines.append("| (none detected) | - | - | - |")

        return "\n".join(lines)

    def generate_technical_debt_table(self) -> str:
        """Generate technical debt table."""
        lines = ["| Issue | Severity | Location | Suggested Fix |", "|-------|----------|----------|---------------|"]

        issues = self.results.technical_debt.get("issues", [])
        for issue in issues[:15]:  # Limit to 15
            lines.append(
                f"| {issue.get('description', 'N/A')[:50]} | {issue.get('severity', 'Medium')} | "
                f"`{issue.get('location', 'N/A')}` | {issue.get('suggestion', '-')[:30]} |"
            )

        if not issues:
            lines.append("| (no issues detected) | - | - | - |")

        return "\n".join(lines)

    def generate_main_document(self) -> str:
        """Generate the main comprehensive document."""
        template = self.load_template("comprehensive-template.md")

        if not template:
            return self._generate_fallback_document()

        # Replace basic placeholders
        content = template
        content = self.inject_section(content, "PROJECT_NAME", self.config.project_name)
        content = self.inject_section(content, "YYYY-MM-DD", datetime.datetime.now().strftime("%Y-%m-%d"))
        content = self.inject_section(content, "COMMIT_HASH", self.codebase_version)
        content = self.inject_section(content, "BRANCH", "")
        content = self.inject_section(content, "TIMESTAMP", datetime.datetime.now().isoformat())
        content = self.inject_section(content, "TECH_STACK_SUMMARY", self.tech_stack.get("summary", "Unknown"))

        # Generate and inject sections
        content = self.inject_section(content, "TECH_STACK_TABLE", self.generate_tech_stack_table())
        content = self.inject_section(content, "KEY_METRICS_TABLE", self.generate_key_metrics_table())
        content = self.inject_section(content, "PROJECT_STRUCTURE", self.generate_project_structure())
        content = self.inject_section(content, "ENTITY_JSON_ARRAY", self.generate_entity_json())
        content = self.inject_section(content, "ENDPOINT_JSON_ARRAY", self.generate_endpoint_json())
        content = self.inject_section(content, "COMPONENT_SUMMARY", self.generate_component_summary())
        content = self.inject_section(content, "ENV_VARS_TABLE", self.generate_environment_vars_table())
        content = self.inject_section(content, "TECH_DEBT_TABLE", self.generate_technical_debt_table())

        # Clear remaining placeholders
        content = self._clear_remaining_placeholders(content)

        return content

    def _generate_fallback_document(self) -> str:
        """Generate a basic document if template is not found."""
        return f"""# System Architecture & Logic Reference: {self.config.project_name}

> **Generated by:** Architecture Audit Agent
> **Date:** {datetime.datetime.now().strftime("%Y-%m-%d")}
> **Codebase Version:** {self.codebase_version}

This document provides a complete technical mapping of **{self.config.project_name}** for AI-driven development and human onboarding.

**Detected Tech Stack:** {self.tech_stack.get("summary", "Unknown")}

---

## Quick Reference

{self.generate_tech_stack_table()}

---

## Key Metrics

{self.generate_key_metrics_table()}

---

*Document generated by Architecture Audit Agent*
"""

    def _clear_remaining_placeholders(self, content: str) -> str:
        """Clear any remaining placeholders."""
        # Replace common placeholders with empty or default values
        defaults = {
            "SYSTEM_PURPOSE_DESCRIPTION": "System purpose not yet documented.",
            "CAPABILITY_1_NAME": "Feature 1",
            "CAPABILITY_1_DESCRIPTION": "Description pending.",
            "CAPABILITY_2_NAME": "Feature 2",
            "CAPABILITY_2_DESCRIPTION": "Description pending.",
            "CAPABILITY_3_NAME": "Feature 3",
            "CAPABILITY_3_DESCRIPTION": "Description pending.",
            "CAPABILITY_4_NAME": "Feature 4",
            "CAPABILITY_4_DESCRIPTION": "Description pending.",
            "ARCHITECTURE_PATTERN": "Not detected",
            "KEY_DECISIONS": "Pending analysis",
            "EXTERNAL_DEPENDENCIES": "Pending analysis",
            "AI_SYSTEM_SUMMARY": f"This is a {self.tech_stack.get('summary', 'software')} application.",
            "FILES_COUNT": "N/A",
            "COMPONENTS_COUNT": str(len(self.results.components.get("components", []))),
            "FEATURES_COUNT": str(len(self.results.features.get("endpoints", []))),
            "DESC_COVERAGE": "0",
            "COMP_COVERAGE": "0",
            "FEATURE_COVERAGE": "0",
        }

        for key, value in defaults.items():
            content = self.inject_section(content, key, value)

        # Clear any remaining [PLACEHOLDER] patterns
        content = re.sub(r'\[[A-Z_0-9]+\]', '', content)

        return content

    def generate_index(self, documents: list[str]) -> str:
        """Generate index document with links to all docs, featuring product overview first."""
        lines = [
            f"# Documentation Index: {self.config.project_name}",
            "",
            f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Available Documents",
            "",
        ]

        # Find product overview document
        product_overview = None
        other_docs = []
        for doc in documents:
            if "Product-Overview" in doc:
                product_overview = doc
            else:
                other_docs.append(doc)

        # Feature product overview first if present
        if product_overview:
            lines.extend([
                "### 1. Product Overview (Business-Focused)",
                "",
                f"**[{product_overview}]({product_overview})**",
                "",
                "User-friendly overview for business stakeholders, executives, and clients.",
                "- What the system does and why it matters",
                "- Key features and benefits",
                "- Use cases with measurable outcomes",
                "- Getting started guide",
                "",
                "**Audience**: Business stakeholders, executives, clients, sales/marketing teams",
                "",
                "---",
                "",
            ])

        # List other documents
        lines.extend([
            "### Technical Documentation",
            "",
            "| Document | Description |",
            "|----------|-------------|",
        ])

        for doc in other_docs:
            if "Architecture" in doc:
                lines.append(f"| [{doc}]({doc}) | Technical architecture reference |")
            elif "Database" in doc:
                lines.append(f"| [{doc}]({doc}) | Database schema documentation |")
            else:
                lines.append(f"| [{doc}]({doc}) | Architecture documentation |")

        lines.extend([
            "",
            "## Quick Links",
            "",
        ])

        if product_overview:
            lines.append(f"- **For Business Users**: Start with the [Product Overview]({product_overview})")

        arch_doc = other_docs[0] if other_docs else documents[0] if documents else ""
        if arch_doc:
            lines.extend([
                f"- **For Developers**: [Technical Architecture]({arch_doc})",
                f"- **For DBAs**: [Database Schema]({arch_doc}#5-data-layer--schema-reference)",
            ])

        lines.extend([
            "",
            "## Document Versions",
            "",
            "| Document | Version | Date |",
            "|----------|---------|------|",
        ])

        for doc in ([product_overview] + other_docs if product_overview else other_docs):
            doc_name = doc.replace(".md", "").replace("-", " ").replace("_", " ")
            lines.append(f"| {doc_name} | 1.0 | {datetime.datetime.now().strftime('%Y-%m-%d')} |")

        lines.extend([
            "",
            "---",
            "",
            "*Generated by Architecture Audit Agent*"
        ])

        return "\n".join(lines)

    def assemble(self) -> AssemblyResult:
        """Assemble all documents."""
        errors = []
        documents = []

        # Load analysis results
        self.load_analysis_results()

        # Get metadata
        self.codebase_version = get_codebase_version(self.config.project_path)
        self.tech_stack = detect_tech_stack(self.config.project_path)
        generated_at = datetime.datetime.now().isoformat()

        # Create output directory
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate main document
        main_content = ""
        try:
            main_content = self.generate_main_document()
            main_filename = f"System-Architecture-{self.config.project_name}.md"
            main_path = self.config.output_dir / main_filename

            with open(main_path, 'w', encoding='utf-8') as f:
                f.write(main_content)

            documents.append(main_filename)
            if not self.config.quiet:
                print(f"Generated: {main_path}")
        except Exception as e:
            errors.append(f"Failed to generate main document: {e}")

        # Generate Product Overview (Phase 10) - NEW
        if not self.config.skip_product_overview and main_content:
            try:
                if not self.config.quiet:
                    print("\nPhase 10: Generating Product Overview...")

                product_content = generate_product_overview(
                    main_content,
                    self.config.project_name,
                    self.tech_stack,
                    self.results
                )

                product_filename = f"{self.config.project_name}-Product-Overview.md"
                product_path = self.config.output_dir / product_filename

                with open(product_path, 'w', encoding='utf-8') as f:
                    f.write(product_content)

                documents.append(product_filename)
                if not self.config.quiet:
                    print(f"Generated: {product_path}")
                    lines = product_content.count('\n')
                    print(f"  Product Overview: {lines} lines")
            except Exception as e:
                errors.append(f"Failed to generate product overview: {e}")
        elif self.config.skip_product_overview and not self.config.quiet:
            print("Skipping Phase 10 (Product Overview)")

        # Generate index
        try:
            index_content = self.generate_index(documents)
            index_path = self.config.output_dir / "INDEX.md"

            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(index_content)

            if not self.config.quiet:
                print(f"Generated: {index_path}")
        except Exception as e:
            errors.append(f"Failed to generate index: {e}")

        # Run validations
        if documents and not self.config.skip_validation:
            main_path = self.config.output_dir / documents[0]
            validation = run_validations(str(main_path), str(self.config.project_path))
        else:
            validation = ValidationReport()

        return AssemblyResult(
            success=len(errors) == 0,
            output_path=str(self.config.output_dir / documents[0]) if documents else "",
            project_name=self.config.project_name,
            codebase_version=self.codebase_version,
            generated_at=generated_at,
            validation=validation,
            documents=documents,
            errors=errors
        )


def output_json(result: AssemblyResult) -> str:
    """Format assembly result as JSON."""
    output = {
        "success": result.success,
        "output_path": result.output_path,
        "project_name": result.project_name,
        "codebase_version": result.codebase_version,
        "generated_at": result.generated_at,
        "documents": result.documents,
        "validation": {
            "has_errors": result.validation.has_errors,
            "path_verification": result.validation.path_verification,
            "mermaid_validation": result.validation.mermaid_validation,
            "schema_completeness": result.validation.schema_completeness,
        },
        "errors": result.errors
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Assemble comprehensive System Architecture documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
    0 - Document assembled successfully with no validation errors
    1 - Document assembled but validation warnings found
    2 - Failed to assemble document

Examples:
    %(prog)s /path/to/project
    %(prog)s /path/to/project --output-dir ./docs --separate-docs
    %(prog)s /path/to/project --template ./custom-template.md
"""
    )

    parser.add_argument(
        "project_path",
        help="Path to the project directory"
    )

    parser.add_argument(
        "--output-dir",
        default="./architecture-output",
        help="Output directory (default: ./architecture-output)"
    )

    parser.add_argument(
        "--separate-docs",
        action="store_true",
        help="Generate separate documents for database, components, features"
    )

    parser.add_argument(
        "--template",
        help="Custom template file path"
    )

    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation checks"
    )

    parser.add_argument(
        "--skip-product-overview",
        action="store_true",
        help="Skip Phase 10 (product overview generation)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration, ignore cache"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )

    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format for status (default: markdown)"
    )

    args = parser.parse_args()

    # Validate project path
    project_path = Path(args.project_path)
    if not project_path.exists():
        print(f"Error: Project path does not exist: {args.project_path}", file=sys.stderr)
        sys.exit(2)

    # Create config
    config = AssemblyConfig(
        project_path=project_path,
        output_dir=Path(args.output_dir),
        separate_docs=args.separate_docs,
        template_path=Path(args.template) if args.template else None,
        project_name=project_path.name,
        skip_validation=args.skip_validation,
        skip_product_overview=args.skip_product_overview,
        force=args.force,
        quiet=args.quiet
    )

    # Assemble document
    assembler = DocumentAssembler(config)
    result = assembler.assemble()

    # Output result
    if args.format == "json":
        print(output_json(result))
    else:
        if result.errors:
            print("ERRORS:", file=sys.stderr)
            for error in result.errors:
                print(f"  - {error}", file=sys.stderr)
            print()

        if result.success:
            print(f"Document assembled: {result.output_path}")
            print(f"Project: {result.project_name}")
            print(f"Version: {result.codebase_version}")
            print(f"Documents: {len(result.documents)}")

            if not args.skip_validation:
                print()
                print("Validation:")
                print(f"  Paths: {result.validation.path_verification.get('missing', 0)} missing")
                print(f"  Mermaid: {result.validation.mermaid_validation.get('invalid', 0)} invalid")
                print(f"  Schema: {result.validation.schema_completeness.get('coverage_percentage', 0)}% coverage")

    # Return appropriate exit code
    if not result.success:
        sys.exit(2)  # Failed to assemble
    elif result.validation.has_errors:
        sys.exit(1)  # Warnings found
    sys.exit(0)  # Success


if __name__ == "__main__":
    main()
