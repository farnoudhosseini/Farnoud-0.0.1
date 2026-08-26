-- جداول سیستم کاربران ربات، کیف پول و پرداخت

CREATE TABLE IF NOT EXISTS bot_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(100) DEFAULT NULL,
    first_name VARCHAR(150) DEFAULT NULL,
    last_name VARCHAR(150) DEFAULT NULL,
    phone VARCHAR(30) DEFAULT NULL,
    balance DECIMAL(18,0) NOT NULL DEFAULT 0,
    trial_count INT NOT NULL DEFAULT 0,
    role ENUM('user','reseller','reseller_vip','vip') NOT NULL DEFAULT 'user',
    referrer_id BIGINT DEFAULT NULL,
    invite_code VARCHAR(32) NOT NULL,
    is_blocked TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_referrer (referrer_id),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_activity (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    action VARCHAR(80) NOT NULL,
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_uid (telegram_id),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS message_templates (
    `key` VARCHAR(80) PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    body TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO message_templates (`key`, title, body) VALUES
('wallet_main', 'کیف پول من', '💰 کیف پول شما\n\n👤 کاربر: [name]\n🆔 آیدی: [id]\n💳 موجودی: [balance] تومان\n🎭 نقش: [role]\n🔗 لینک دعوت: [invite_link]\n👥 زیرمجموعه‌ها: [referrals]'),
('wallet_charge', 'شارژ حساب', 'مبلغ شارژ را وارد کنید.\nحداقل: [min_charge] تومان\nحداکثر: [max_charge] تومان'),
('wallet_gift', 'کد هدیه', '🎁 کد هدیه خود را ارسال کنید:'),
('wallet_referrals', 'زیرمجموعه', '👥 تعداد زیرمجموعه: [referrals]\n🔗 لینک دعوت شما:\n[invite_link]'),
('charge_invoice', 'فاکتور شارژ', '🧾 فاکتور شارژ\n\nمبلغ: [amount] تومان\nشناسه: [invoice_id]\n\nروش پرداخت را انتخاب کنید.'),
('charge_card_info', 'کارت به کارت', '💳 لطفاً مبلغ [amount] تومان را به کارت زیر واریز کنید:\n\nشماره کارت: [card_number]\nبه نام: [card_owner]\n\nپس از واریز، تصویر رسید را ارسال کنید.'),
('charge_waiting', 'در انتظار تایید', '⏳ رسید شما ثبت شد و در انتظار تایید ادمین است.\nشناسه درخواست: [invoice_id]'),
('charge_approved', 'تایید شارژ', '✅ شارژ حساب شما به مبلغ [amount] تومان تایید شد.\nموجودی جدید: [balance] تومان'),
('charge_rejected', 'رد شارژ', '❌ درخواست شارژ شما رد شد.\nدلیل: [reason]');

CREATE TABLE IF NOT EXISTS payment_cards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    card_number VARCHAR(32) NOT NULL,
    owner_name VARCHAR(150) NOT NULL,
    bank_name VARCHAR(100) DEFAULT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS payment_methods (
    id INT AUTO_INCREMENT PRIMARY KEY,
    method_key VARCHAR(40) NOT NULL UNIQUE,
    title VARCHAR(100) NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    config_json TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO payment_methods (method_key, title, is_active) VALUES
('card', 'کارت به کارت', 1),
('variza', 'پرداخت واریزا', 0);

CREATE TABLE IF NOT EXISTS charge_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    amount DECIMAL(18,0) NOT NULL,
    method_key VARCHAR(40) NOT NULL DEFAULT 'card',
    card_id INT DEFAULT NULL,
    status ENUM('pending_payment','waiting_receipt','pending_review','approved','rejected','cancelled') NOT NULL DEFAULT 'pending_payment',
    receipt_file_id VARCHAR(255) DEFAULT NULL,
    admin_note TEXT,
    variza_slug VARCHAR(120) DEFAULT NULL,
    variza_amount DECIMAL(18,0) DEFAULT NULL,
    variza_attempt_code VARCHAR(120) DEFAULT NULL,
    variza_delivery_id VARCHAR(120) DEFAULT NULL,
    paid_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_tg (telegram_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stars_payments (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    charge_id INT DEFAULT NULL,
    stars_amount INT NOT NULL,
    toman_amount DECIMAL(18,0) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_stars_charge (charge_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS gift_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    amount DECIMAL(18,0) NOT NULL,
    max_uses INT NOT NULL DEFAULT 1,
    used_count INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    expires_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS gift_code_uses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code_id INT NOT NULL,
    telegram_id BIGINT NOT NULL,
    amount DECIMAL(18,0) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_code_user (code_id, telegram_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO settings (`key`, `value`) VALUES
('min_charge', '10000'),
('max_charge', '50000000'),
('variza_enabled', '0'),
('variza_api_key', ''),
('variza_webhook_secret', ''),
('variza_title', 'پرداخت واریزا'),
('public_base_url', '');
