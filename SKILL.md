---
name: architecture-audit
description: |
  Performs comprehensive 10-phase codebase audits to produce System Architecture & Logic Reference documents and business-focused Product Overviews. Use when users request architecture reviews, codebase audits, system documentation, logic flow mapping, C4 diagrams, ER diagrams, product overviews, or need to understand a codebase's structure.

  Triggers: "audit this codebase", "document the architecture", "analyze the system", "create architecture reference", "map the logic flow", "system documentation", "technical debt analysis", "architecture review", "C4 diagrams", "ER diagrams from code", "create product overview", "generate business documentation".
---

# Architecture Audit

Comprehensive codebase analysis producing technical "System Architecture & Logic Reference" documents for AI-driven development and human onboarding, plus business-focused "Product Overview" documents for stakeholders and clients.

## Workflow

Execute phases **sequentially**. Complete each phase before proceeding.

### Phase 1: Discovery & Stack Detection
→ See [references/phase-1-discovery.md](references/phase-1-discovery.md)

Auto-detect languages, frameworks, databases from config files. Build technology manifest.

### Phase 2: System Context (C4 Level 1)
→ See [references/phase-2-system-context.md](references/phase-2-system-context.md)

Define system purpose, external actors, and data flows. Generate C4Context diagram.

### Phase 3: Container Architecture (C4 Level 2)
→ See [references/phase-3-container.md](references/phase-3-container.md)

Map deployable units, communication protocols. Generate C4Container diagram.

### Phase 4: Component Breakdown (C4 Level 3)
→ See [references/phase-4-component.md](references/phase-4-component.md)

Decompose backend into layers, modules, cross-cutting concerns. Generate C4Component diagram.

### Phase 5: Data Layer & Schema
→ See [references/phase-5-data-schema.md](references/phase-5-data-schema.md)

Document complete database structure. Generate erDiagram for SQL/NoSQL schemas.

### Phase 6: Feature Catalog & API Reference
→ See [references/phase-6-feature-catalog.md](references/phase-6-feature-catalog.md)

Map features to code. Build API reference tables with endpoints, auth, request/response schemas.

### Phase 7: Developer Onboarding
→ See [references/phase-7-onboarding.md](references/phase-7-onboarding.md)

Document env vars, startup sequence, auth model, happy paths, error handling.

### Phase 8: Technical Debt & Risk
→ See [references/phase-8-technical-debt.md](references/phase-8-technical-debt.md)

Flag technical debt, fragile logic, deprecated deps. Assign severity levels.

### Phase 9: Validation & Completeness
→ See [references/phase-9-validation.md](references/phase-9-validation.md)

Verify completeness: all routes documented, services mapped, features covered. Run gap analysis and completeness checks.

### Phase 10: Product Overview Generation
→ See [references/phase-10-product-overview.md](references/phase-10-product-overview.md)

Generate user-friendly, business-focused product overview from technical documentation.

**Purpose**: Create non-technical documentation for business stakeholders, executives, and clients

**Input**: System Architecture Reference (completed)

**Output**: `[PROJECT_NAME]-Product-Overview.md` (1,500-2,500 lines)

**Sections Generated**:
1. What is [PROJECT_NAME]?
2. Who is [PROJECT_NAME] For?
3. Key Features Summary
4. Detailed Feature Descriptions
5. Supported Integrations
6. System Capabilities
7. Use Cases & Benefits
8. Getting Started

**Audience**: Business stakeholders, executives, clients, sales/marketing teams

**Key Activities**:
- Read technical architecture sections
- Transform technical content to business language
- Generate feature descriptions with business benefits
- Create use cases with measurable outcomes
- Update README to feature product overview

## Output

### Technical Documentation
Use [templates/output-template.md](templates/output-template.md) as the starting structure.

**Output file:** `System-Architecture-Reference-[PROJECT_NAME].md`

### Product Overview (Phase 10)
Use [templates/product-overview-template.md](templates/product-overview-template.md) as the starting structure.

**Output file:** `[PROJECT_NAME]-Product-Overview.md`

**Audience**: Business stakeholders, executives, clients, sales/marketing teams

**Length**: 1,500-2,500 lines

## Critical Constraints

| Constraint | Detail |
|------------|--------|
| Accuracy | Every file path, function name, endpoint must exist. Never hallucinate. |
| Tech-agnostic | Auto-detect stack from config files. Do NOT assume. |
| Machine-parsable | Prefer tables, structured lists, code blocks over prose. |
| Diagram format | All diagrams use Mermaid.js syntax |

## Self-Check (Before Finalizing)

### Technical Documentation (Phases 1-9)
1. **Path verification**: Confirm every mentioned file exists
2. **Schema completeness**: If no DB found, explicitly state it
3. **Diagram validation**: Verify Mermaid syntax, all nodes defined
4. **Feature coverage**: All routes appear in feature catalog
5. **Env var completeness**: Search for all `process.env`, `os.environ` patterns
6. **Completeness check**: Run `completeness_checker.py` to verify all routes, services, jobs, and events are documented
7. **Gap analysis**: Run `gap_analyzer.py` to identify any documentation, coverage, or quality gaps

### Product Overview (Phase 10)
1. **Section completeness**: All 8 required sections present
2. **No technical jargon**: No code examples, API paths, or unexplained technical terms
3. **Business focus**: Features explain value, use cases have metrics
4. **Document length**: 1,500-2,500 lines
5. **No placeholders**: All `[PLACEHOLDER]` text replaced
6. **README update**: Product overview featured first in documentation/README.md
7. **Validation**: Run `validate_product_overview.py` to verify quality
