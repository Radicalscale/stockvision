# AI GPU Configuration (Ultra-Safe Version)
$ErrorActionPreference = 'Stop'

$src = 'C:\Users\dell\Downloads\cudnn-11.2-windows-x64-v8.1.1.33\cuda'
$dst = 'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.2'

Write-Host '🚀 Starting...' -ForegroundColor Cyan

# 1. Copy Files
try {
    Copy-Item -Path "$src\bin\*" -Destination "$dst\bin\" -Force
    Copy-Item -Path "$src\include\*" -Destination "$dst\include\" -Force
    Copy-Item -Path "$src\lib\x64\*" -Destination "$dst\lib\x64\" -Force
    Write-Host '✅ Files copied.' -ForegroundColor Green
}
catch {
    Write-Host '❌ Copy failed. Run as Admin.' -ForegroundColor Red
    exit 1
}

# 2. Set Variables
[Environment]::SetEnvironmentVariable('CUDA_PATH', $dst, 'Machine')
[Environment]::SetEnvironmentVariable('CUDA_PATH_V11_2', $dst, 'Machine')

# 3. Add to Path
$oldPath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$binDir = "$dst\bin"
$nvvpDir = "$dst\libnvvp"

if ($oldPath -notlike "*$binDir*") {
    $oldPath = $oldPath + ';' + $binDir
}
if ($oldPath -notlike "*$nvvpDir*") {
    $oldPath = $oldPath + ';' + $nvvpDir
}

[Environment]::SetEnvironmentVariable('Path', $oldPath, 'Machine')

Write-Host '✅ Variables set.' -ForegroundColor Green
Write-Host '🎉 Please RESTART your computer now.' -ForegroundColor Yellow
