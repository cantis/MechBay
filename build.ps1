# MechBay Build Script
# Automates version bumping, dependency sync, PyInstaller build, and distribution packaging

# Stop on first error
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MechBay Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Bump patch version
Write-Host "[1/6] Bumping patch version..." -ForegroundColor Yellow
uv version --bump patch
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Version bump failed" -ForegroundColor Red
    exit 1
}

# Extract new version from pyproject.toml
$version = (Get-Content pyproject.toml | Select-String 'version = "(.+)"').Matches.Groups[1].Value
Write-Host "New version: $version" -ForegroundColor Green
Write-Host ""

# Step 2: Sync dependencies
Write-Host "[2/6] Syncing dependencies..." -ForegroundColor Yellow
uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Dependency sync failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 3: Build with PyInstaller
Write-Host "[3/6] Building executable with PyInstaller..." -ForegroundColor Yellow
uv run python -m PyInstaller mechbay.spec --clean
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PyInstaller build failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 4: Create distribution folder
$distFolder = "dist/MechBay_v$version"
Write-Host "[4/6] Creating distribution folder: $distFolder" -ForegroundColor Yellow

if (Test-Path $distFolder) {
    Remove-Item -Recurse -Force $distFolder
}
New-Item -ItemType Directory -Path $distFolder | Out-Null

# Copy executable folder
Copy-Item -Recurse "dist/MechBay/*" $distFolder

# Copy .env.example
Copy-Item ".env.example" "$distFolder/.env.example"

# Generate README.txt
$readmeContent = @"
MechBay v$version
================

GETTING STARTED
---------------
1. Double-click MechBay.exe to start the application
2. Your web browser will automatically open to http://127.0.0.1:5001
3. The application runs locally on your computer (no internet required)
4. Close the terminal window to stop the server

DATABASE LOCATION
-----------------
Your miniature inventory is stored in:
  %APPDATA%\MechBay\mechbay.db

This is typically located at:
  C:\Users\<YourUsername>\AppData\Roaming\MechBay\mechbay.db

BACKING UP YOUR DATA
--------------------
Method 1 - Direct Database Backup (Recommended):
  1. Close MechBay if it's running
  2. Copy the mechbay.db file from %APPDATA%\MechBay\ to a safe location
  3. To restore, copy the backup file back to %APPDATA%\MechBay\

Method 2 - Document files (portable):
  1. In the app, use File → Save inventory to create a .mechbay file
  2. Use Save force on each force to create .mbforce files
  3. Store those files in a safe location
  4. To restore, use File → Open inventory or File → Open force

Linked file paths are stored in:
  %APPDATA%\MechBay\documents.json

UPDATING TO A NEW VERSION
--------------------------
1. Backup your database (see above)
2. Download the new version
3. Extract and run - your data in %APPDATA% will be preserved
4. If you encounter issues, restore from your backup

TROUBLESHOOTING
---------------
- If the browser doesn't open automatically, navigate to http://127.0.0.1:5001
- If port 5001 is already in use, close other applications or edit .env.example
- For issues, check the terminal window for error messages
- Visit https://github.com/cantis/MechBay for support

CONFIGURATION (Advanced)
------------------------
Create a .env file in the same folder as MechBay.exe to customize settings.
See .env.example for available options.

"@

Set-Content -Path "$distFolder/README.txt" -Value $readmeContent
Write-Host "Distribution folder created successfully" -ForegroundColor Green
Write-Host ""

# Step 5: Create ZIP archive
$zipFile = "dist/MechBay_v$version.zip"
Write-Host "[5/6] Creating ZIP archive: $zipFile" -ForegroundColor Yellow

if (Test-Path $zipFile) {
    Remove-Item -Force $zipFile
}

Compress-Archive -Path $distFolder -DestinationPath $zipFile
Write-Host "ZIP archive created successfully" -ForegroundColor Green
Write-Host ""

# Step 6: Summary
Write-Host "[6/6] Build complete!" -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Build Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Version:      $version" -ForegroundColor White
Write-Host "Folder:       $distFolder" -ForegroundColor White
Write-Host "ZIP Archive:  $zipFile" -ForegroundColor White
Write-Host ""
Write-Host "Distribution is ready for testing or deployment!" -ForegroundColor Green
