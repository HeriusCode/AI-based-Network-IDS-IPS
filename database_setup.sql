-- ============================================================
-- SQL Setup script for PostgreSQL (AI-based Network IDS/IPS)
-- ============================================================
-- 1. Tạo Database (nếu chưa tạo):
--    Mở pgAdmin hoặc psql và chạy:
--    CREATE DATABASE ids_ips_db;
--
-- 2. Kết nối vào database ids_ips_db:
--    \c ids_ips_db
--
-- 3. Tạo bảng lưu trữ tài khoản người dùng:
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    salt VARCHAR(64) NOT NULL,
    role VARCHAR(50) DEFAULT 'Quản trị viên',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- Tạo Index để tối ưu truy vấn đăng nhập theo username hoặc email
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

