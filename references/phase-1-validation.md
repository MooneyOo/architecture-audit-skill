# Phase 1 Validation Checklist

## Overview

Use this checklist to validate that the Discovery & Stack Detection phase is complete and accurate.

---

## Configuration Files Scan

### Required Checks

| Check | Status | Notes |
|-------|--------|-------|
| `package.json` scanned | [ ] | |
| `requirements.txt` scanned | [ ] | |
| `pyproject.toml` scanned | [ ] | |
| `go.mod` scanned | [ ] | |
| `Cargo.toml` scanned | [ ] | |
| `docker-compose.yml` analyzed | [ ] | |
| `Dockerfile` analyzed | [ ] | |
| CI/CD configs reviewed | [ ] | |
| `.env.example` reviewed | [ ] | |

### Missing Files (If Applicable)

If any expected files are missing, note why:
- _______________

---

## Technology Stack Detection

### Language Identification

| Item | Detected | Version | Source File |
|------|----------|---------|-------------|
| Primary Language | [ ] | | |
| Secondary Language(s) | [ ] | | |

### Framework Identification

| Item | Detected | Version | Source File |
|------|----------|---------|-------------|
| Backend Framework | [ ] | | |
| Frontend Framework | [ ] | | |
| Build Tool | [ ] | | |

### Database/ORM Identification

| Item | Detected | Version | Source File |
|------|----------|---------|-------------|
| Primary Database | [ ] | | |
| ORM/ODM | [ ] | | |
| Migrations Tool | [ ] | | |
| Cache Layer | [ ] | | |

### Third-Party Services

| Service | Type | Detected In |
|---------|------|-------------|
| | | |
| | | |

---

## Project Structure

### Directory Tree Capture

- [ ] Top 3 levels captured
- [ ] Entry points identified (`main.py`, `server.js`, `index.ts`)
- [ ] Source directories mapped
- [ ] Test directories noted
- [ ] Config directories noted

### Directory Tree Output

```
[Insert tree output here]
```

---

## Output Completeness

| Section | Required | Present | Notes |
|---------|----------|---------|-------|
| Technology Manifest | Yes | [ ] | |
| Directory Tree | Yes | [ ] | |
| Framework Detection | Yes | [ ] | |
| Database Detection | Yes | [ ] | |
| Service Detection | Conditional | [ ] | If services used |

---

## Cross-Reference Verification

### Path Verification

For every file path mentioned in the output:

| Path | Exists | Correct |
|------|--------|---------|
| | [ ] | [ ] |
| | [ ] | [ ] |

### No Hallucination Check

- [ ] All detected technologies have corresponding code/config evidence
- [ ] No technologies listed that aren't in the codebase
- [ ] Version numbers are from actual config files (not guessed)

---

## Dependency Analysis Script Validation

Run the script and verify output:

```bash
python scripts/analyze_dependencies.py <project_path> --format json
```

| Check | Status | Notes |
|-------|--------|-------|
| Script runs without errors | [ ] | |
| All dependencies captured | [ ] | |
| Dependency types correct | [ ] | |
| Dev dependencies separated | [ ] | |

---

## Final Sign-off

### Issues Found

| Issue | Severity | Resolution |
|-------|----------|------------|
| | | |

### Completion Status

- [ ] All configuration files scanned
- [ ] Technology stack fully identified
- [ ] Directory tree generated
- [ ] No hallucinated technologies
- [ ] Ready for Phase 2

**Validated by:** _______________

**Date:** _______________
