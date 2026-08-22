// اسکریپت پایه پنل مدیریت فرنود

document.addEventListener("DOMContentLoaded", () => {
    const flashes = document.querySelectorAll(".flash-message");
    flashes.forEach(flash => {
        setTimeout(() => {
            flash.style.opacity = "0";
            flash.style.transition = "opacity 0.3s ease";
            setTimeout(() => flash.remove(), 300);
        }, 3000);
    });
});
