"""Script kiểm tra và khởi tạo kết nối cơ sở dữ liệu PostgreSQL cho dự án."""

import sys
from pathlib import Path

# Thêm thư mục gốc vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.database import get_db_config, ensure_database_exists, init_db, test_connection
from app.services.auth_service import ensure_default_admin


def main():
    print("=" * 60)
    print("   KIỂM TRA KẾT NỐI POSTGRESQL - AI NETWORK IDS/IPS")
    print("=" * 60)

    cfg = get_db_config()
    print(f"[*] Cấu hình hiện tại:")
    print(f"    - Host: {cfg.get('host')}")
    print(f"    - Port: {cfg.get('port')}")
    print(f"    - User: {cfg.get('user')}")
    print(f"    - Database: {cfg.get('database')}")
    masked_pw = "*" * len(str(cfg.get('password', '')))
    print(f"    - Password: {masked_pw} ({cfg.get('password')})")
    print("-" * 60)

    print("[*] Đang kiểm tra kết nối tới PostgreSQL...")
    ok, msg = test_connection()
    if not ok:
        print("\n❌ THẤT BẠI:")
        print(f"   {msg}")
        print("\n👉 Hướng dẫn khắc phục:")
        if "password authentication failed" in msg:
            print("   Mật khẩu của tài khoản postgres trên máy bạn không khớp với db_config.json.")
            print("   1. Nếu bạn nhớ mật khẩu khi cài PostgreSQL: hãy mở file 'db_config.json' và đổi 'password' thành mật khẩu của bạn.")
            print("   2. Nếu bạn quên mật khẩu: hãy chạy file 'reset_pg_password.bat' bằng quyền Administrator để tự động đặt lại mật khẩu thành '123456'.")
        elif "connection to server at" in msg and "failed" in msg:
            print("   Dịch vụ PostgreSQL chưa chạy. Vui lòng mở Services (services.msc) và Start dịch vụ 'postgresql-x64-18'.")
        sys.exit(1)

    print(f"✅ {msg}")

    print("[*] Đang khởi tạo bảng cơ sở dữ liệu...")
    init_ok, init_msg = init_db()
    if not init_ok:
        print(f"❌ Lỗi khởi tạo bảng: {init_msg}")
        sys.exit(1)
    print(f"✅ {init_msg}")

    print("[*] Đang kiểm tra tài khoản quản trị viên mặc định...")
    admin_ok, admin_msg = ensure_default_admin()
    if admin_ok:
        print(f"✅ {admin_msg}")
        print("   Tài khoản đăng nhập quản trị: admin / Admin@123")
    else:
        print(f"⚠️  {admin_msg}")

    print("=" * 60)
    print("🎉 TẤT CẢ ĐÃ SẴN SÀNG! Bạn có thể chạy 'python main.py' để đăng nhập / đăng ký.")
    print("=" * 60)


if __name__ == "__main__":
    main()

