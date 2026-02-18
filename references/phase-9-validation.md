# Phase 9: Validation & Completeness

## Overview

Run completeness checks and gap analysis to ensure no features are missed and documentation is accurate. This phase validates the quality of the generated documentation by checking coverage, consistency, and completeness.

## Actions

1. Verify all file paths referenced in documentation exist
2. Check schema documentation completeness
3. Verify all routes/endpoints are documented
4. Run gap analysis for coverage issues
5. Generate validation report

## Validation Checks

### 1. Path Verification

Verify every file path mentioned in documentation exists.

```bash
# Run path verification
python scripts/verify_paths.py output/document.md /path/to/project
```

**Common Issues:**
- Files moved/renamed after analysis
- Typos in file paths
- Referenced files deleted

**What Gets Checked:**
- All file paths in backticks (e.g., `src/main.py`)
- Import statements referenced in documentation
- Configuration file paths

### 2. Schema Completeness

Ensure all database models are documented.

| Check | Requirement |
|-------|-------------|
| All models documented | Every ORM model appears in docs |
| All columns listed | All fields appear with types |
| Primary keys marked | PK clearly identified |
| Foreign keys mapped | FK references documented |
| Relationships shown | Entity relationships in ER diagram |

```bash
# Run schema completeness check
python scripts/completeness_checker.py /path/to/project
```

### 3. Feature Coverage

Verify all features are documented.

| Source | Check |
|--------|-------|
| API Routes | All routes appear in feature catalog |
| Service Methods | All public methods mapped to features |
| Scheduled Jobs | All cron/celery tasks documented |
| Event Handlers | All consumers documented |
| Database Tables | All tables referenced in features |

```bash
# Run feature coverage check
python scripts/completeness_checker.py /path/to/project
```

**Coverage Thresholds:**
| Coverage | Status |
|----------|--------|
| 95%+ | Pass |
| 80-94% | Warning |
| <80% | Fail |

### 4. Gap Analysis

Identify documentation gaps.

| Gap Type | Severity | Example |
|----------|----------|---------|
| Coverage | Warning | Route not documented |
| Documentation | Info | Missing field description |
| Consistency | Warning | Naming mismatch |
| Quality | Info | Missing error documentation |

```bash
# Run gap analysis
python scripts/gap_analyzer.py /path/to/project
```

**Gap Categories:**

#### Documentation Gaps
- Missing descriptions
- Missing examples
- Incomplete schemas

#### Coverage Gaps
- Undocumented routes
- Orphaned services
- Missing features

#### Consistency Gaps
- Mismatched names (model vs table)
- Duplicate definitions
- Stale references

#### Quality Gaps
- Missing validation documentation
- Missing error handling docs
- Incomplete workflows

## Output Section

Populates: `## 9. Validation Report`

### Validation Report Template

```markdown
## 9. Validation Report

> **Generated:** [TIMESTAMP]
> **Overall Status:** [PASS/WARN/FAIL]

### Completeness Summary

| Category | Found | Documented | Coverage | Status |
|----------|-------|------------|----------|--------|
| API Routes | N | M | X% | [status icon] |
| Service Methods | N | M | X% | [status icon] |
| Scheduled Jobs | N | M | X% | [status icon] |
| Event Handlers | N | M | X% | [status icon] |
| Database Tables | N | M | X% | [status icon] |

### Path Verification

| Status | Count |
|--------|-------|
| Valid | N |
| Invalid | M |

### Gaps Found

| # | Severity | Category | Description | Location |
|---|----------|----------|-------------|----------|
| 1 | Warning | coverage | Route not documented | file.py:10 |

### Recommendations

1. [Priority recommendation]
2. [Secondary recommendation]

---
*Validation completed successfully*
```

## Self-Check

- [ ] All file paths verified
- [ ] Schema completeness checked
- [ ] Feature coverage calculated
- [ ] Gap analysis completed
- [ ] Validation report generated
- [ ] Critical issues addressed

## Exit Codes

The validation phase returns exit codes:

| Code | Meaning |
|------|---------|
| 0 | All validations pass |
| 1 | Critical issues found |
| 2 | Warnings only (non-critical) |
| 3 | Validation could not complete |

## CLI Options

```bash
# Run full validation
python scripts/run_validation.py /path/to/project

# Validate with document
python scripts/run_validation.py /path/to/project --document output.md

# Skip specific checks
python scripts/run_validation.py /path/to/project --skip path_verification

# Strict mode (fail on warnings)
python scripts/run_validation.py /path/to/project --strict

# Output as JSON
python scripts/run_validation.py /path/to/project --format json

# Save to file
python scripts/run_validation.py /path/to/project --output validation-report.md
```

### Individual Scripts

```bash
# Completeness checker only
python scripts/completeness_checker.py /path/to/project --format markdown

# Gap analyzer only
python scripts/gap_analyzer.py /path/to/project --type coverage

# Path verification only
python scripts/verify_paths.py output.md /path/to/project
```

## Integration with Assembly

When running the full audit with `assemble_comprehensive.py`:

```bash
# Run with validation (default)
python scripts/assemble_comprehensive.py /path/to/project --validate

# Skip validation
python scripts/assemble_comprehensive.py /path/to/project --no-validate

# Strict mode
python scripts/assemble_comprehensive.py /path/to/project --validate --strict
```

## Troubleshooting

### "Path not found" errors

1. Verify file still exists in project
2. Check for typos in path
3. Update documentation with correct path

**Solution:**
```bash
# Find the correct path
find /path/to/project -name "filename.py"
```

### Low feature coverage

1. Run completeness checker for details:
   ```bash
   python scripts/completeness_checker.py /path/to/project
   ```
2. Identify undocumented routes
3. Map orphaned services to features

**Common causes:**
- Internal routes not documented
- New endpoints added after initial audit
- Service methods used only by other services

### Critical gaps found

1. Review gap details:
   ```bash
   python scripts/gap_analyzer.py /path/to/project --severity error
   ```
2. Address critical gaps first
3. Re-run validation after fixes

### Schema coverage issues

1. Check for models without descriptions
2. Verify all table relationships documented
3. Add missing field comments

## Best Practices

### Maintaining High Coverage

1. **Document as you code**: Add docstrings when creating new endpoints
2. **Regular validation**: Run validation after major changes
3. **Address warnings promptly**: Warnings can become errors as coverage drops

### Common Pitfalls

1. **Forgetting internal endpoints**: Health checks, metrics endpoints
2. **Missing service layer docs**: Public methods should be documented
3. **Outdated paths**: After refactoring, update documentation

### Recommended Workflow

1. Run full audit (Phases 1-8)
2. Run Phase 9 validation
3. Address critical gaps
4. Re-run validation
5. Publish documentation
