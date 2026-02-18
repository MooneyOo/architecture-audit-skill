# Phase 2 Validation Checklist

## Overview

Use this checklist to validate that the System Context (C4 Level 1) phase is complete and accurate.

---

## System Purpose

### Required Elements

| Element | Status | Notes |
|---------|--------|-------|
| Primary purpose stated (1-2 sentences) | [ ] | |
| Business context understood | [ ] | |
| Target users identified | [ ] | |

### System Purpose Statement

> [Insert system purpose here for review]

---

## Actor Identification

### Person Actors

| Actor | Identified | Detection Evidence |
|-------|------------|-------------------|
| End User | [ ] | |
| Admin | [ ] | |
| Support Agent | [ ] | |
| API Consumer | [ ] | |
| Other: _____ | [ ] | |

### External Systems

| System | Identified | Detection Evidence |
|--------|------------|-------------------|
| Database | [ ] | |
| External API | [ ] | |
| Email Service | [ ] | |
| Auth Provider | [ ] | |
| Storage Service | [ ] | |
| Other: _____ | [ ] | |

### Internal Systems (If Microservices)

| Service | Identified | Detection Evidence |
|---------|------------|-------------------|
| | [ ] | |
| | [ ] | |

---

## Data Flows

### Inbound Data Flows

| Data Flow | Documented | Source | Format |
|-----------|------------|--------|--------|
| User input | [ ] | | |
| API requests | [ ] | | |
| Webhooks | [ ] | | |
| File uploads | [ ] | | |

### Outbound Data Flows

| Data Flow | Documented | Destination | Format |
|-----------|------------|-------------|--------|
| API responses | [ ] | | |
| External API calls | [ ] | | |
| Emails | [ ] | | |
| Webhooks sent | [ ] | | |

---

## C4Context Diagram Validation

### Syntax Check

| Check | Status | Notes |
|-------|--------|-------|
| `C4Context` keyword present | [ ] | |
| `title` defined | [ ] | |
| All `Person` nodes defined | [ ] | |
| All `System` nodes defined | [ ] | |
| All `System_Ext` nodes defined | [ ] | |
| All `Rel` reference existing nodes | [ ] | |
| No duplicate node aliases | [ ] | |

### Content Check

| Check | Status | Notes |
|-------|--------|-------|
| All identified actors in diagram | [ ] | |
| All external systems in diagram | [ ] | |
| Relationships are clear | [ ] | |
| Protocols specified | [ ] | |

### Diagram Preview

```mermaid
[Paste generated diagram here for review]
```

---

## Interaction Table Validation

### Actor / System Interactions

| Check | Status | Notes |
|-------|--------|-------|
| All actors listed | [ ] | |
| All types correctly classified | [ ] | |
| Interaction summaries complete | [ ] | |
| No actors missing from table | [ ] | |

### Data Flows Table

| Check | Status | Notes |
|-------|--------|-------|
| Direction specified | [ ] | |
| Data type described | [ ] | |
| Source/destination named | [ ] | |
| Format specified | [ ] | |
| Trigger documented | [ ] | |

---

## Discovery Questions Answered

### User Identification

- [ ] What routes/pages are publicly accessible?
- [ ] What routes require authentication?
- [ ] What routes require admin privileges?
- [ ] Are there different user roles?

### External Systems

- [ ] What external APIs does the system call?
- [ ] What webhooks does the system receive?
- [ ] What databases/services does it connect to?
- [ ] What third-party SDKs are used?

### Data Flows

- [ ] What data enters the system?
- [ ] What data leaves the system?
- [ ] What triggers each data flow?
- [ ] What format is the data in?

---

## Output Completeness

| Section | Required | Present | Notes |
|---------|----------|---------|-------|
| System Purpose | Yes | [ ] | |
| C4Context Diagram | Yes | [ ] | |
| Actor Interaction Table | Yes | [ ] | |
| Data Flows Table | Yes | [ ] | |

---

## Cross-Reference Check

### Code Verification

Verify all external systems mentioned exist in code:

| System | File Evidence | Verified |
|--------|---------------|----------|
| | | [ ] |
| | | [ ] |

### No Hallucination Check

- [ ] All external systems have corresponding code evidence
- [ ] No systems listed that aren't referenced in codebase
- [ ] API endpoints are real (not invented)

---

## Final Sign-off

### Issues Found

| Issue | Severity | Resolution |
|-------|----------|------------|
| | | |

### Completion Status

- [ ] System purpose documented
- [ ] All actors identified
- [ ] C4Context diagram generated and validated
- [ ] Interaction tables complete
- [ ] Data flows documented
- [ ] Discovery questions answered
- [ ] Ready for Phase 3

**Validated by:** _______________

**Date:** _______________
