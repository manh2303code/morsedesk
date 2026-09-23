# Dựng MorseDesk.exe một file cho Windows. Gọi từ gốc repo, trong PowerShell:
#
#   powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
#
# Kết quả: dist/MorseDesk.exe và dist/SHA256SUMS-windows.txt. Kiểm bằng scripts/test_windows_exe.ps1.
#
# Không gọi `uv sync`: nó gỡ mọi gói không khai báo trong pyproject khỏi .venv của máy dev (chính
# pyinstaller cũng là một gói như vậy). `uv pip install` chỉ thêm, không gỡ.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

foreach ($f in "models/acoustic.onnx", "models/lm/en.bin", "models/lm/ru.bin", "models/lm/kk.bin") {
    if (-not (Test-Path $f)) { throw "thiếu $f — bản dựng sẽ không giải mã được bằng model" }
}
$ver = (Get-Content models/acoustic.json -Raw | ConvertFrom-Json).version
Write-Host "== model âm thanh v$ver =="

uv pip install --quiet "pyinstaller>=6.6,<7"
if ($LASTEXITCODE -ne 0) { throw "không cài được pyinstaller" }

Write-Host "== dựng bản một file =="
uv run pyinstaller --noconfirm --log-level WARN --workpath build/win --distpath dist `
    packaging/morsedesk.spec -- --onefile
if ($LASTEXITCODE -ne 0) { throw "pyinstaller thất bại (mã $LASTEXITCODE)" }

$exe = Get-Item dist/MorseDesk.exe
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
"$hash  MorseDesk.exe" | Set-Content -Encoding ascii dist/SHA256SUMS-windows.txt
Write-Host ("== xong: {0} ({1:N1} MB), model v{2} ==" -f $exe.FullName, ($exe.Length / 1MB), $ver)
Write-Host "sha256 $hash"
