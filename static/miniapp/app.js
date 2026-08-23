const tg = window.Telegram?.WebApp;
if(tg){
  try{ tg.ready(); tg.expand();
    tg.setHeaderColor(tg.themeParams?.bg_color || '#090910');
    tg.setBackgroundColor(tg.themeParams?.bg_color || '#090910');
  }catch(e){}
}
const state={data:null,tab:'home'};

const ICONS = {
  home: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 10.8 12 3.7l8.5 7.1"/><path d="M5.5 10v9.3h13V10"/><path d="M9.2 19.3v-5.8h5.6v5.8"/></svg>',
  services: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="4" width="17" height="5.8" rx="1.8"/><rect x="3.5" y="14.2" width="17" height="5.8" rx="1.8"/><path d="M7 6.9h.01M7 17.1h.01"/></svg>',
  wallet: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7.2h14.2A1.8 1.8 0 0 1 20 9v9.2A1.8 1.8 0 0 1 18.2 20H5.8A2.8 2.8 0 0 1 3 17.2V6.8A2.8 2.8 0 0 1 5.8 4H18a2 2 0 0 1 2 2"/><path d="M20 11.5h-6.1a2.3 2.3 0 0 0 0 4.6H20"/><path d="M15.9 13.8h.01"/></svg>',
  rewards: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.4 14.4 8l5.1.7-3.7 3.6.9 5.1-4.7-2.4-4.7 2.4.9-5.1-3.7-3.6L9.6 8 12 3.4Z"/><path d="M8.2 19.8h7.6"/></svg>',
  profile: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="7.8" r="3.4"/><path d="M5 20c1.5-3.6 3.8-5.3 7-5.3s5.5 1.7 7 5.3"/></svg>',
  bell: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.2 10a5.8 5.8 0 0 1 11.6 0c0 5.9 2.5 6.7 2.5 6.7H3.7S6.2 15.9 6.2 10Z"/><path d="M9.8 20h4.4"/></svg>',
  bolt: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m13.3 2.8-8.1 10h6.1l-.7 8.4 8.2-10.2h-6.2l.7-8.2Z"/></svg>',
  link: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9.7 14.3 4.6-4.6"/><path d="M7.8 17.8H6.7a4.7 4.7 0 0 1 0-9.4h3.1"/><path d="M16.2 6.2h1.1a4.7 4.7 0 0 1 0 9.4h-3.1"/></svg>',
  copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="11.5" height="11.5" rx="2"/><path d="M15.5 8V6.5A2.5 2.5 0 0 0 13 4H6.5A2.5 2.5 0 0 0 4 6.5V13a2.5 2.5 0 0 0 2.5 2.5H8"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7.5V3.8h-3.7"/><path d="M20 3.8a8.5 8.5 0 1 0 1 9.2"/><path d="M20 3.8 16.4 7.4"/></svg>',
  check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.2 4.2L19.2 7"/></svg>',
  support: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12a8 8 0 0 1 16 0"/><path d="M4 12v3.2A2.8 2.8 0 0 0 6.8 18H8v-6H6.8A2.8 2.8 0 0 0 4 14.8"/><path d="M20 12v3.2a2.8 2.8 0 0 1-2.8 2.8H16v-6h1.2a2.8 2.8 0 0 1 2.8 2.8"/><path d="M12 21h2.2"/></svg>',
  vpn: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5 19 6v5.1c0 4.4-2.7 7.6-7 9.4-4.3-1.8-7-5-7-9.4V6l7-2.5Z"/><path d="m8.6 12 2.2 2.2 4.7-4.7"/></svg>',
  empty: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v14H5z"/><path d="M8 9h8M8 12h5M8 15h3"/></svg>',
  purchase: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14l-1.2 15H6.2L5 4Z"/><path d="M9 4a3 3 0 0 0 6 0M8.2 10h7.6M8.2 13h5.2"/></svg>',
  refund: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 7 5 11l4 4"/><path d="M5 11h8a5.5 5.5 0 0 1 5.5 5.5V19"/></svg>',
  plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
  help: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M9.7 9.3a2.4 2.4 0 1 1 3.8 2c-.9.6-1.5 1.1-1.5 2.2M12 16.8h.01"/></svg>',
  telegram: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m20.3 4.2-3.1 15.1c-.2 1-.8 1.2-1.6.8l-4.4-3.2-2.1 2c-.2.2-.4.4-.8.4l.3-4.5 8.2-7.4c.4-.4-.1-.6-.6-.2L6 13.8l-4.3-1.4c-.9-.3-.9-.9.2-1.3L18.7 3c.8-.3 1.8.4 1.6 1.2Z"/></svg>'
};
function icon(name, cls='') {
  const svg = ICONS[name] || ICONS.empty;
  return svg.replace('<svg ', `<svg class="${cls}" `);
}

