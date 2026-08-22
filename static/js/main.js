const THEME_KEY = "farnoud_theme";
const COLOR_KEY = "farnoud_color";

const COLORS = {
  blue:   { primary: "#3b82f6", hover: "#2563eb", accent: "#38bdf8" },
  purple: { primary: "#a855f7", hover: "#9333ea", accent: "#c084fc" },
  green:  { primary: "#22c55e", hover: "#16a34a", accent: "#4ade80" },
  orange: { primary: "#f59e0b", hover: "#d97706", accent: "#fbbf24" },
  pink:   { primary: "#ec4899", hover: "#db2777", accent: "#f472b6" },
  teal:   { primary: "#14b8a6", hover: "#0d9488", accent: "#2dd4bf" },
  red:    { primary: "#ef4444", hover: "#dc2626", accent: "#f87171" },
  indigo: { primary: "#6366f1", hover: "#4f46e5", accent: "#818cf8" },
};

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(THEME_KEY, theme);
}

function applyColor(name) {
  const c = COLORS[name] || COLORS.blue;
  const root = document.documentElement;
  root.style.setProperty("--primary", c.primary);
  root.style.setProperty("--primary-hover", c.hover);
  root.style.setProperty("--accent", c.accent);
  root.style.setProperty("--primary-soft", c.primary + "24");
  root.style.setProperty("--primary-glow", c.primary + "59");
  localStorage.setItem(COLOR_KEY, name);
  document.querySelectorAll(".color-swatch").forEach(el => {
    el.classList.toggle("active", el.dataset.color === name);
  });
}

function initPreferences() {
  const theme = localStorage.getItem(THEME_KEY) || "dark";
  const color = localStorage.getItem(COLOR_KEY) || "blue";
  applyTheme(theme);
  applyColor(color);

  document.querySelectorAll(".theme-option").forEach(el => {
    el.classList.toggle("active", el.dataset.theme === theme);
    el.addEventListener("click", () => {
      applyTheme(el.dataset.theme);
      document.querySelectorAll(".theme-option").forEach(o =>
        o.classList.toggle("active", o.dataset.theme === el.dataset.theme)
      );
    });
  });

  document.querySelectorAll(".color-swatch").forEach(el => {
    el.addEventListener("click", () => applyColor(el.dataset.color));
  });

  const toggle = document.getElementById("themeToggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme") || "dark";
      const next = cur === "dark" ? "light" : "dark";
      applyTheme(next);
      document.querySelectorAll(".theme-option").forEach(o =>
        o.classList.toggle("active", o.dataset.theme === next)
      );
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initPreferences();
  document.querySelectorAll(".flash-message, .flash").forEach(flash => {
    setTimeout(() => {
      flash.style.opacity = "0";
      flash.style.transition = "opacity .3s";
      setTimeout(() => flash.remove(), 300);
    }, 3200);
  });
});

/* vNext interaction layer: native drag/drop for any admin list marked data-sortable */
(function(){
  const groups=document.querySelectorAll('[data-sortable]');
  groups.forEach(group=>{
    let dragged=null;
    group.querySelectorAll('[data-sort-item], tr[data-sort-item], .panel-card[data-sort-item]').forEach(item=>{
      item.draggable=true;
      item.addEventListener('dragstart',e=>{dragged=item;item.classList.add('sortable-drag');e.dataTransfer.effectAllowed='move';});
      item.addEventListener('dragend',()=>{item.classList.remove('sortable-drag');dragged=null;});
      item.addEventListener('dragover',e=>{
        e.preventDefault();
        if(!dragged||dragged===item)return;
        const r=item.getBoundingClientRect();
        const after=(e.clientY-r.top)>(r.height/2);
        group.insertBefore(dragged,after?item.nextSibling:item);
      });
    });
    group.addEventListener('drop',()=>{
      const ids=[...group.querySelectorAll('[data-sort-item], tr[data-sort-item], .panel-card[data-sort-item]')].map(x=>x.dataset.id).filter(Boolean);
      if(ids.length) fetch(group.dataset.sortable,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids})}).catch(()=>{});
    });
  });
  document.querySelectorAll('input[type=checkbox]').forEach(x=>{
    x.addEventListener('change',()=>x.closest('label')?.classList.toggle('checked',x.checked));
  });
})();
