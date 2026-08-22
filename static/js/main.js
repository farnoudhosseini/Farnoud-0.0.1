// اسکریپت پایه پنل مدیریت فرنود
// تم تیره/روشن + رنگ اصلی (localStorage)

const THEME_KEY = "farnoud_theme";
const COLOR_KEY = "farnoud_color";

const COLORS = {
    blue:   { primary: "#0a84ff", hover: "#0071e3" },
    purple: { primary: "#bf5af2", hover: "#a33ad4" },
    green:  { primary: "#30d158", hover: "#28cd41" },
    orange: { primary: "#ff9f0a", hover: "#e68600" },
    pink:   { primary: "#ff375f", hover: "#e01e45" },
    teal:   { primary: "#64d2ff", hover: "#3bb8eb" },
};

function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
    updateThemeToggleIcon(theme);
}

function applyColor(name) {
    const c = COLORS[name] || COLORS.blue;
    document.documentElement.style.setProperty("--primary", c.primary);
    document.documentElement.style.setProperty("--primary-hover", c.hover);
    // soft بر اساس primary
    document.documentElement.style.setProperty("--primary-soft", c.primary + "26");
    localStorage.setItem(COLOR_KEY, name);
    // به‌روزرسانی UI سواچ‌ها
    document.querySelectorAll(".color-swatch").forEach(el => {
        el.classList.toggle("active", el.dataset.color === name);
    });
    document.querySelectorAll(".theme-option[data-theme]").forEach(el => {
        // nothing for color
    });
}

function updateThemeToggleIcon(theme) {
    const btn = document.getElementById("themeToggle");
    if (!btn) return;
    // آیکون ساده با متن/SVG داخل HTML مدیریت می‌شود
    const sun = btn.querySelector(".icon-sun");
    const moon = btn.querySelector(".icon-moon");
    if (sun && moon) {
        if (theme === "light") {
            sun.style.display = "none";
            moon.style.display = "block";
        } else {
            sun.style.display = "block";
            moon.style.display = "none";
        }
    }
}

function initPreferences() {
    const savedTheme = localStorage.getItem(THEME_KEY) || "dark";
    const savedColor = localStorage.getItem(COLOR_KEY) || "blue";
    applyTheme(savedTheme);
    applyColor(savedColor);

    // دکمه‌های تم در صفحه شخصی‌سازی
    document.querySelectorAll(".theme-option").forEach(el => {
        el.classList.toggle("active", el.dataset.theme === savedTheme);
        el.addEventListener("click", () => {
            applyTheme(el.dataset.theme);
            document.querySelectorAll(".theme-option").forEach(o => {
                o.classList.toggle("active", o.dataset.theme === el.dataset.theme);
            });
        });
    });

    // سواچ رنگ
    document.querySelectorAll(".color-swatch").forEach(el => {
        el.classList.toggle("active", el.dataset.color === savedColor);
        el.addEventListener("click", () => applyColor(el.dataset.color));
    });

    // دکمه تم در تاپ‌بار
    const toggle = document.getElementById("themeToggle");
    if (toggle) {
        toggle.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme") || "dark";
            applyTheme(current === "dark" ? "light" : "dark");
            document.querySelectorAll(".theme-option").forEach(o => {
                o.classList.toggle("active", o.dataset.theme === (current === "dark" ? "light" : "dark"));
            });
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initPreferences();

    // حذف فلش‌ها
    document.querySelectorAll(".flash-message").forEach(flash => {
        setTimeout(() => {
            flash.style.opacity = "0";
            flash.style.transition = "opacity 0.3s ease";
            setTimeout(() => flash.remove(), 300);
        }, 3000);
    });
});
