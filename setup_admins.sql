-- راه‌اندازی جداول دیتابیس farnoudbot
-- این فایل را در phpMyAdmin یا mysql CLI اجرا کنید

CREATE DATABASE IF NOT EXISTS farnoudbot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE farnoudbot;

CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO admins (username, password)
VALUES ('admin', 'admin123')
ON DUPLICATE KEY UPDATE password = 'admin123';

CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(100) PRIMARY KEY,
    `value` TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO settings (`key`, `value`)
VALUES ('welcome_message', 'سلام! به ربات فرنود خوش آمدید 👋');
