# Kiểm dist/MorseDesk.exe trên máy Windows thật. Gọi từ gốc repo, sau scripts/build_windows.ps1:
#
#   powershell -ExecutionPolicy Bypass -File scripts/test_windows_exe.ps1
#
# Ba phép kiểm:
#   1. Tự kiểm giải mã: `MorseDesk.exe --self-test IN OUT` giải bản tin ru và kk bằng đúng model +
#      LM trong gói, profile auto, rồi so với mã nguồn chạy trên CÙNG file — phải giống hệt. Có nhiễu
#      vì tín hiệu sạch đi đường DSP và không chạm tới model ONNX.
#   2. Khởi động: thời điểm ảnh chờ hiện (tiến trình cha, bootloader) và cửa sổ chính hiện (tiến
#      trình con). Lần chạy ĐẦU của một bản dựng mới là lần Defender quét — ghi riêng.
#   3. Dọn dẹp: đóng cửa sổ bình thường thì thư mục _MEI trong %TEMP% phải biến mất.
#
# BẪY PHÉP ĐO (22/09): bản một file chạy HAI tiến trình, Start-Process -PassThru trả tiến trình CHA
# nên MainWindowHandle của nó chỉ là ảnh chờ. Phải tìm cửa sổ chính ở tiến trình con.
param([switch]$SkipStartup)       # -SkipStartup: chỉ tự kiểm giải mã, không bật cửa sổ
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$exe = (Resolve-Path dist/MorseDesk.exe).Path
# dist/ chứ không phải build/: build_appimage.sh xóa cả build/, mà test_appimage.sh cần các mẫu này.
$work = New-Item -ItemType Directory -Force dist/selftest
$rc = 0

function Invoke-Native([string]$file, [string[]]$argList) {
    # PowerShell 5.1 biến MỌI dòng stderr của lệnh ngoài thành lỗi khi ErrorActionPreference là
    # Stop — kể cả dòng thông báo "đã ghi ..." của `morsedesk encode`. Hạ xuống trong phạm vi hàm.
    $ErrorActionPreference = "Continue"
    & $file @argList *> $null
    return $LASTEXITCODE
}

