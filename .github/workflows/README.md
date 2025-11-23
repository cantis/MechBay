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
**Triggers**: GitHub release creation or version tag push (e.g., `v0.1.1`)

**Purpose**: Builds Windows executable and attaches to release

**Actions**:
- Builds Windows .exe with PyInstaller
- Creates distribution package with README
- Uploads ZIP file to GitHub release
- Stores artifacts for 30 days

### `auto-release.yml` - Automatic Release
**Triggers**: Push to `main` with version bump in `pyproject.toml`

**Purpose**: Automates release creation when version changes

**Actions**:
- Detects version changes in `pyproject.toml`
- Creates GitHub release with tag
- Triggers `release.yml` workflow to build executable

## Quick Release Guide

**Easiest method (auto-release):**
```powershell
uv version --bump patch
git add pyproject.toml
git commit -m "Release v0.1.x"
git push
```
GitHub Actions automatically creates release and builds executable.

**See [DEVELOPER.md](../Docs/DEVELOPER.md#continuous-integration--deployment) for detailed instructions.**
