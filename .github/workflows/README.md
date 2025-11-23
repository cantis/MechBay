# GitHub Actions Workflows

This directory contains automated CI/CD workflows for MechBay.

## Workflows

### `ci.yml` - Continuous Integration
**Triggers**: Push to `main`/`PackageForDistro` or pull requests to `main`

**Purpose**: Validates code quality on every commit

**Actions**:
- Runs Ruff linter
- Executes pytest test suite
- Verifies app initialization

### `release.yml` - Build and Release
**Triggers**: Manual GitHub release creation only

**Purpose**: Builds Windows executable and attaches to release

**Actions**:
- Builds Windows .exe with PyInstaller
- Creates distribution package with README
- Uploads ZIP file to GitHub release
- Stores artifacts for 30 days

## Quick Release Guide

**Release process:**
```powershell
# 1. Bump version locally
uv version --bump patch

# 2. Commit and push
git add pyproject.toml
git commit -m "Bump version to 0.1.x"
git push

# 3. Create release on GitHub.com
# Go to Releases → Draft a new release
# Create tag matching version (e.g., v0.1.1)
# Click "Publish release"
# GitHub Actions automatically builds and uploads ZIP
```

**See [DEVELOPER.md](../Docs/DEVELOPER.md#continuous-integration--deployment) for detailed instructions.**
