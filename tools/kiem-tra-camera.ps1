# Kiểm tra camera cho photobooth: Windows có thấy máy Sony / card ghi hình không, và phần mềm mở được camera nào.
# Chạy: chuột phải file → "Run with PowerShell", hoặc trong PowerShell:  powershell -ExecutionPolicy Bypass -File tools\kiem-tra-camera.ps1

$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Title($text) { Write-Host ""; Write-Host "=== $text ===" -ForegroundColor Cyan }

Title "1. Thiet bi Sony dang cam (ma hang USB 054C)"
$sonyNow = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_054C' }
if ($sonyNow) {
  $sonyNow | Select-Object Status, Class, FriendlyName | Format-Table -AutoSize
} else {
  Write-Host "Khong thay may Sony nao dang cam qua USB." -ForegroundColor Yellow
  $sonyEver = Get-PnpDevice | Where-Object { $_.InstanceId -match 'VID_054C' }
  if ($sonyEver) { Write-Host "(Windows tung thay may Sony truoc day, nhung hien khong ket noi.)" }
  else { Write-Host "(Windows CHUA TUNG thay may Sony: kiem tra cap USB co truyen du lieu, may anh da bat, cai dat USB Connection.)" }
}

Title "2. Camera / card ghi hinh Windows dang thay"
Get-PnpDevice -PresentOnly | Where-Object { $_.Class -in @('Camera', 'Image') -or $_.FriendlyName -match 'Capture|Cam Link|USB Video|HDMI|Imaging Edge|Webcam' } |
  Select-Object Status, Class, FriendlyName | Format-Table -AutoSize

Title "3. Camera phan mem photobooth mo duoc (dung ten nay cho device_identifier)"
$python = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $python) {
  Push-Location $Root
  & $python -c "from photobooth.utils.enumerate import webcameras; [print(' -', name) for name in webcameras()]"
  Pop-Location
} else {
  Write-Host "Chua co .venv: chay run-local.bat mot lan truoc." -ForegroundColor Yellow
}

Title "4. Trang thai camera cua kiosk (can phan mem dang chay)"
try {
  $status = Invoke-RestMethod "http://127.0.0.1:8000/api/framebooth/camera-status" -TimeoutSec 15
  Write-Host ("available = {0}, virtual = {1}" -f $status.available, $status.virtual)
  if ($status.virtual) { Write-Host "-> Dang dung camera ao: chua cau hinh may anh trong phan mem (xem muc 5 cua huong dan)." -ForegroundColor Yellow }
  elseif ($status.available) { Write-Host "-> Camera that dang hoat dong." -ForegroundColor Green }
  else { Write-Host "-> Camera da cau hinh nhung khong mo duoc." -ForegroundColor Yellow }
} catch {
  Write-Host "Phan mem chua chay (http://127.0.0.1:8000 khong phan hoi)." -ForegroundColor Yellow
}

Write-Host ""
Read-Host "Nhan Enter de dong"