function Get-Children([int]$parentId) {
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$parentId" |
        ForEach-Object { Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
}

function Measure-Startup([string]$label) {
    $t0 = Get-Date
    $parent = Start-Process -FilePath $exe -PassThru
    $splash = $null; $window = $null; $child = $null
    while (((Get-Date) - $t0).TotalSeconds -lt 180 -and -not $window) {
        $parent.Refresh()
        if (-not $splash -and $parent.MainWindowHandle -ne 0) { $splash = ((Get-Date) - $t0).TotalSeconds }
        foreach ($c in Get-Children $parent.Id) {
            if ($c.MainWindowHandle -ne 0) { $window = ((Get-Date) - $t0).TotalSeconds; $child = $c }
        }
        Start-Sleep -Milliseconds 100
    }
    if (-not $window) {
        Write-Host "  $label : KHÔNG thấy cửa sổ chính sau 180 s"
        Stop-Process -Id $parent.Id -Force -ErrorAction SilentlyContinue
        return $false
    }
    $s = if ($splash) { "{0,5:N1} s" -f $splash } else { "  không thấy" }
    Write-Host ("  {0}: ảnh chờ {1}, cửa sổ chính {2,5:N1} s ('{3}')" -f $label, $s, $window, $child.MainWindowTitle)
    $null = $child.CloseMainWindow()
    if (-not $parent.WaitForExit(20000)) {
        Write-Host "  KHÔNG tự thoát sau khi đóng cửa sổ"; Stop-Process -Id $parent.Id -Force; return $false
    }
    return $true
}

Write-Host "== bản dựng =="
$item = Get-Item $exe
Write-Host ("  {0} ({1:N1} MB), dựng {2}" -f $item.Name, ($item.Length / 1MB), $item.LastWriteTime)
$meiBefore = @(Get-ChildItem $env:TEMP -Directory -Filter "_MEI*" -ErrorAction SilentlyContinue).Count

Write-Host "== khởi động (lần 1 là lần Defender quét bản dựng mới) =="
if ($SkipStartup) { Write-Host "  bỏ qua" }
else { foreach ($i in 1..4) { if (-not (Measure-Startup "lần $i")) { $rc = 1 } } }

Write-Host "== tự kiểm giải mã bằng model trong gói =="
$cases = @(
    @{ profile = "ru"; text = "ПРИВЕТ КАК ДЕЛА У ТЕБЯ"; snr = 8 },
    @{ profile = "kk-cyrl-ru"; text = "СӘЛЕМ ҚАЛАЙСЫҢ БҮГІН"; snr = 8 },
    # Nhịp Farnsworth lệch lưới 1/3/7 nên văn bản cuối đi đường MODEL chứ không phải DSP (tín hiệu
    # tổng hợp nhịp chuẩn đi DSP kể cả ở 0 dB). Có thể lệch đáp án; bắt buộc là giống hệt mã nguồn.
    @{ profile = "en"; text = "CQ CQ DE R1ABC R1ABC K"; snr = 3; extra = @("--farnsworth", "10") }
)
foreach ($c in $cases) {
    $wav = Join-Path $work "$($c.profile).wav"; $out = Join-Path $work "$($c.profile).json"
    $encArgs = @("run", "morsedesk", "encode", $c.text, "--profile", $c.profile, "--out", $wav)
    if ($c.snr) { $encArgs += @("--snr", "$($c.snr)") }
    if ($c.extra) { $encArgs += $c.extra }
    if ((Invoke-Native "uv" $encArgs) -ne 0) { throw "không sinh được $wav" }
    $t0 = Get-Date
    $p = Start-Process -FilePath $exe -ArgumentList "--self-test", "`"$wav`"", "`"$out`"" -PassThru -Wait
    $dt = ((Get-Date) - $t0).TotalSeconds
    $r = Get-Content $out -Raw -Encoding utf8 | ConvertFrom-Json
    # Cùng file vào mã nguồn: bản đóng gói phải cho KẾT QUẢ GIỐNG HỆT, không chỉ "gần đúng".
    $devOut = Join-Path $work "$($c.profile).dev.json"
    $null = Invoke-Native "uv" @("run", "python", "packaging/entry_gui.py", "--self-test", $wav, $devOut)
    $d = Get-Content $devOut -Raw -Encoding utf8 | ConvertFrom-Json
    $same = ($p.ExitCode -eq 0) -and ($r.text -eq $d.text) -and ($r.decoded_by -eq $d.decoded_by)
    if (-not $same) { $rc = 1 }
    $verdict = if ($same) { "GIỐNG mã nguồn" } else { "KHÁC mã nguồn" }
    $exact = if ($r.text -eq $c.text) { "đúng nguyên văn" } else { "lệch đáp án" }
    Write-Host ("  {0,-10} {1}, {2}: '{3}' ngôn ngữ {4}, đường {5}, {6:N1} s" -f `
        $c.profile, $verdict, $exact, $r.text, $r.language, $r.decoded_by, $dt)
    if ($r.error) { Write-Host "    lỗi: $($r.error) $($r.detail)" }
}

Write-Host "== dọn thư mục tạm =="
Start-Sleep -Seconds 2
$meiAfter = @(Get-ChildItem $env:TEMP -Directory -Filter "_MEI*" -ErrorAction SilentlyContinue).Count
Write-Host "  _MEI trong %TEMP%: trước $meiBefore, sau $meiAfter"
if ($meiAfter -gt $meiBefore) { $rc = 1 }

Write-Host ("== {0} ==" -f $(if ($rc -eq 0) { "ĐẠT" } else { "CÓ LỖI" }))
exit $rc
