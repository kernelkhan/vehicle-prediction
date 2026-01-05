# Windows Setup Instructions

## Step 1: Fix PowerShell Execution Policy

Run PowerShell **as Administrator** and execute:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

This allows local scripts (like `.venv\Scripts\Activate.ps1`) to run.

**Alternative (if you can't run as admin):**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```
This only affects the current PowerShell session.

## Step 2: Activate Virtual Environment

After fixing the policy, activate the venv:

```powershell
.\.venv\Scripts\Activate.ps1
```

**Alternative activation method (if script still fails):**
```powershell
.\.venv\Scripts\python.exe -m pip --version
```
This verifies the venv is working without activating.

## Step 3: Install Dependencies (Windows-Compatible)

Use the Windows-specific requirements file that excludes Raspberry Pi-only packages:

```powershell
# Make sure you're in the venv (or use full path)
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
```

## Step 4: Verify Installation

```powershell
.\.venv\Scripts\python.exe -c "import cv2, numpy, onnxruntime; print('All core packages installed!')"
```

## Troubleshooting

### If NumPy still fails:
1. Install pre-built NumPy wheel directly:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install numpy --only-binary :all:
   ```

2. Or install Visual Studio Build Tools (if you need to compile):
   - Download: https://visualstudio.microsoft.com/downloads/
   - Install "Desktop development with C++" workload

### If activation script still doesn't work:
Use the direct Python path method:
```powershell
# Instead of: .\.venv\Scripts\Activate.ps1
# Use: .\.venv\Scripts\python.exe directly
.\.venv\Scripts\python.exe -m src.main
```

