# Architecture Audit Skill - Sharing Guide

This document explains how to share the Architecture Audit skill with your friends and colleagues.

---

## Quick Summary

To share this skill, you need to copy the entire `architecture-audit` folder to your friend's Claude Code skills directory.

---

## Files Required

The complete skill consists of the following files (copy ALL of them):

### Root Files
```
architecture-audit/
├── SKILL.md                    # Main skill definition (required)
├── README.md                   # Documentation
└── SHARING-GUIDE.md            # This file
```

### Templates (all required)
```
architecture-audit/templates/
├── output-template.md          # Technical document template
├── comprehensive-template.md   # Comprehensive template
├── database-template.md        # Database schema template
├── feature-catalog-template.md # Feature catalog template
├── component-registry-template.md
└── product-overview-template.md # Business overview template
```

### References (all recommended)
```
architecture-audit/references/
├── phase-1-discovery.md
├── phase-2-system-context.md
├── phase-2-validation.md
├── phase-3-container.md
├── phase-4-component.md
├── phase-5-data-schema.md
├── phase-6-feature-catalog.md
├── phase-7-onboarding.md
├── phase-8-technical-debt.md
├── phase-9-validation.md
├── phase-10-product-overview.md
└── phase-10-validation.md
```

### Scripts (all recommended)
```
architecture-audit/scripts/
├── analyze_dependencies.py
├── assemble_comprehensive.py
├── assemble_document.py
├── auth_analyzer.py
├── cache_manager.py
├── chunked_analyzer.py
├── completeness_checker.py
├── component_breakdown.py
├── container_discovery.py
├── environment_analyzer.py
├── error_handler_analyzer.py
├── feature_analyzer.py
├── feature_catalog.py
├── gap_analyzer.py
├── happy_path_tracer.py
├── progress_tracker.py
├── run_validation.py
├── schema_analysis.py
├── technical_debt_analyzer.py
├── validate_mermaid.py
├── validate_product_overview.py
└── verify_paths.py
```

---

## Sharing Methods

### Method 1: ZIP Archive (Easiest)

**Step 1: Create the ZIP file**

On macOS/Linux:
```bash
cd ~/.claude/skills
zip -r architecture-audit-skill.zip architecture-audit/
```

On Windows (PowerShell):
```powershell
cd $env:USERPROFILE\.claude\skills
Compress-Archive -Path architecture-audit -DestinationPath architecture-audit-skill.zip
```

**Step 2: Share the ZIP file**

Send via:
- Email attachment
- Slack/Teams file upload
- Google Drive / Dropbox / OneDrive
- USB drive
- Any file sharing service

**Step 3: Recipient installs**

On macOS/Linux:
```bash
# Create skills directory if it doesn't exist
mkdir -p ~/.claude/skills

# Unzip to skills directory
unzip architecture-audit-skill.zip -d ~/.claude/skills/
```

On Windows (PowerShell):
```powershell
# Create skills directory if it doesn't exist
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills"

# Unzip to skills directory
Expand-Archive -Path architecture-audit-skill.zip -DestinationPath "$env:USERPROFILE\.claude\skills"
```

---

### Method 2: Git Repository

**Step 1: Create a repository**

```bash
cd ~/.claude/skills/architecture-audit
git init
git add .
git commit -m "Initial commit - Architecture Audit Skill"
```

**Step 2: Push to GitHub/GitLab**

```bash
# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/architecture-audit-skill.git
git branch -M main
git push -u origin main
```

**Step 3: Recipient installs**

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/YOUR_USERNAME/architecture-audit-skill.git ~/.claude/skills/architecture-audit
```

---

### Method 3: Direct Copy (Same Network)

If you're on the same network, you can copy directly:

**Using scp (macOS/Linux):**
```bash
scp -r ~/.claude/skills/architecture-audit friend@their-computer:~/.claude/skills/
```

**Using shared network drive:**
1. Copy `architecture-audit` folder to shared drive
2. Recipient copies from shared drive to `~/.claude/skills/`

---

### Method 4: Copy-Paste Single Command

For the recipient, here's a single command to download and install from a ZIP URL:

```bash
# Replace YOUR_URL with the actual download URL
mkdir -p ~/.claude/skills && curl -L YOUR_URL | tar -xz -C ~/.claude/skills
```

---

## Verification

After installation, verify the skill works:

```bash
# Check the skill is installed
ls ~/.claude/skills/architecture-audit/

# Expected output:
# SKILL.md  README.md  SHARING-GUIDE.md  templates/  references/  scripts/
```

In Claude Code, test by saying:
```
"audit this codebase"
```

or

```
"document the architecture"
```

---

## Minimum Required Files

If you need to share a minimal version, these are the absolute minimum files:

```
architecture-audit/
├── SKILL.md                              # Required - skill definition
├── templates/
│   └── output-template.md                # Required - document template
└── references/
    ├── phase-1-discovery.md              # Required - discovery phase
    ├── phase-2-system-context.md         # Required - context phase
    └── phase-3-container.md              # Required - container phase
```

Note: Without the scripts, the skill will still work for basic audits but won't have:
- Automated schema analysis
- Path verification
- Mermaid validation
- Product overview generation (Phase 10)

---

## Troubleshooting

### "Skill not found" error

1. Verify the folder is in the correct location:
   ```bash
   ls ~/.claude/skills/architecture-audit/SKILL.md
   ```

2. Check file permissions:
   ```bash
   chmod -R 755 ~/.claude/skills/architecture-audit/
   ```

### "Permission denied" errors

```bash
chmod +x ~/.claude/skills/architecture-audit/scripts/*.py
```

### Skill works but scripts fail

Make sure Python 3.8+ is installed:
```bash
python3 --version
```

---

## File Sizes

Approximate sizes for planning transfers:

| Component | Size |
|-----------|------|
| Complete skill (all files) | ~500 KB |
| Just markdown files (SKILL.md, README, references) | ~150 KB |
| All scripts | ~200 KB |
| All templates | ~100 KB |

---

## Version Info

When sharing, let recipients know:
- Skill version (check SKILL.md header)
- Date of your copy
- Any customizations you've made

---

## Questions?

If recipients have issues:
1. Check Claude Code documentation
2. Verify all files are present
3. Check file permissions
4. Try the minimum required files first
