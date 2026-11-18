# Script tự động đặt lại mật khẩu người dùng 'postgres' thành '123456' trên Windows
# Yêu cầu: Chạy PowerShell với quyền Administrator (Run as Administrator)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "Reset PostgreSQL Password to 123456"

# 1. Kiểm tra quyền Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host " [!] YÊU CẦU QUYỀN ADMINISTRATOR" -ForegroundColor Red
    Write-Host " Vui lòng bấm chuột phải vào file này hoặc mở PowerShell" -ForegroundColor Yellow
    Write-Host " chọn 'Run as administrator' để tiếp tục." -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "Đang thử tự động yêu cầu quyền Admin..." -ForegroundColor Cyan
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   TỰ ĐỘNG ĐẶT LẠI MẬT KHẨU POSTGRESQL THÀNH 123456" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

# 2. Tìm thư mục PostgreSQL và Data
$pgBase = "C:\Program Files\PostgreSQL"
if (-not (Test-Path $pgBase)) {
    Write-Host "[-] Không tìm thấy thư mục: $pgBase" -ForegroundColor Red
    Pause
    exit 1
}

$pgVersions = Get-ChildItem -Path $pgBase -Directory | Sort-Object Name -Descending
if ($pgVersions.Count -eq 0) {
    Write-Host "[-] Không tìm thấy phiên bản PostgreSQL nào trong $pgBase" -ForegroundColor Red
    Pause
    exit 1
}

$pgVersionDir = $pgVersions[0].FullName
$versionName = $pgVersions[0].Name
Write-Host "[+] Phát hiện PostgreSQL phiên bản: $versionName tại: $pgVersionDir" -ForegroundColor Cyan

$binDir = Join-Path $pgVersionDir "bin"
$psqlPath = Join-Path $binDir "psql.exe"
$dataDir = Join-Path $pgVersionDir "data"
$hbaPath = Join-Path $dataDir "pg_hba.conf"
$hbaBackup = Join-Path $dataDir "pg_hba.conf.orig_bak"

if (-not (Test-Path $hbaPath)) {
    Write-Host "[-] Không tìm thấy file cấu hình: $hbaPath" -ForegroundColor Red
    Pause
    exit 1
}

# 3. Tìm Windows Service của PostgreSQL
$service = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $service) {
    $serviceName = "postgresql-x64-$versionName"
} else {
    $serviceName = $service.Name
}
Write-Host "[+] Tên dịch vụ Windows: $serviceName" -ForegroundColor Cyan

try {
    # 4. Tạm dừng dịch vụ để sửa file cấu hình
    Write-Host "[*] Đang dừng dịch vụ $serviceName..." -ForegroundColor Yellow
    Stop-Service -Name $serviceName -Force -ErrorAction Stop

    # 5. Sao lưu pg_hba.conf
    if (-not (Test-Path $hbaBackup)) {
        Copy-Item -Path $hbaPath -Destination $hbaBackup -Force
        Write-Host "[+] Đã tạo file sao lưu: pg_hba.conf.orig_bak" -ForegroundColor Gray
    }

    # 6. Tạm thời chuyển cơ chế xác thực sang 'trust' cho local
    Write-Host "[*] Tạm chuyển cấu hình xác thực sang 'trust'..." -ForegroundColor Yellow
    $hbaContent = Get-Content -Path $hbaPath -Raw -Encoding UTF8
    $trustedContent = $hbaContent -replace 'scram-sha-256', 'trust' -replace 'md5', 'trust'
    Set-Content -Path $hbaPath -Value $trustedContent -Encoding UTF8

    # 7. Khởi động lại dịch vụ với chế độ trust
    Write-Host "[*] Đang khởi động lại dịch vụ PostgreSQL..." -ForegroundColor Yellow
    Start-Service -Name $serviceName -ErrorAction Stop
    Start-Sleep -Seconds 2

    # 8. Thực thi lệnh ALTER USER để đặt mật khẩu thành 123456
    Write-Host "[*] Đang đặt lại mật khẩu user 'postgres' thành '123456'..." -ForegroundColor Yellow
    $alterCmd = "ALTER USER postgres WITH PASSWORD '123456';"
    & $psqlPath -U postgres -h localhost -p 5432 -c $alterCmd
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[-] Lệnh đổi mật khẩu bằng psql gặp lỗi!" -ForegroundColor Red
    } else {
        Write-Host "[+] Đã đổi mật khẩu thành 123456 thành công!" -ForegroundColor Green
    }

    # 9. Khôi phục lại file pg_hba.conf bảo mật như cũ
    Write-Host "[*] Đang khôi phục lại cơ chế bảo mật ban đầu..." -ForegroundColor Yellow
    if (Test-Path $hbaBackup) {
        Copy-Item -Path $hbaBackup -Destination $hbaPath -Force
    } else {
        Set-Content -Path $hbaPath -Value $hbaContent -Encoding UTF8
    }

    # 10. Khởi động lại dịch vụ
    Write-Host "[*] Khởi động lại dịch vụ PostgreSQL lần cuối..." -ForegroundColor Yellow
    Restart-Service -Name $serviceName -Force -ErrorAction Stop
    Start-Sleep -Seconds 2

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "🎉 HOÀN TẤT THÀNH CÔNG!" -ForegroundColor Green
    Write-Host "   - User: postgres" -ForegroundColor White
    Write-Host "   - Password: 123456" -ForegroundColor White
    Write-Host "   - Port: 5432" -ForegroundColor White
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "Bây giờ bạn có thể mở ứng dụng và Đăng ký / Đăng nhập bình thường!" -ForegroundColor Cyan

} catch {
    Write-Host "[-] Có lỗi xảy ra: $_" -ForegroundColor Red
    if (Test-Path $hbaBackup) {
        Copy-Item -Path $hbaBackup -Destination $hbaPath -Force
        Start-Service -Name $serviceName -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Nhấn Enter để thoát..."
[Console]::ReadLine() | Out-Null

