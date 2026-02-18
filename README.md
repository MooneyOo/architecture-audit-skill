# Architecture Audit Skill

A Claude Code skill that performs comprehensive 10-phase codebase audits to produce "System Architecture & Logic Reference" documents and business-focused "Product Overview" documents for AI-driven development, human onboarding, and stakeholder communication.

## Features

- **10-Phase Analysis**: Discovery, System Context, Containers, Components, Data Schema, Features, Onboarding, Technical Debt, Validation, and **Product Overview Generation**
- **Dual Output**: Technical documentation for developers + Business-focused product overview for stakeholders
- **C4 Diagrams**: Generates Mermaid C4Context, C4Container, C4Component diagrams
- **ER Diagrams**: Auto-generates database entity-relationship diagrams
- **Multi-ORM Support**: SQLAlchemy, Prisma, TypeORM, Sequelize, Django ORM, Mongoose
- **Validation**: Path verification, Mermaid syntax validation, schema completeness checks
- **Tech-Agnostic**: Auto-detects stack from config files
- **Business-Ready**: Generates stakeholder-friendly product overviews with no technical jargon

## Installation

### Option 1: Install Globally (Recommended)

```bash
# Create user skills directory
mkdir -p ~/.claude/skills

# Clone or copy the skill
git clone <repository-url> ~/.claude/skills/architecture-audit
# OR copy from local
cp -r ./architecture-audit ~/.claude/skills/
```

### Option 2: Install per Project

```bash
# In your project directory
mkdir -p .claude/skills
cp -r /path/to/architecture-audit .claude/skills/
```

### Option 3: Reference from Any Location

Add to your project's `.claude/settings.local.json`:

```json
{
  "additionalDirectories": [
    "/path/to/architecture-audit"
  ]
}
```

## Usage

### Trigger Phrases

The skill activates when you say things like:

- "audit this codebase"
- "document the architecture"
- "analyze the system"
- "create architecture reference"
- "map the logic flow"
- "system documentation"
- "C4 diagrams"
- "ER diagrams from code"

### Command Line

Run individual analysis scripts:

```bash
# Dependency analysis
python scripts/analyze_dependencies.py /path/to/project --format markdown

# Schema analysis
python scripts/schema_analysis.py /path/to/project --format markdown --diagram

# Full document assembly
python scripts/assemble_document.py /path/to/project --output ./output

# Path verification
python scripts/verify_paths.py document.md /path/to/project

# Mermaid validation
python scripts/validate_mermaid.py document.md
```

### Example Session

```
You: Audit this codebase and generate architecture documentation

Claude: I'll perform a comprehensive 8-phase architecture audit...
[Generates System-Architecture-Reference-[PROJECT].md]
```

## Output

The skill produces two types of documentation:

### 1. Technical Architecture Reference

A single markdown document containing:

| Section | Content |
|---------|---------|
| 1. Project Overview | Technology manifest, directory tree, config files |
| 2. System Context | C4Context diagram, actors, data flows |
| 3. Container Architecture | C4Container diagram, container details |
| 4. Component Breakdown | C4Component diagram, component registry |
| 5. Data Layer | ER diagram, table schemas, ORM models |
| 6. Feature Catalog | Feature-to-code mapping, API reference |
| 7. Developer Onboarding | Prerequisites, env vars, startup sequence |
| 8. Technical Debt | Known issues, deprecated deps, risks |
| 9. Validation | Completeness checks, gap analysis |

**Output file:** `System-Architecture-Reference-[PROJECT].md`

**Audience:** Developers, DevOps, Technical Leads

### 2. Product Overview (Phase 10 - NEW!)

A business-focused document containing:

| Section | Content |
|---------|---------|
| 1. What is [PROJECT]? | Challenge, Solution, Value proposition |
| 2. Who is it For? | User personas, organization types |
| 3. Key Features Summary | 5-10 major features with descriptions |
| 4. Detailed Feature Descriptions | What, Why, How, Benefits for each feature |
| 5. Supported Integrations | External systems and APIs |
| 6. System Capabilities | Scale, performance, security, compliance |
| 7. Use Cases & Benefits | Real scenarios with measurable outcomes |
| 8. Getting Started | Implementation process, next steps |

**Output file:** `[PROJECT]-Product-Overview.md`

**Audience:** Business stakeholders, executives, clients, sales/marketing teams

**Length:** 1,500-2,500 lines

## Supported Technologies