function applyTheme(theme){
  if(!theme) return;
  state.theme = theme;
  const root = document.documentElement;
  const map = {
    primary:'--accent', primary_2:'--accent-2', bg:'--bg', surface:'--surface',
    text:'--text', muted:'--muted', success:'--success', danger:'--danger', warning:'--warning'
  };
  Object.keys(map).forEach(k=>{ if(theme[k]) root.style.setProperty(map[k], theme[k]); });
  if(theme.surface) root.style.setProperty('--surface-2', theme.surface);
  if(theme.radius) root.style.setProperty('--radius', theme.radius+'px');
  if(theme.font) document.body.style.fontFamily = theme.font + ', Vazirmatn, Tahoma, sans-serif';
  if(theme.bg){ try{ tg?.setBackgroundColor(theme.bg); tg?.setHeaderColor(theme.bg);}catch(e){} }
  // brand
  const brand = document.querySelector('.brand');
  if(brand){
    const mark = brand.querySelector('.brand-mark');
    const strong = brand.querySelector('strong');
    const small = brand.querySelector('small');
    if(theme.logo_url){
      if(mark) mark.innerHTML = '<img src="'+esc(theme.logo_url)+'" alt="" style="width:100%;height:100%;object-fit:contain;border-radius:inherit">';
    } else if(mark && theme.brand_mark){ mark.textContent = theme.brand_mark; }
    if(strong && theme.brand_name) strong.textContent = theme.brand_name;
    if(small && theme.brand_sub) small.textContent = theme.brand_sub;
  }
  // tabs
  const tabs = document.querySelectorAll('.bottom-nav button');
  const labels = [theme.tab_home, theme.tab_services, theme.tab_wallet, theme.tab_rewards, theme.tab_profile];
  const iconKeys = ['home','services','wallet','rewards','profile'];
  tabs.forEach((btn,i)=>{
    const lab = labels[i] || btn.querySelector('small')?.textContent;
    btn.innerHTML = '<span class="nav-ico">'+ICONS[iconKeys[i]]+'</span><small>'+esc(lab)+'</small>';
    if(iconKeys[i]==='rewards' && theme.show_rewards==='0') btn.style.display='none';
    else btn.style.display='';
  });
  // bell icon
  const nb = document.getElementById('notifyBtn');
  if(nb){
    const badge = document.getElementById('notifyBadge');
    nb.innerHTML = ICONS.bell + (badge ? badge.outerHTML : '');
  }
  // custom css
  let st = document.getElementById('themeCustomCss');
  if(!st){ st=document.createElement('style'); st.id='themeCustomCss'; document.head.appendChild(st); }
  st.textContent = theme.custom_css || '';
}

const app=document.getElementById('app');
const loading=document.getElementById('loading');
const API_BASE = (location.pathname.indexOf('/miniapp')===0 ? '' : '') + '/miniapp/api';

