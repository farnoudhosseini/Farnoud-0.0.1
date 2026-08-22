-- ساخت جدول ادمین‌ها - دیتابیس farnoudbot
-- این فایل را در phpMyAdmin اجرا کنید

CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ادمین پیش‌فرض
-- نام کاربری: admin
-- رمز عبور: admin123
INSERT INTO admins (username, password) 
VALUES ('admin', 'admin123')
ON DUPLICATE KEY UPDATE password = 'admin123';