### Languages
- Python, TypeScript, JavaScript, Go, Rust, Java

### Frameworks
- FastAPI, Flask, Django, Express, NestJS, Next.js, React, Vue

### Databases
- PostgreSQL, MySQL, SQLite, MongoDB

### ORMs
- SQLAlchemy, Prisma, TypeORM, Sequelize, Django ORM, Mongoose

## Skill Structure

```
architecture-audit/
├── SKILL.md                    # Skill definition and workflow
├── README.md                   # This file
├── SHARING-GUIDE.md            # How to share the skill with others
├── templates/
│   ├── output-template.md      # Technical document template
│   └── product-overview-template.md  # Business document template
├── references/
│   ├── phase-1-discovery.md    # Phase 1 guidelines
│   ├── phase-2-system-context.md
│   ├── phase-3-container.md
│   ├── phase-4-component.md
│   ├── phase-5-data-schema.md
│   ├── phase-6-feature-catalog.md
│   ├── phase-7-onboarding.md
│   ├── phase-8-technical-debt.md
│   ├── phase-9-validation.md
│   ├── phase-10-product-overview.md  # Product overview generation
│   └── phase-10-validation.md        # Product overview validation
└── scripts/
    ├── analyze_dependencies.py # Dependency analysis
    ├── schema_analysis.py      # Database schema analysis
    ├── container_discovery.py  # Container detection
    ├── component_breakdown.py  # Component analysis
    ├── feature_catalog.py      # Feature mapping
    ├── environment_analyzer.py # Env var detection
    ├── auth_analyzer.py        # Auth pattern analysis
    ├── technical_debt_analyzer.py
    ├── verify_paths.py         # Path verification
    ├── validate_mermaid.py     # Mermaid validation
    ├── validate_product_overview.py  # Product overview validation
    └── assemble_comprehensive.py    # Final assembly (includes Phase 10)
```

## Sharing with Others

### Method 1: Git Repository

1. **Create a repository:**
   ```bash
   cd architecture-audit
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/username/architecture-audit-skill.git
   git push -u origin main
   ```

2. **Others can install:**
   ```bash
   mkdir -p ~/.claude/skills
   git clone https://github.com/username/architecture-audit-skill.git ~/.claude/skills/architecture-audit
   ```

### Method 2: NPM Package

Create `package.json`:
```json
{
  "name": "claude-code-skill-architecture-audit",
  "version": "1.0.0",
  "description": "Claude Code skill for comprehensive codebase architecture audits",
  "keywords": ["claude", "claude-code", "skill", "architecture", "audit"],
  "files": ["SKILL.md", "README.md", "templates/**", "references/**", "scripts/**"]
}
```

Publish and others can install:
```bash
npm install -g claude-code-skill-architecture-audit
# Then copy to skills directory
```

### Method 3: Direct Share (ZIP)

1. **Create archive:**
   ```bash
   cd /path/to/parent
   zip -r architecture-audit-skill.zip architecture-audit/
   ```

2. **Share the ZIP file** via email, Slack, or file sharing

3. **Recipients install:**
   ```bash
   unzip architecture-audit-skill.zip -d ~/.claude/skills/
   ```

### Method 4: Internal Registry

For teams, host on internal Git server or package registry:

```bash
# Team members add to settings.local.json
{
  "additionalDirectories": [
    "/shared/tools/claude-skills/architecture-audit"
  ]
}
```

## Validation

After installation, verify the skill works:

```bash
# Test on any project
cd /path/to/test-project

# In Claude Code, say:
"audit this codebase"
```

Or run scripts directly:
```bash
python ~/.claude/skills/architecture-audit/scripts/schema_analysis.py . --format markdown
```

## Customization

### Add Custom Patterns

Edit `scripts/analyze_dependencies.py` to add new framework patterns:

```python
FRAMEWORK_PATTERNS = {
    # Add your custom patterns
    "my-framework": "My Framework",
}
```

### Modify Output Template

Edit `templates/output-template.md` to customize document structure.

### Add New Phases

1. Create `references/phase-N-[name].md`
2. Add script in `scripts/[name].py`
3. Update `SKILL.md` workflow

## Requirements

- Python 3.8+
- No external dependencies (uses stdlib only)

## License

MIT License - Feel free to share and modify.

## Contributing

1. Fork the skill repository
2. Make your improvements
3. Submit a pull request

## Support

For issues or feature requests, open an issue on the repository or contact the skill author.
