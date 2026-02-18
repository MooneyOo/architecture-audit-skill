# Architecture Audit Prompt Template

Use this prompt to run the architecture-audit skill on any project.

---

## Basic Prompt

```
Run architecture audit on this project and generate complete documentation.
```

---

## Detailed Prompt

```
Run a full 10-phase architecture audit on this codebase:

1. Analyze the project structure and detect the tech stack
2. Generate System Architecture Reference document
3. Generate Product Overview document for business stakeholders

Save all documentation to the documentation/ folder.
```

---

## Minimal Prompt

```
/architecture-audit
```

---

## With Specific Focus

```
Run architecture audit on this project with focus on:
- API endpoints and their documentation
- Database schema and relationships
- Generate product overview for stakeholders
```

---

## For Specific Output

```
Audit this codebase and generate:
1. System-Architecture-Reference-[PROJECT].md (technical documentation)
2. [PROJECT]-Product-Overview.md (business overview)

Include C4 diagrams and ER diagrams where applicable.
```

---

## Quick Reference

| Trigger Phrase | Action |
|----------------|--------|
| `audit this codebase` | Full architecture audit |
| `document the architecture` | Generate technical docs |
| `create product overview` | Generate business docs |
| `analyze the system` | System analysis |
| `C4 diagrams` | Focus on C4 diagrams |
| `ER diagrams` | Focus on database schema |

---

## What Gets Generated

| Document | Purpose | Audience |
|----------|---------|----------|
| `System-Architecture-Reference-*.md` | Technical documentation | Developers |
| `*-Product-Overview.md` | Business overview | Stakeholders |
| `INDEX.md` | Documentation index | All users |

---

## Tips

- Run from the project root directory
- Ensure you have read access to all source files
- For large projects, the audit may take several minutes
- Review generated docs and commit them to your repository