function initData(){
  try{
    if(tg && tg.initData) return tg.initData;
  }catch(e){}
  return '';
}
async function api(path,opts={}){
  const headers=Object.assign({
    'X-Telegram-Init-Data': initData(),
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }, opts.headers||{});
  const r=await fetch(API_BASE+path, Object.assign({}, opts, {headers}));
  const d=await r.json().catch(()=>({ok:false,error:'پاسخ نامعتبر'}));
  if(!r.ok||d.ok===false) throw new Error(d.error||'خطایی رخ داد');
  return d;
}
function money(n){return new Intl.NumberFormat('fa-IR').format(Number(n||0))+' تومان'}
function num(n){return new Intl.NumberFormat('fa-IR').format(Number(n||0))}
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function toast(s){const e=document.getElementById('toast');e.textContent=s;e.classList.add('show');setTimeout(()=>e.classList.remove('show'),2600)}
function haptic(type='light'){try{tg?.HapticFeedback?.impactOccurred(type)}catch(e){}}
function showSheet(html){
  const el=document.getElementById('sheet');
  document.getElementById('sheetContent').innerHTML=html;
  el.hidden=false;
  el.classList.add('is-open');
}
function closeSheet(){
  const el=document.getElementById('sheet');
  el.classList.remove('is-open');
  el.hidden=true;
  document.getElementById('sheetContent').innerHTML='';
}
(function bindSheet(){
  const el=document.getElementById('sheet');
  const btn=document.getElementById('sheetClose');
  if(btn) btn.onclick=function(e){e.preventDefault();e.stopPropagation();closeSheet()};
  if(el) el.addEventListener('click',function(e){ if(e.target===el) closeSheet(); });
  // ensure closed on boot
  closeSheet();
})();
function setTab(tab){state.tab=tab;document.querySelectorAll('.bottom-nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));render()}
document.querySelectorAll('.bottom-nav button').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
document.getElementById('notifyBtn').onclick=()=>renderNotifications();

function usagePercent(s){if(!s)return 0; const total=Number(s.volume_gb||0); const rem=Number(s.remaining_gb??total); return total?Math.max(0,Math.min(100,(rem/total)*100)):100}
function statusFa(s){return ({active:'فعال',provisioned:'فعال',expired:'منقضی',suspended:'معلق',no_subscription:'بدون سرویس'})[s]||s||'—'}

function home(){
 const d=state.data.dashboard, s=d.subscription, p=usagePercent(s);
 const b=state.data.banners?.[0];
 return `<h1 class="page-title">سلام ${esc(state.data.user.first_name||'دوست من')} 👋</h1>
 <p class="page-subtitle">همه‌چیز برای مدیریت سرویس شما، همین‌جاست.</p>
 <section class="hero">
  <div class="status-row"><div><div class="eyebrow">وضعیت سرویس</div><div class="status">${s? 'سرویس شما فعال است':'هنوز سرویسی ندارید'}</div></div><span class="pill">${statusFa(d.status)}</span></div>
  ${s?`<div class="usage"><div class="ring" style="--p:${p}"><div class="ring-inner"><strong>${Math.round(p)}%</strong><small>باقی‌مانده</small></div></div><div class="usage-copy"><strong>${num(s.remaining_gb)} GB</strong><span>از ${num(s.volume_gb)} GB</span><span>${num(s.remaining_days)} روز باقی‌مانده</span></div></div>
  <div class="actions"><button class="btn primary" onclick="openService(${s.id})">مدیریت سرویس</button><button class="btn" onclick="setTab('services')">خرید / تمدید</button></div>`
  :`<div class="empty"><span class="big">${icon("vpn")}</span><strong>اولین سرویس خودت را فعال کن</strong><span>پلن مناسب را انتخاب کن و در چند قدم کوتاه شروع کن.</span></div><div class="actions"><button class="btn primary" onclick="setTab('services')">مشاهده پلن‌ها</button></div>`}
 </section>
 <section class="section"><div class="section-head"><h2>خلاصه حساب</h2></div><div class="grid">
  <div class="metric"><span>کیف پول</span><strong>${money(d.balance)}</strong></div>
  <div class="metric"><span>باشگاه</span><strong>${num(d.loyalty.points)}</strong><em>امتیاز</em></div>
  <div class="metric"><span>سطح</span><strong>${esc(d.loyalty.level)}</strong></div>
  <div class="metric"><span>دعوت‌ها</span><strong>${num(d.referrals.total)}</strong><em>نفر</em></div>
 </div></section>
 ${b?`<section class="banner"><img src="${esc(b.image_url||'')}" onerror="this.style.display='none'"><div class="banner-copy"><h3>${esc(b.title)}</h3><p>${esc(b.description||'')}</p>${b.cta?`<button class="btn primary" style="margin-top:14px" onclick="bannerClick('${esc(b.link||'')}')">${esc(b.cta)}</button>`:''}</div></section>`:''}
 <section class="section"><div class="section-head"><h2>سرویس‌های شما</h2><button onclick="setTab('services')">مشاهده همه</button></div>${serviceList(d.subscriptions.slice(0,3))}</section>
 <section class="section"><div class="section-head"><h2>آخرین خبرها</h2><button onclick="renderNews()">همه خبرها</button></div>${newsList(state.data.news.slice(0,2))}</section>`;
}
function serviceList(list){if(!list?.length)return `<div class="empty"><span class="big">${icon("empty")}</span><strong>سرویسی ندارید</strong></div>`;return `<div class="service-list">${list.map(s=>`<button class="service-mini" onclick="openService(${s.id})"><div class="service-icon">${icon("vpn")}</div><div class="grow"><strong>${esc(s.name)}</strong><small>${statusFa(s.status)} · ${num(s.remaining_days)} روز · ${num(s.remaining_gb)} GB</small></div><span class="chev">‹</span></button>`).join('')}</div>`}
function services(){return `<div class="detail-head"><div><h1 class="page-title">سرویس‌ها</h1><p class="page-subtitle">سرویس‌های فعال و پلن‌های قابل خرید</p></div></div><div class="section">${serviceList(state.data.dashboard.subscriptions)}</div><div class="section"><div class="section-head"><h2>پلن‌های VPN</h2></div><div class="plan-grid">${state.data.plans.map(planCard).join('')}</div></div>`}
function planCard(p){return `<article class="plan ${p.popular?'popular':''}">${p.popular?'<span class="badge">محبوب‌ترین</span>':''}<h3>${esc(p.name)}</h3><p class="desc">${esc(p.description||'سرویس سریع و پایدار برای استفاده روزمره.')}</p><div class="specs"><span class="spec">${num(p.volume_gb)} GB</span><span class="spec">${num(p.duration_days)} روز</span><span class="spec">${p.hwid_limit?num(p.hwid_limit)+' دستگاه':'دستگاه نامحدود'}</span></div><div class="price"><strong>${money(p.price).replace(' تومان','')}</strong><span>تومان</span></div><button class="btn primary" style="width:100%" onclick="buyPlan(${p.id})">انتخاب پلن</button></article>`}
function wallet(){const w=state.data.wallet;return `<h1 class="page-title">کیف پول</h1><p class="page-subtitle">پرداخت سریع و امن، بدون خروج از تلگرام.</p><section class="wallet-card"><div class="eyebrow">موجودی فعلی</div><div class="balance">${money(w.balance)}</div><div class="wallet-actions"><button class="btn primary" onclick="topup()">افزایش موجودی</button><button class="btn" onclick="showTransactions()">تراکنش‌ها</button></div></section><section class="section"><div class="section-head"><h2>آخرین تراکنش‌ها</h2></div>${transactions(w.transactions.slice(0,8))}</section>`}
function transactions(list){if(!list?.length)return `<div class="empty"><span class="big">${icon("wallet")}</span><strong>هنوز تراکنشی ندارید</strong></div>`;return list.map(t=>`<div class="tx"><div class="tx-icon">${t.type==='purchase'?icon("purchase"):t.type==='refund'?icon("refund"):icon("plus")}</div><div class="grow"><strong>${esc(t.description||'تراکنش')}</strong><small>${new Date(t.created_at).toLocaleDateString('fa-IR')}</small></div><div class="amount ${Number(t.amount)>=0?'positive':'negative'}">${Number(t.amount)>=0?'+':''}${num(t.amount)}</div></div>`).join('')}
function rewards(){const l=state.data.loyalty;const next=l.next_min?num(l.next_min-l.points):'∞';return `<h1 class="page-title">باشگاه مشتریان</h1><p class="page-subtitle">با خرید و دعوت دوستان، امتیاز جمع کن.</p><section class="reward-card"><div class="level"><div><div class="eyebrow">سطح فعلی</div><strong>${esc(l.level)}</strong></div><span class="pill">${num(l.points)} امتیاز</span></div><div class="progress"><i style="width:${Math.round(l.progress*100)}%"></i></div><div class="eyebrow" style="margin-top:9px">${l.next_min?num(next)+' امتیاز تا سطح بعدی':'بالاترین سطح'}</div></section><section class="section"><div class="section-head"><h2>چطور امتیاز بگیرم؟</h2></div><div class="grid"><div class="metric"><span>خرید</span><strong>امتیاز</strong><em>با هر خرید</em></div><div class="metric"><span>تمدید</span><strong>Bonus</strong><em>پاداش وفاداری</em></div><div class="metric"><span>دعوت دوست</span><strong>پاداش</strong><em>برای هر دعوت</em></div><div class="metric"><span>کمپین</span><strong>ویژه</strong><em>امتیاز بیشتر</em></div></div></section><section class="section"><div class="section-head"><h2>دعوت دوستان</h2></div><div class="reward-card"><strong>${num(state.data.referrals.total)} دعوت</strong><p class="page-subtitle">${num(state.data.referrals.active)} کاربر فعال</p>${state.data.referrals.link?`<div class="ref-link"><input id="refInput" readonly value="${esc(state.data.referrals.link)}"><button class="btn primary" onclick="copyRef()">کپی</button></div>`:'<p class="page-subtitle">BOT_USERNAME را در محیط تنظیم کنید تا لینک دعوت نمایش داده شود.</p>'}</div></section>`}
function profile(){const u=state.data.user;const initial=(u.first_name||'ی').slice(0,1);return `<h1 class="page-title">پروفایل</h1><p class="page-subtitle">حساب تلگرامی شما</p><section class="profile"><div class="avatar">${u.photo_url?`<img src="${esc(u.photo_url)}" style="width:100%;height:100%;border-radius:inherit;object-fit:cover">`:esc(initial)}</div><div><h2>${esc(u.first_name||'کاربر')} ${esc(u.last_name||'')}</h2><p>${u.username?'@'+esc(u.username):'کاربر تلگرام'} · ID ${num(u.telegram_id)}</p></div></section><div class="menu-list"><button class="menu-item" onclick="renderNotifications()"><span>◌</span><span class="grow"><strong>اعلان‌ها</strong><small>${num(state.data.notifications.unread)} اعلان خوانده‌نشده</small></span><span>‹</span></button><button class="menu-item" onclick="renderNews()"><span>▣</span><span class="grow"><strong>اخبار و اطلاعیه‌ها</strong><small>آخرین اتفاقات سرویس</small></span><span>‹</span></button><button class="menu-item" onclick="faq()"><span>?</span><span class="grow"><strong>راهنما و پشتیبانی</strong><small>سوالات متداول و ارتباط با پشتیبانی</small></span><span>‹</span></button></div>`}
function newsList(list){if(!list?.length)return `<div class="empty"><span class="big">▣</span><strong>خبری نیست</strong></div>`;return `<div class="news-list">${list.map(n=>`<article class="news-card" onclick="openNews(${n.id})">${n.image_url?`<img src="${esc(n.image_url)}" onerror="this.style.display='none'">`:''}<div class="copy"><h3>${esc(n.title)}</h3><p>${esc(n.summary||'')}</p></div></article>`).join('')}</div>`}
function renderNews(){app.innerHTML=`<div class="detail-head"><button class="back" onclick="render()">›</button><div><h1 class="page-title">اخبار</h1><p class="page-subtitle">آخرین خبرها و اطلاعیه‌ها</p></div></div>${newsList(state.data.news)}`}
function renderNotifications(){const n=state.data.notifications;app.innerHTML=`<div class="detail-head"><button class="back" onclick="render()">›</button><div><h1 class="page-title">اعلان‌ها</h1><p class="page-subtitle">${num(n.unread)} مورد خوانده‌نشده</p></div></div><div class="service-list">${n.items.length?n.items.map(x=>`<button class="menu-item" onclick="readNotif(${x.id})"><span>${x.is_read?'○':'●'}</span><span class="grow"><strong>${esc(x.title)}</strong><small>${esc(x.body)}</small></span></button>`).join(''):`<div class="empty"><span class="big">✓</span><strong>همه‌چیز مرتب است</strong><span>اعلان جدیدی ندارید.</span></div>`}</div>`}
function openNews(id){const n=state.data.news.find(x=>x.id===id);if(!n)return;showSheet(`<h2>${esc(n.title)}</h2>${n.image_url?`<img src="${esc(n.image_url)}" style="width:100%;border-radius:16px;margin-bottom:12px">`:''}<p style="color:var(--muted);font-size:13px;line-height:2">${esc(n.content||n.summary||'')}</p>`)}
function openService(id){api('/subscriptions/'+id).then(d=>{const s=d.subscription;const p=Number(s.total_bytes||0),r=Number(s.remaining_bytes??0);const percent=p?Math.round(r/p*100):100;showSheet(`<h2>${esc(s.name)}</h2><span class="pill">${statusFa(s.status)}</span><div class="kv"><div><span>حجم باقی‌مانده</span><strong>${s.remaining_bytes==null?num(s.remaining_gb)+' GB':num((r/1073741824).toFixed(2))+' GB'}</strong></div><div><span>زمان باقی‌مانده</span><strong>${num(s.remaining_days)} روز</strong></div><div><span>نام کاربری</span><strong>${esc(s.vpn_username||'—')}</strong></div><div><span>درصد باقی‌مانده</span><strong>${percent}%</strong></div></div>${s.subscription_link?`<div class="link-box">${esc(s.subscription_link)}</div><div class="actions"><button class="btn primary" onclick="copyText('${esc(s.subscription_link)}')">کپی لینک</button><button class="btn" onclick="openQR(${s.id},'${esc(s.subscription_link)}')">QR Code</button></div>`:''}`)}).catch(e=>toast(e.message))}
function openQR(id,link){api('/subscriptions/'+id).then(d=>{const q=d.subscription.qr_data_url;showSheet(`<h2>QR Code اتصال</h2><div style="text-align:center">${q?`<img src="${q}" style="width:240px;height:240px;background:#fff;border-radius:18px;padding:10px">`:`<div class="empty">QR در دسترس نیست</div>`}<button class="btn primary" style="width:100%;margin-top:14px" onclick="copyText('${esc(link)}')">کپی لینک</button></div>`)}).catch(()=>toast('QR در دسترس نیست'))}
function buyPlan(id){const p=state.data.plans.find(x=>x.id===id);if(!p)return;const panels=p.panels||[];showSheet(`<h2>تأیید خرید</h2><div class="detail-card"><strong>${esc(p.name)}</strong><div class="kv"><div><span>حجم</span><strong>${num(p.volume_gb)} GB</strong></div><div><span>مدت</span><strong>${num(p.duration_days)} روز</strong></div><div><span>قیمت</span><strong>${money(p.price)}</strong></div><div><span>کیف پول</span><strong>${money(state.data.dashboard.balance)}</strong></div></div></div>${panels.length>1?`<div class="form-row"><label>لوکیشن</label><select id="panelSel">${panels.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('')}</select></div>`:''}<div class="form-row"><label>کد تخفیف (اختیاری)</label><input id="coupon" placeholder="مثلاً UNIQUE20"></div><button class="btn primary" style="width:100%" onclick="confirmBuy(${id})">پرداخت و فعال‌سازی</button>`)}
async function confirmBuy(id){const p=state.data.plans.find(x=>x.id===id);const key=crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random();const panel=document.getElementById('panelSel')?.value;try{const d=await api('/orders',{method:'POST',headers:{'Idempotency-Key':key},body:JSON.stringify({product_id:id,panel_id:panel?Number(panel):undefined,coupon_code:document.getElementById('coupon')?.value||''})});closeSheet();haptic('medium');toast('سرویس با موفقیت فعال شد 🎉');await refresh();if(d.provision?.subscription_link)openService(d.order.id)}catch(e){toast(e.message)}}
function topup(){showSheet(`<h2>افزایش موجودی</h2><div class="form-row"><label>مبلغ به تومان</label><input id="topupAmount" type="number" inputmode="numeric" placeholder="مثلاً 200000"></div><button class="btn primary" style="width:100%" onclick="confirmTopup()">ادامه</button>`)}
async function confirmTopup(){try{const d=await api('/wallet/topup',{method:'POST',body:JSON.stringify({amount:Number(document.getElementById('topupAmount').value)})});showSheet(`<h2>واریز ${money(d.card?document.getElementById('topupAmount').value:0)}</h2><p class="page-subtitle">مبلغ را به کارت زیر واریز کنید، سپس رسید را در ربات ارسال کنید.</p><div class="detail-card"><strong>${esc(d.card.card_number)}</strong><p class="page-subtitle">${esc(d.card.owner_name)}${d.card.bank_name?' · '+esc(d.card.bank_name):''}</p></div><button class="btn primary" style="width:100%;margin-top:12px" onclick="copyText('${esc(d.card.card_number)}')">کپی شماره کارت</button>`)}catch(e){toast(e.message)}}
function showTransactions(){showSheet(`<h2>تاریخچه تراکنش‌ها</h2>${transactions(state.data.wallet.transactions)}`)}
function copyText(t){navigator.clipboard?.writeText(t).then(()=>toast('کپی شد')).catch(()=>toast('امکان کپی خودکار نیست'))}
function copyRef(){const t=document.getElementById('refInput')?.value;copyText(t)}
function bannerClick(link){if(!link)return;try{tg?.openLink(link)}catch(e){location.href=link}}
async function readNotif(id){try{await api('/notifications/read',{method:'POST',body:JSON.stringify({id})});await refresh();renderNotifications()}catch(e){toast(e.message)}}
function faq(){showSheet(`<h2>پشتیبانی و راهنما</h2><div class="menu-list"><button class="menu-item"><span class="menu-ico">${icon("vpn")}</span><span class="grow"><strong>مشکل اتصال دارم</strong><small>راهنمای اتصال و عیب‌یابی</small></span></button><button class="menu-item"><span class="menu-ico">${icon("help")}</span><span class="grow"><strong>سوالات متداول</strong><small>خرید، پرداخت، حجم و تمدید</small></span></button><button class="menu-item"><span class="menu-ico">${icon("telegram")}</span><span class="grow"><strong>پشتیبانی تلگرام</strong><small>ارتباط مستقیم با پشتیبانی</small></span></button></div>`)}
function render(){if(!state.data)return; if(state.tab==='home')app.innerHTML=home();else if(state.tab==='services')app.innerHTML=services();else if(state.tab==='wallet')app.innerHTML=wallet();else if(state.tab==='rewards')app.innerHTML=rewards();else app.innerHTML=profile()}
async function refresh(){
  closeSheet();
  state.data = await api('/bootstrap');
  if(state.data.theme) applyTheme(state.data.theme);
  const unread = (state.data.notifications && state.data.notifications.unread) || 0;
  let badge = document.getElementById('notifyBadge');
  if(!badge){
    const nb=document.getElementById('notifyBtn');
    if(nb){ nb.insertAdjacentHTML('beforeend','<b id="notifyBadge" hidden>0</b>'); badge=document.getElementById('notifyBadge'); }
  }
  if(badge){ badge.hidden = !(unread>0); badge.textContent = num(unread); }
  if(loading && loading.parentNode) loading.remove();
  render();
}
refresh().catch(e=>{
  closeSheet();
  const msg = (e && e.message) ? String(e.message) : 'خطای ناشناخته';
  const hint = !initData()
    ? 'این صفحه را از داخل تلگرام با دکمه مینی‌اپ باز کنید.\n(در مرورگر معمولی initData وجود ندارد.)'
    : msg;
  if(loading){
    loading.innerHTML = '<div class="empty"><span class="big">!</span><strong>اتصال برقرار نشد</strong><span style="white-space:pre-wrap;display:block;margin-top:8px">'+esc(hint)+'</span><button class="btn primary" style="margin-top:15px" type="button" onclick="location.reload()">تلاش دوباره</button></div>';
  }
  console.error('miniapp bootstrap failed', e);
});
