const tg = window.Telegram?.WebApp;
if(tg){
  try{ tg.ready(); tg.expand();
    tg.setHeaderColor(tg.themeParams?.bg_color || '#090910');
    tg.setBackgroundColor(tg.themeParams?.bg_color || '#090910');
  }catch(e){}
}
const state={data:null,tab:'home',buy:null,ticketPoll:null};

const ICONS = {
  home: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 10.8 12 3.7l8.5 7.1"/><path d="M5.5 10v9.3h13V10"/><path d="M9.2 19.3v-5.8h5.6v5.8"/></svg>',
  services: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="4" width="17" height="5.8" rx="1.8"/><rect x="3.5" y="14.2" width="17" height="5.8" rx="1.8"/><path d="M7 6.9h.01M7 17.1h.01"/></svg>',
  wallet: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7.2h14.2A1.8 1.8 0 0 1 20 9v9.2A1.8 1.8 0 0 1 18.2 20H5.8A2.8 2.8 0 0 1 3 17.2V6.8A2.8 2.8 0 0 1 5.8 4H18a2 2 0 0 1 2 2"/><path d="M20 11.5h-6.1a2.3 2.3 0 0 0 0 4.6H20"/><path d="M15.9 13.8h.01"/></svg>',
  rewards: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.4 14.4 8l5.1.7-3.7 3.6.9 5.1-4.7-2.4-4.7 2.4.9-5.1-3.7-3.6L9.6 8 12 3.4Z"/><path d="M8.2 19.8h7.6"/></svg>',
  profile: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="7.8" r="3.4"/><path d="M5 20c1.5-3.6 3.8-5.3 7-5.3s5.5 1.7 7 5.3"/></svg>',
  bell: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.2 10a5.8 5.8 0 0 1 11.6 0c0 5.9 2.5 6.7 2.5 6.7H3.7S6.2 15.9 6.2 10Z"/><path d="M9.8 20h4.4"/></svg>',
  vpn: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5 19 6v5.1c0 4.4-2.7 7.6-7 9.4-4.3-1.8-7-5-7-9.4V6l7-2.5Z"/><path d="m8.6 12 2.2 2.2 4.7-4.7"/></svg>',
  empty: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v14H5z"/><path d="M8 9h8M8 12h5M8 15h3"/></svg>',
  purchase: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14l-1.2 15H6.2L5 4Z"/><path d="M9 4a3 3 0 0 0 6 0M8.2 10h7.6M8.2 13h5.2"/></svg>',
  refund: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 7 5 11l4 4"/><path d="M5 11h8a5.5 5.5 0 0 1 5.5 5.5V19"/></svg>',
  plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
  help: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M9.7 9.3a2.4 2.4 0 1 1 3.8 2c-.9.6-1.5 1.1-1.5 2.2M12 16.8h.01"/></svg>',
  telegram: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m20.3 4.2-3.1 15.1c-.2 1-.8 1.2-1.6.8l-4.4-3.2-2.1 2c-.2.2-.4.4-.8.4l.3-4.5 8.2-7.4c.4-.4-.1-.6-.6-.2L6 13.8l-4.3-1.4c-.9-.3-.9-.9.2-1.3L18.7 3c.8-.3 1.8.4 1.6 1.2Z"/></svg>',
  support: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12a8 8 0 0 1 16 0"/><path d="M4 12v3.2A2.8 2.8 0 0 0 6.8 18H8v-6H6.8A2.8 2.8 0 0 0 4 14.8"/><path d="M20 12v3.2a2.8 2.8 0 0 1-2.8 2.8H16v-6h1.2a2.8 2.8 0 0 1 2.8 2.8"/></svg>',
  card: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M7 15h4"/></svg>',
  back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 6 8 12l6 6"/><path d="M8 12h12"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7.5V3.8h-3.7"/><path d="M20 3.8a8.5 8.5 0 1 0 1 9.2"/></svg>',
  power: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v9"/><path d="M7.5 6.2a7 7 0 1 0 9 0"/></svg>',
  key: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="8" cy="14" r="4"/><path d="M11.5 12.5 20 4"/><path d="M16 5.5 18.5 8"/></svg>',
  clock: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 8v5l3 2"/></svg>',
  edit: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4l10-10-4-4L4 16v4Z"/><path d="m12.5 7.5 4 4"/></svg>',
  trash: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14"/><path d="M9 7V5h6v2"/><path d="m8 7 1 12h6l1-12"/></svg>',
  gift: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 11h16v9H4z"/><path d="M3 7h18v4H3z"/><path d="M12 7v13"/><path d="M12 7c-1.5-2.5-4-2.5-4 0"/><path d="M12 7c1.5-2.5 4-2.5 4 0"/></svg>'
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
  const brand = document.querySelector('.brand');
  if(brand){
    const mark = brand.querySelector('.brand-mark');
    const strong = brand.querySelector('strong');
    const small = brand.querySelector('small');
    if(theme.logo_url){
      if(mark){
        mark.classList.add('has-logo');
        mark.innerHTML = '<img src="'+esc(theme.logo_url)+'" alt="" loading="eager">';
      }
    } else if(mark && theme.brand_mark){
      mark.classList.remove('has-logo');
      mark.textContent = theme.brand_mark;
    }
    if(strong && theme.brand_name) strong.textContent = theme.brand_name;
    if(small && theme.brand_sub) small.textContent = theme.brand_sub;
  }
  const tabs = document.querySelectorAll('.bottom-nav button');
  const labels = [theme.tab_home, theme.tab_services, theme.tab_wallet, theme.tab_rewards, theme.tab_profile];
  const iconKeys = ['home','services','wallet','rewards','profile'];
  tabs.forEach((btn,i)=>{
    const lab = labels[i] || btn.querySelector('small')?.textContent;
    btn.innerHTML = '<span class="nav-ico">'+ICONS[iconKeys[i]]+'</span><small>'+esc(lab)+'</small>';
    if(iconKeys[i]==='rewards' && theme.show_rewards==='0') btn.style.display='none';
    else btn.style.display='';
  });
  const nb = document.getElementById('notifyBtn');
  if(nb){
    const badge = document.getElementById('notifyBadge');
    nb.innerHTML = ICONS.bell + (badge ? badge.outerHTML : '');
  }
  let st = document.getElementById('themeCustomCss');
  if(!st){ st=document.createElement('style'); st.id='themeCustomCss'; document.head.appendChild(st); }
  st.textContent = theme.custom_css || '';
}

const app=document.getElementById('app');
const loading=document.getElementById('loading');
const API_BASE = (location.pathname.indexOf('/miniapp')===0 ? '' : '') + '/miniapp/api';

function initData(){
  try{ if(tg && tg.initData) return tg.initData; }catch(e){}
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
function toast(s){const e=document.getElementById('toast');e.textContent=s;e.classList.add('show');setTimeout(()=>e.classList.remove('show'),2800)}
function haptic(type='light'){try{tg?.HapticFeedback?.impactOccurred(type)}catch(e){}}
let _busyTimer=null;
function showBusy(title, sub){
  const ov=document.getElementById('busyOverlay');
  if(!ov) return;
  document.getElementById('busyTitle').textContent=title||'در حال انجام...';
  document.getElementById('busySub').textContent=sub||'لطفاً صبر کنید';
  ov.hidden=false; ov.setAttribute('aria-hidden','false');
  try{tg?.MainButton?.showProgress()}catch(e){}
}
function hideBusy(){
  const ov=document.getElementById('busyOverlay');
  if(ov){ ov.hidden=true; ov.setAttribute('aria-hidden','true'); }
  try{tg?.MainButton?.hideProgress()}catch(e){}
  if(_busyTimer){ clearTimeout(_busyTimer); _busyTimer=null; }
}
async function withBusy(title, sub, fn){
  showBusy(title, sub);
  try{ return await fn(); }
  finally{ hideBusy(); }
}
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
  closeSheet();
})();
function setTab(tab){state.tab=tab;document.querySelectorAll('.bottom-nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));render()}
document.querySelectorAll('.bottom-nav button').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
document.getElementById('notifyBtn').onclick=()=>renderNotifications();

function usagePercent(s){if(!s)return 0; const total=Number(s.volume_gb||0); const rem=Number(s.remaining_gb??total); return total?Math.max(0,Math.min(100,(rem/total)*100)):100}
function statusFa(s){return ({active:'فعال',provisioned:'فعال',expired:'منقضی',suspended:'معلق',no_subscription:'بدون سرویس',pending_review:'در انتظار تایید',waiting_receipt:'منتظر رسید',pending_payment:'در انتظار پرداخت'})[s]||s||'—'}

/* ===================== HOME ===================== */
function home(){
 const d=state.data.dashboard, s=d.subscription, p=usagePercent(s);
 const b=state.data.banners?.[0];
 return `<h1 class="page-title">سلام ${esc(state.data.user.first_name||'دوست من')}</h1>
<p class="page-subtitle">همه‌چیز برای مدیریت سرویس شما، همین‌جاست.</p>
<section class="hero">
<div class="status-row"><div><div class="eyebrow">وضعیت سرویس</div><div class="status">${s? 'سرویس شما فعال است':'هنوز سرویسی ندارید'}</div></div><span class="pill">${statusFa(d.status)}</span></div>
  ${s?`<div class="usage"><div class="ring" style="--p:${p}"><div class="ring-inner"><strong>${Math.round(p)}%</strong><small>باقی‌مانده</small></div></div><div class="usage-copy"><strong>${num(s.remaining_gb)} GB</strong><span>از ${num(s.volume_gb)} GB</span><span>${num(s.remaining_days)} روز باقی‌مانده</span></div></div>
<div class="actions"><button class="btn primary" onclick="openService(${s.id})">مدیریت سرویس</button><button class="btn" onclick="startBuyFlow()">خرید سرویس جدید</button></div>`
  :`<div class="empty"><span class="big">${icon("vpn")}</span><strong>اولین سرویس خودت را فعال کن</strong><span>پلن مناسب را انتخاب کن و در چند قدم کوتاه شروع کن.</span></div><div class="actions"><button class="btn primary" onclick="startBuyFlow()">خرید سرویس جدید</button></div>`}
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

function serviceList(list){
  if(!list?.length)return `<div class="empty"><span class="big">${icon("empty")}</span><strong>سرویسی ندارید</strong></div>`;
  return `<div class="service-list">${list.map(s=>`<button class="service-mini" onclick="openService(${s.id})"><div class="service-icon">${icon("vpn")}</div><div class="grow"><strong>${esc(s.name)}</strong><small>${statusFa(s.status)} · ${num(s.remaining_days)} روز · ${num(s.remaining_gb)} GB</small></div><span class="chev"></span></button>`).join('')}</div>`;
}

/* ===================== SERVICES + BUY FLOW ===================== */
function services(){
  return `<div class="detail-head"><div><h1 class="page-title">سرویس‌ها</h1><p class="page-subtitle">سرویس‌های فعال و خرید سرویس جدید</p></div></div>
<div class="actions" style="margin-bottom:16px"><button class="btn primary" style="width:100%" onclick="startBuyFlow()">خرید سرویس جدید</button></div>
<div class="section"><div class="section-head"><h2>سرویس‌های من</h2></div>${serviceList(state.data.dashboard.subscriptions)}</div>`;
}

/* Step-by-step buy */
async function startBuyFlow(){
  state.buy = {step:1, panel_id:null, category_id:null, product_id:null, mode:null, order:null};
  try{
    const d = await api('/catalog/panels');
    if(!d.panels?.length){ toast('فعلاً پنلی فعال نیست'); return; }
    state.buy.panels = d.panels;
    renderBuyStep();
  }catch(e){ toast(e.message); }
}

function renderBuyStep(){
  const b = state.buy;
  if(!b) return;
  if(b.step===1){
    showSheet(`<h2>خرید سرویس جدید</h2>
<p class="page-subtitle">۱ — سرویس شما کجا ارائه می‌شود؟</p>
<div class="menu-list">${b.panels.map(p=>`
<button class="menu-item" onclick="buySelectPanel(${p.id})">
<span class="menu-ico">${icon('vpn')}</span>
<span class="grow"><strong>${esc(p.name)}</strong><small>${esc(p.description||'انتخاب پنل')}</small></span>
<span class="chev"></span>
</button>`).join('')}
</div>`);
  } else if(b.step===2){
    showSheet(`<h2>خرید سرویس جدید</h2>
<p class="page-subtitle">۲ — دسته‌بندی مناسب را انتخاب کنید</p>
<div class="menu-list">
        ${(b.categories||[]).map(c=>`
<button class="menu-item" onclick="buySelectCat(${c.id})">
<span class="menu-ico"></span>
<span class="grow"><strong>${esc(c.name)}</strong></span>
<span class="chev"></span>
</button>`).join('')}
        ${b.has_uncategorized?`<button class="menu-item" onclick="buySelectCat(0)"><span class="menu-ico"></span><span class="grow"><strong>همه محصولات</strong></span><span class="chev"></span></button>`:''}
<button class="btn" style="width:100%;margin-top:8px" onclick="state.buy.step=1;renderBuyStep()">بازگشت</button>
</div>`);
  } else if(b.step===3){
    showSheet(`<h2>خرید سرویس جدید</h2>
<p class="page-subtitle">۳ — محصول مورد نظر را انتخاب کنید</p>
<div class="plan-grid">${(b.products||[]).map(p=>`
<article class="plan">
<h3>${esc(p.name)}</h3>
<p class="desc">${esc(p.description||'')}</p>
<div class="specs">
<span class="spec spec-ico">${icon("vpn")} ${num(p.volume_gb)} GB</span>
<span class="spec spec-ico">${icon("clock")} ${num(p.duration_days)} روز</span>
${p.hwid_limit?`<span class="spec spec-ico">${icon("profile")} ${num(p.hwid_limit)} کاربر</span>`:`<span class="spec spec-ico">${icon("profile")} نامحدود</span>`}
${p.hourly_enabled?`<span class="spec spec-ico">${icon("card")} ساعتی ${money(p.hourly_price)}</span>`:''}
</div>
<div class="price"><strong>${money(p.price).replace(' تومان','')}</strong><span>تومان</span></div>
<button class="btn primary" style="width:100%" onclick="buySelectProduct(${p.id})">انتخاب</button>
</article>`).join('')||'<div class="empty">محصولی نیست</div>'}
<button class="btn" style="width:100%;margin-top:8px" onclick="state.buy.step=2;renderBuyStep()">بازگشت</button>
</div>`);
  } else if(b.step===4){
    renderBuyPayment();
  }
}

async function buySelectPanel(id){
  state.buy.panel_id = id;
  try{
    const d = await api('/catalog/categories?panel_id='+id);
    state.buy.categories = d.categories||[];
    state.buy.has_uncategorized = !!d.has_uncategorized;
    if(!state.buy.categories.length){
      // skip to products
      const pd = await api('/catalog/products?panel_id='+id);
      state.buy.products = pd.products||[];
      state.buy.step = 3;
    } else {
      state.buy.step = 2;
    }
    renderBuyStep();
  }catch(e){ toast(e.message); }
}

async function buySelectCat(cid){
  state.buy.category_id = cid||null;
  try{
    let url = '/catalog/products?panel_id='+state.buy.panel_id;
    if(cid) url += '&category_id='+cid;
    const d = await api(url);
    state.buy.products = d.products||[];
    state.buy.step = 3;
    renderBuyStep();
  }catch(e){ toast(e.message); }
}

async function buySelectProduct(pid){
  state.buy.product_id = pid;
  const p = (state.buy.products||[]).find(x=>x.id===pid);
  state.buy.product = p;
  state.buy.custom_name = null;
  if(p && p.ask_custom_name){
    showSheet(`<h2>${esc(p.name)}</h2>
<p class="page-subtitle">نام سرویس مورد نظرتان را بنویسید</p>
<div class="form-row"><label>نام سرویس</label><input id="buyCustomName" placeholder="مثلاً سرویس خانه" maxlength="100"></div>
<div class="actions" style="margin-top:14px">
<button class="btn primary" style="width:100%" onclick="buyAfterCustomName()">ادامه</button>
</div>
<button class="btn" style="width:100%;margin-top:8px" onclick="state.buy.step=3;renderBuyStep()">بازگشت</button>`);
    return;
  }
  await buyContinueAfterName();
}

async function buyAfterCustomName(){
  const name = (document.getElementById('buyCustomName')?.value||'').trim();
  if(name.length < 2){ toast('نام سرویس حداقل ۲ کاراکتر باشد'); return; }
  state.buy.custom_name = name.slice(0,100);
  await buyContinueAfterName();
}

async function buyContinueAfterName(){
  const p = state.buy.product;
  if(p && p.hourly_enabled){
    showSheet(`<h2>${esc(p.name)}</h2>
<p class="page-subtitle">نوع خرید را انتخاب کنید</p>
<div class="detail-card">
<div class="kv">
<div><span>کامل</span><strong>${money(p.price)} / ${num(p.duration_days)} روز</strong></div>
<div><span>ساعتی</span><strong>${money(p.hourly_price)} / ساعت</strong></div>
</div>
</div>
<div class="actions" style="margin-top:14px">
<button class="btn primary" onclick="buyChooseMode('full')">خرید کامل</button>
<button class="btn" onclick="buyChooseMode('hourly')">خرید ساعتی</button>
</div>
<div class="form-row"><label>کد تخفیف (اختیاری)</label><input id="buyCoupon" placeholder="مثلاً OFF20"></div>
<button class="btn" style="width:100%;margin-top:8px" onclick="state.buy.step=3;renderBuyStep()">بازگشت</button>`);
  } else {
    state.buy.mode = 'full';
    state.buy.step = 4;
    await prepareAndShowInvoice();
  }
}

async function buyChooseMode(mode){
  state.buy.mode = mode;
  state.buy.coupon = document.getElementById('buyCoupon')?.value||'';
  state.buy.step = 4;
  await prepareAndShowInvoice();
}

async function prepareAndShowInvoice(){
  try{
    const body = {
      product_id: state.buy.product_id,
      panel_id: state.buy.panel_id,
      mode: state.buy.mode||'full',
      coupon_code: state.buy.coupon||'',
      custom_name: state.buy.custom_name||''
    };
    const d = await api('/orders/prepare',{method:'POST',body:JSON.stringify(body)});
    if(d.mode==='hourly'){
      closeSheet(); haptic('medium'); toast(d.message||'سرویس ساعتی فعال شد');
      await refresh(); return;
    }
    state.buy.order = d;
    renderBuyPayment();
  }catch(e){ toast(e.message); }
}

function renderBuyPayment(){
  const o = state.buy.order;
  if(!o) return;
  const walletOk = !!o.can_pay_wallet;
  showSheet(`<h2>تأیید و پرداخت</h2>
<div class="detail-card">
<strong>${esc(o.product_name)}</strong>
<p class="page-subtitle">${esc(o.panel_name||'')}</p>
<div class="kv">
<div><span>قیمت</span><strong>${money(o.price)}</strong></div>
<div><span>تخفیف</span><strong>${money(o.discount||0)}</strong></div>
<div><span>مبلغ نهایی</span><strong>${money(o.final_price)}</strong></div>
<div><span>موجودی کیف پول</span><strong>${money(o.balance)}</strong></div>
<div><span>از کیف پول</span><strong>${money(o.wallet_used)}</strong></div>
<div><span>قابل پرداخت</span><strong>${money(o.pay_amount)}</strong></div>
</div>
</div>
<div class="form-row"><label>کد تخفیف</label>
<div style="display:flex;gap:8px">
<input id="invCoupon" placeholder="کد تخفیف" value="${esc(state.buy.coupon||'')}">
<button class="btn" onclick="applyBuyDiscount()">اعمال</button>
</div>
</div>
    ${walletOk
      ? `<p class="page-subtitle" style="margin-top:10px">با تایید، مبلغ از کیف پول کسر و سرویس ساخته می‌شود.</p>
<button class="btn primary" style="width:100%" onclick="confirmWalletBuy()">تایید و پرداخت از کیف پول</button>`
      : `<p class="page-subtitle" style="margin-top:10px">مبلغ ${money(o.wallet_used||0)} از کیف پول رزرو می‌شود و باقی‌مانده ${money(o.pay_amount)} را با یکی از روش‌های پرداخت زیر پرداخت کنید.</p>
${(o.payment_methods||[]).map(pm=>pm.key==='variza'?`<button class="btn primary" style="width:100%;margin-top:8px" onclick="startVarizaPay()">${esc(pm.title)}</button>`:pm.key==='card'?`<button class="btn" style="width:100%;margin-top:8px" onclick="startCardPay()">${esc(pm.title)}</button>`:'').join('')}`
    }
<button class="btn" style="width:100%;margin-top:8px" onclick="closeSheet()">انصراف</button>
    ${o.hourly_available?`<button class="btn" style="width:100%;margin-top:8px" onclick="buyChooseMode('hourly')">خرید ساعتی (${money(o.hourly_price)} / ساعت)</button>`:''}`);
}

async function applyBuyDiscount(){
  const code = document.getElementById('invCoupon')?.value||'';
  if(!code||!state.buy.order) return;
  try{
    const d = await api('/orders/'+state.buy.order.order_id+'/discount',{method:'POST',body:JSON.stringify({coupon_code:code})});
    state.buy.order = Object.assign({}, state.buy.order, d, {can_pay_wallet:d.can_pay_wallet, discount:d.discount, final_price:d.final_price, pay_amount:d.pay_amount, wallet_used:d.wallet_used});
    state.buy.coupon = code;
    toast(d.message||'تخفیف اعمال شد');
    renderBuyPayment();
  }catch(e){ toast(e.message); }
}

async function confirmWalletBuy(){
  if(!state.buy?.order) return;
  try{
    const d = await withBusy('در حال پرداخت و ساخت سرویس','ممکن است چند ثانیه طول بکشد',
      ()=>api('/orders/'+state.buy.order.order_id+'/confirm-wallet',{method:'POST',body:'{}'}));
    closeSheet(); haptic('medium'); toast(d.message||'خرید موفق');
    state.buy=null; await refresh();
  }catch(e){ toast(e.message); }
}

async function startVarizaPay(){
  if(!state.buy?.order) return;
  try{
    const d=await api('/orders/'+state.buy.order.order_id+'/pay-variza',{method:'POST',body:'{}'});
    window.open(d.pay_url,'_blank','noopener');
    showSheet(`<h2>پرداخت واریزا</h2><p class="page-subtitle">صفحه پرداخت باز شد. پس از پرداخت، تایید و ساخت سرویس به‌صورت خودکار انجام می‌شود و نیازی به ارسال رسید نیست.</p><button class="btn primary" style="width:100%" onclick="closeSheet();refresh()">بررسی وضعیت</button>`);
  }catch(e){toast(e.message)}
}

async function startCardPay(){
  if(!state.buy?.order) return;
  try{
    const d = await api('/orders/'+state.buy.order.order_id+'/pay-card',{method:'POST',body:'{}'});
    state.buy.card = d.card;
    state.buy.pay_amount = d.pay_amount;
    showSheet(`<h2>واریز کارت‌به‌کارت</h2>
<p class="page-subtitle">مبلغ ${money(d.pay_amount)} را واریز کنید، سپس تصویر رسید را آپلود کنید. همزمان در ربات هم پیام واریز برایتان ارسال شد.</p>
<div class="detail-card">
<strong style="font-size:18px;letter-spacing:1px">${esc(d.card.card_number)}</strong>
<p class="page-subtitle">${esc(d.card.owner_name||'')}${d.card.bank_name?' · '+esc(d.card.bank_name):''}</p>
</div>
<button class="btn" style="width:100%;margin-top:10px" onclick="copyText('${esc(d.card.card_number)}')">کپی شماره کارت</button>
<div class="form-row" style="margin-top:14px">
<label>تصویر رسید</label>
<input type="file" id="receiptFile" accept="image/*" capture="environment">
</div>
<button class="btn primary" style="width:100%" onclick="uploadBuyReceipt()">ارسال رسید برای تایید</button>`);
  }catch(e){ toast(e.message); }
}

function fileToBase64(file, onProgress){
  return new Promise((resolve,reject)=>{
    const r=new FileReader();
    r.onprogress=function(e){
      if(e.lengthComputable && onProgress) onProgress(Math.round(e.loaded/e.total*100));
    };
    r.onload=()=>{ if(onProgress) onProgress(100); resolve(r.result); };
    r.onerror=reject;
    r.readAsDataURL(file);
  });
}
function showProgress(title){
  showSheet(`<h2>${esc(title||'در حال ارسال...')}</h2>
    <div class="progress" style="height:12px;margin:18px 0"><i id="upBar" style="width:0%"></i></div>
    <p class="page-subtitle" id="upLabel">۰٪</p>`);
}
function setProgress(pct){
  const bar=document.getElementById('upBar');
  const lab=document.getElementById('upLabel');
  if(bar) bar.style.width=Math.max(0,Math.min(100,pct))+'%';
  if(lab) lab.textContent=Math.round(pct)+'٪';
}

async function uploadBuyReceipt(){
  const f = document.getElementById('receiptFile')?.files?.[0];
  if(!f){ toast('تصویر رسید را انتخاب کنید'); return; }
  if(!state.buy?.order) return;
  try{
    showProgress('ارسال رسید خرید');
    const b64 = await fileToBase64(f, setProgress);
    setProgress(90);
    const d = await api('/orders/'+state.buy.order.order_id+'/receipt',{method:'POST',body:JSON.stringify({photo:b64})});
    setProgress(100);
    closeSheet(); haptic('medium'); toast(d.message||'رسید ثبت شد');
    state.buy=null; await refresh();
  }catch(e){ toast(e.message); }
}

/* ===================== SERVICE DETAIL ===================== */
function openService(id){
  api('/subscriptions/'+id).then(d=>{
    const s=d.subscription;
    const p=Number(s.total_bytes||0),r=Number(s.remaining_bytes??0);
    const percent=p?Math.round(r/p*100):100;
    showSheet(`<h2>${esc(s.name)}</h2>
<span class="pill">${statusFa(s.status)}</span>
<div class="kv">
<div><span>حجم باقی‌مانده</span><strong>${s.remaining_bytes==null?num(s.remaining_gb)+' GB':num((r/1073741824).toFixed(2))+' GB'}</strong></div>
<div><span>زمان باقی‌مانده</span><strong>${num(s.remaining_days)} روز</strong></div>
<div><span>نام کاربری</span><strong>${esc(s.vpn_username||'—')}</strong></div>
<div><span>درصد باقی‌مانده</span><strong>${percent}%</strong></div>
</div>
      ${s.subscription_link?`<div class="link-box">${esc(s.subscription_link)}</div>
<div class="actions">
<button class="btn primary" onclick="copyText('${esc(s.subscription_link)}')">کپی لینک</button>
<button class="btn" onclick="openQR(${s.id},'${esc(s.subscription_link)}')">QR Code</button>
</div>`:''}
<div class="menu-list" style="margin-top:14px">
        <button class="menu-item" onclick="svcAction(${s.id},'refresh')"><span class="menu-ico">${icon('refresh')}</span><span class="grow"><strong>بروزرسانی</strong><small>وضعیت زنده از پنل</small></span><span class="chev"></span></button>
        <button class="menu-item" onclick="svcAction(${s.id},'toggle')"><span class="menu-ico">${icon('power')}</span><span class="grow"><strong>خاموش / روشن</strong><small>قطع یا وصل سرویس</small></span><span class="chev"></span></button>
        <button class="menu-item" onclick="svcAction(${s.id},'reset')"><span class="menu-ico">${icon('key')}</span><span class="grow"><strong>بازنشانی اشتراک</strong><small>لینک و نشست جدید</small></span><span class="chev"></span></button>
        <button class="menu-item" onclick="svcAction(${s.id},'hourly_toggle')"><span class="menu-ico">${icon('clock')}</span><span class="grow"><strong>توقف / شروع ساعتی</strong><small>کنترل سرویس ساعتی</small></span><span class="chev"></span></button>
        <button class="menu-item" onclick="svcRename(${s.id})"><span class="menu-ico">${icon('edit')}</span><span class="grow"><strong>تغییر نام</strong><small>نام نمایشی سرویس</small></span><span class="chev"></span></button>
        <button class="menu-item" onclick="svcDeleteConfirm(${s.id})"><span class="menu-ico">${icon('trash')}</span><span class="grow"><strong>حذف سرویس</strong><small>حذف از لیست و پنل</small></span><span class="chev"></span></button>
      </div>`);
  }).catch(e=>toast(e.message));
}
function openQR(id,link){
  api('/subscriptions/'+id).then(d=>{
    const q=d.subscription.qr_data_url;
    showSheet(`<h2>QR Code اتصال</h2><div style="text-align:center">${q?`<img src="${q}" style="width:240px;height:240px;background:#fff;border-radius:18px;padding:10px">`:`<div class="empty">QR در دسترس نیست</div>`}
<button class="btn primary" style="width:100%;margin-top:14px" onclick="copyText('${esc(link)}')">کپی لینک</button></div>`);
  }).catch(()=>toast('QR در دسترس نیست'));
}
async function svcAction(id, action){
  try{
    const d = await api('/subscriptions/'+id+'/action',{method:'POST',body:JSON.stringify({action})});
    toast(d.message||'انجام شد');
    if(action==='refresh'||action==='link') openService(id);
    else { await refresh(); openService(id); }
  }catch(e){ toast(e.message); }
}
function svcRename(id){
  showSheet(`<h2>تغییر نام سرویس</h2>
<div class="form-row"><label>نام جدید</label><input id="svcNewName" placeholder="مثلاً لپ‌تاپ"></div>
<button class="btn primary" style="width:100%" onclick="doRename(${id})">ذخیره</button>`);
}
function svcDeleteConfirm(id){
  showSheet(`<h2>حذف سرویس</h2>
    <p class="page-subtitle">آیا مطمئن هستید؟ سرویس از لیست شما حذف می‌شود و در پنل هم غیرفعال/حذف خواهد شد.</p>
    <button class="btn primary" style="width:100%;background:var(--danger)" onclick="svcDelete(${id})">بله، حذف شود</button>
    <button class="btn" style="width:100%;margin-top:8px" onclick="openService(${id})">انصراف</button>`);
}
async function svcDelete(id){
  try{
    const d=await api('/subscriptions/'+id+'/delete',{method:'POST',body:JSON.stringify({confirm:true})});
    toast(d.message||'حذف شد'); closeSheet(); await refresh(); setTab('services');
  }catch(e){toast(e.message)}
}
async function doRename(id){
  const name=document.getElementById('svcNewName')?.value||'';
  try{
    const d=await api('/subscriptions/'+id+'/action',{method:'POST',body:JSON.stringify({action:'rename',name})});
    toast(d.message); await refresh(); openService(id);
  }catch(e){toast(e.message)}
}

/* ===================== WALLET ===================== */
function wallet(){
  const w=state.data.wallet;
  return `<h1 class="page-title">کیف پول</h1><p class="page-subtitle">پرداخت سریع و امن، بدون خروج از تلگرام.</p>
<section class="wallet-card"><div class="eyebrow">موجودی فعلی</div><div class="balance">${money(w.balance)}</div>
<div class="wallet-actions"><button class="btn primary" onclick="topup()">افزایش موجودی</button><button class="btn" onclick="showTransactions()">تراکنش‌ها</button></div></section>
<section class="section"><div class="section-head"><h2>آخرین تراکنش‌ها</h2></div>${transactions(w.transactions.slice(0,8))}</section>`;
}
function transactions(list){
  if(!list?.length)return `<div class="empty"><span class="big">${icon("wallet")}</span><strong>هنوز تراکنشی ندارید</strong></div>`;
  return list.map(t=>`<div class="tx"><div class="tx-icon">${t.type==='purchase'?icon("purchase"):t.type==='refund'?icon("refund"):icon("plus")}</div><div class="grow"><strong>${esc(t.description||'تراکنش')}</strong><small>${new Date(t.created_at).toLocaleDateString('fa-IR')}</small></div><div class="amount ${Number(t.amount)>=0?'positive':'negative'}">${Number(t.amount)>=0?'+':''}${num(t.amount)}</div></div>`).join('');
}
function topup(){
  showSheet(`<h2>افزایش موجودی</h2>
<div class="form-row"><label>مبلغ به تومان</label><input id="topupAmount" type="number" inputmode="numeric" placeholder="مثلاً 200000"></div>
<button class="btn primary" style="width:100%" onclick="confirmTopup()">ادامه</button>`);
}
async function confirmTopup(){
  try{
    const amount=Number(document.getElementById('topupAmount').value);
    const d=await api('/wallet/topup',{method:'POST',body:JSON.stringify({amount})});
    state.pendingChargeId = d.charge_id;
    const methods=(d.payment_methods||[]);
    const cards=d.card?`<div class="detail-card"><strong>${esc(d.card.card_number)}</strong><p class="page-subtitle">${esc(d.card.owner_name||'')}${d.card.bank_name?' · '+esc(d.card.bank_name):''}</p></div>`:'';
    const buttons=methods.map(pm=>pm.key==='variza'?`<button class="btn primary" style="width:100%;margin-top:8px" onclick="startTopupVariza(${d.charge_id},${amount})">${esc(pm.title)}</button>`:pm.key==='card'?`${cards}<button class="btn" style="width:100%;margin-top:10px" onclick="copyText('${esc(d.card?.card_number||'')}')">کپی شماره کارت</button><div class="form-row" style="margin-top:12px"><label>تصویر رسید</label><input type="file" id="chargeReceipt" accept="image/*"></div><button class="btn primary" style="width:100%" onclick="uploadChargeReceipt()">ارسال رسید</button>`:'').join('');
    showSheet(`<h2>واریز ${money(amount)}</h2><p class="page-subtitle">روش پرداخت را انتخاب کنید.</p>${buttons}`);
  }catch(e){toast(e.message)}
}
async function startTopupVariza(chargeId,amount){
  try{
    const d=await api('/wallet/topup/variza',{method:'POST',body:JSON.stringify({amount,charge_id:chargeId})});
    window.open(d.pay_url,'_blank','noopener');
    showSheet(`<h2>پرداخت واریزا</h2><p class="page-subtitle">صفحه پرداخت باز شد. پس از پرداخت، شارژ کیف پول به‌صورت خودکار تایید می‌شود.</p><button class="btn primary" style="width:100%" onclick="closeSheet();refresh()">بررسی وضعیت</button>`);
  }catch(e){toast(e.message)}
}
async function uploadChargeReceipt(){
  const f=document.getElementById('chargeReceipt')?.files?.[0];
  if(!f||!state.pendingChargeId){toast('تصویر را انتخاب کنید');return}
  try{
    showProgress('ارسال رسید شارژ');
    const b64=await fileToBase64(f, setProgress);
    setProgress(90);
    const d=await api('/wallet/topup/receipt',{method:'POST',body:JSON.stringify({charge_id:state.pendingChargeId,photo:b64})});
    setProgress(100);
    closeSheet(); toast(d.message||'رسید ثبت شد');
  }catch(e){toast(e.message)}
}
function showTransactions(){showSheet(`<h2>تاریخچه تراکنش‌ها</h2>${transactions(state.data.wallet.transactions)}`)}

/* ===================== REWARDS / PROFILE ===================== */
function rewards(){
  const l=state.data.loyalty||{}; const ptsToNext=(l.points_to_next!=null)?Number(l.points_to_next):(l.next_min!=null?Math.max(0,Number(l.next_min)-Number(l.points||0)):null);
  return `<h1 class="page-title">باشگاه مشتریان</h1><p class="page-subtitle">با خرید و دعوت دوستان، امتیاز جمع کن.</p>
<section class="reward-card"><div class="level"><div><div class="eyebrow">سطح فعلی</div><strong>${esc(l.level)}</strong></div><span class="pill">${num(l.points)} امتیاز</span></div>
<div class="progress"><i style="width:${Math.round((l.progress||0)*100)}%"></i></div>
<div class="eyebrow" style="margin-top:9px">${ptsToNext!=null?(num(ptsToNext)+' امتیاز تا سطح بعدی'):'بالاترین سطح'}</div></section>
<div id="trialBox"></div>
<section class="section"><div class="section-head"><h2>دعوت دوستان</h2></div>
<div class="reward-card"><strong>${num(state.data.referrals.total)} دعوت</strong>
<p class="page-subtitle">${num(state.data.referrals.active)} کاربر فعال</p>
  ${state.data.referrals.link?`<div class="ref-link"><input id="refInput" readonly value="${esc(state.data.referrals.link)}"><button class="btn primary" onclick="copyRef()">کپی لینک</button></div>`:(state.data.referrals && state.data.referrals.bot_username===null?`<p class="page-subtitle">لینک دعوت در دسترس نیست.</p>`:`<p class="page-subtitle">لینک دعوت در دسترس نیست.</p>`)}
</div></section>
  ${Array.isArray(l.packages)&&l.packages.length?`<section class="section"><div class="section-head"><h2>بسته‌های امتیازی</h2></div>
<div class="plan-grid">${l.packages.map(pkg=>`<article class="plan">
<h3>${esc(pkg.title||'بسته')}</h3>
<p class="desc">${esc(pkg.description||'')}</p>
<div class="specs">
<span class="spec">${num(pkg.points_cost)} امتیاز</span>
${pkg.volume_gb?`<span class="spec spec-ico">${icon("vpn")} ${num(pkg.volume_gb)} GB</span>`:''}
${pkg.duration_days?`<span class="spec spec-ico">${icon("clock")} ${num(pkg.duration_days)} روز</span>`:''}
${pkg.hwid_limit?`<span class="spec spec-ico">${icon("profile")} ${num(pkg.hwid_limit)} کاربر</span>`:''}
${pkg.min_level?`<span class="spec">از سطح ${esc(pkg.min_level)}</span>`:''}
</div>
<button class="btn primary" style="width:100%" onclick="redeemPackage('${esc(pkg.id)}')">دریافت بسته</button>
</article>`).join('')}</div></section>`:''}`;
}
async function redeemPackage(id){
  try{
    const d=await withBusy('در حال فعال‌سازی بسته','ساخت سرویس ممکن است چند ثانیه طول بکشد',()=>api('/loyalty/redeem',{method:'POST',body:JSON.stringify({package_id:id})}));
    toast(d.message||'انجام شد'); await refresh(); setTab('rewards');
  }catch(e){toast(e.message)}
}

function profile(){
  const u=state.data.user;const initial=(u.first_name||'ی').slice(0,1);
  return `<h1 class="page-title">پروفایل</h1><p class="page-subtitle">حساب تلگرامی شما</p>
<section class="profile"><div class="avatar">${u.photo_url?`<img src="${esc(u.photo_url)}" style="width:100%;height:100%;border-radius:inherit;object-fit:cover">`:esc(initial)}</div>
<div><h2>${esc(u.first_name||'کاربر')} ${esc(u.last_name||'')}</h2><p>${u.username?'@'+esc(u.username):'کاربر تلگرام'} · ID ${num(u.telegram_id||u.id||"")}</p></div></section>
<div class="menu-list">
<button class="menu-item" onclick="renderNotifications()"><span class="menu-ico">${icon("bell")}</span><span class="grow"><strong>اعلان‌ها</strong><small>${num(state.data.notifications.unread)} خوانده‌نشده</small></span><span class="chev"></span></button>
<button class="menu-item" onclick="renderNews()"><span class="menu-ico">${icon("empty")}</span><span class="grow"><strong>اخبار</strong><small>اطلاعیه‌ها</small></span><span class="chev"></span></button>
<button class="menu-item" onclick="openSupport()"><span class="menu-ico">${icon('support')}</span><span class="grow"><strong>پشتیبانی و تیکت</strong><small>ارسال پیام و پیگیری</small></span><span class="chev"></span></button>
<button class="menu-item" onclick="startBuyFlow()"><span class="menu-ico">${icon('purchase')}</span><span class="grow"><strong>خرید سرویس جدید</strong><small>مرحله‌ای</small></span><span class="chev"></span></button>
</div>`;
}

/* ===================== SUPPORT / TICKETS ===================== */
async function openSupport(){
  try{
    const [deps, tickets] = await Promise.all([
      api('/support/departments'),
      api('/support/tickets')
    ]);
    state.support = {deps: deps.departments||[], tickets: tickets.tickets||[]};
    showSheet(`<h2>پشتیبانی</h2>
<div class="actions" style="margin-bottom:12px">
<button class="btn primary" style="width:100%" onclick="newTicket()">تیکت جدید</button>
</div>
<div class="section-head"><h2>تیکت‌های من</h2></div>
<div class="menu-list">${state.support.tickets.length?state.support.tickets.map(t=>`
<button class="menu-item" onclick="openTicket(${t.id})">
<span class="grow"><strong>#${t.id} · ${esc(t.subject||'تیکت')}</strong>
<small>${statusFa(t.status)} · ${new Date(t.updated_at||t.created_at).toLocaleDateString('fa-IR')}</small></span>
<span class="chev"></span>
</button>`).join(''):`<div class="empty"><strong>تیکتی ندارید</strong></div>`}
</div>`);
  }catch(e){toast(e.message)}
}
function newTicket(){
  const deps = state.support?.deps||[];
  showSheet(`<h2>تیکت جدید</h2>
<div class="form-row"><label>دپارتمان</label>
<select id="tkDep">${deps.map(d=>`<option value="${d.id}">${esc(d.name)}</option>`).join('')}</select>
</div>
<div class="form-row"><label>موضوع / پیام</label>
<textarea id="tkMsg" rows="4" style="width:100%;border-radius:14px;border:1px solid var(--line);background:var(--surface);color:var(--text);padding:12px;font:inherit" placeholder="متن پیام..."></textarea>
</div>
<button class="btn primary" style="width:100%" onclick="createTicket()">ارسال</button>
<button class="btn" style="width:100%;margin-top:8px" onclick="openSupport()">بازگشت</button>`);
}
async function createTicket(){
  try{
    const department_id=Number(document.getElementById('tkDep').value);
    const message=(document.getElementById('tkMsg').value||'').trim();
    const d=await api('/support/tickets',{method:'POST',body:JSON.stringify({department_id,message,subject:message.slice(0,80)})});
    toast(d.message||'ثبت شد'); openTicket(d.ticket_id);
  }catch(e){toast(e.message)}
}
async function openTicket(tid){
  try{
    const d=await api('/support/tickets/'+tid);
    const t=d.ticket, msgs=d.messages||[];
    // near-realtime poll
    if(state.ticketPoll) clearInterval(state.ticketPoll);
    state.ticketPoll = setInterval(async()=>{
      try{
        const n=await api('/support/tickets/'+tid);
        if((n.messages||[]).length !== msgs.length){
          openTicket(tid);
        }
      }catch(e){}
    }, 5000);
    showSheet(`<h2>تیکت #${t.id}</h2>
<span class="pill">${statusFa(t.status)}</span>
<div class="chat-box" style="margin-top:12px;max-height:40vh;overflow:auto;display:grid;gap:8px">
        ${msgs.map(m=>`<div style="padding:10px 12px;border-radius:14px;background:${m.sender==='user'?'rgba(155,108,255,.15)':'var(--surface-2)'};align-self:${m.sender==='user'?'end':'start'}">
<small style="color:var(--muted)">${m.sender==='user'?'شما':'پشتیبانی'} · ${new Date(m.created_at).toLocaleString('fa-IR')}</small>
<div style="margin-top:4px;font-size:13px;line-height:1.7">${esc(m.message)}</div>
</div>`).join('')||'<div class="empty">پیامی نیست</div>'}
</div>
      ${t.status!=='closed'?`
<div class="form-row" style="margin-top:12px">
<textarea id="tkReply" rows="2" style="width:100%;border-radius:14px;border:1px solid var(--line);background:var(--surface);color:var(--text);padding:12px;font:inherit" placeholder="پیام جدید..."></textarea>
</div>
<button class="btn primary" style="width:100%" onclick="sendTicketMsg(${t.id})">ارسال</button>`
      :'<p class="page-subtitle">این تیکت بسته شده است.</p>'}
<button class="btn" style="width:100%;margin-top:8px" onclick="clearInterval(state.ticketPoll);openSupport()">بازگشت</button>`);
  }catch(e){toast(e.message)}
}
async function sendTicketMsg(tid){
  const message=(document.getElementById('tkReply')?.value||'').trim();
  if(!message) return;
  try{
    await api('/support/tickets/'+tid+'/messages',{method:'POST',body:JSON.stringify({message})});
    openTicket(tid);
  }catch(e){toast(e.message)}
}

/* ===================== NEWS / NOTIFS ===================== */
function newsList(list){
  if(!list?.length)return `<div class="empty"><span class="big">▣</span><strong>خبری نیست</strong></div>`;
  return `<div class="news-list">${list.map(n=>`<article class="news-card" onclick="openNews(${n.id})">${n.image_url?`<img src="${esc(n.image_url)}" onerror="this.style.display='none'">`:''}<div class="copy"><h3>${esc(n.title)}</h3><p>${esc(n.summary||'')}</p></div></article>`).join('')}</div>`;
}
function renderNews(){app.innerHTML=`<div class="detail-head"><button class="back" onclick="render()" aria-label="بازگشت">${icon("back")}</button><div><h1 class="page-title">اخبار</h1><p class="page-subtitle">آخرین خبرها</p></div></div>${newsList(state.data.news)}`}
function renderNotifications(){
  const n=state.data.notifications;
  app.innerHTML=`<div class="detail-head"><button class="back" onclick="render()">${icon("back")}</button><div><h1 class="page-title">اعلان‌ها</h1><p class="page-subtitle">${num(n.unread)} خوانده‌نشده</p></div></div>
<div class="service-list">${n.items.length?n.items.map(x=>`<button class="menu-item" onclick="readNotif(${x.id})"><span>${x.is_read?'○':'●'}</span><span class="grow"><strong>${esc(x.title)}</strong><small>${esc(x.body)}</small></span></button>`).join(''):`<div class="empty"><strong>اعلان جدیدی ندارید</strong></div>`}</div>`;
}
function openNews(id){const n=state.data.news.find(x=>x.id===id);if(!n)return;showSheet(`<h2>${esc(n.title)}</h2>${n.image_url?`<img src="${esc(n.image_url)}" style="width:100%;border-radius:16px;margin-bottom:12px">`:''}<p style="color:var(--muted);font-size:13px;line-height:2">${esc(n.content||n.summary||'')}</p>`)}
function copyText(t){navigator.clipboard?.writeText(t).then(()=>toast('کپی شد')).catch(()=>toast('امکان کپی نیست'))}
function copyRef(){copyText(document.getElementById('refInput')?.value)}
function bannerClick(link){if(!link)return;try{tg?.openLink(link)}catch(e){location.href=link}}
async function readNotif(id){try{await api('/notifications/read',{method:'POST',body:JSON.stringify({id})});await refresh();renderNotifications()}catch(e){toast(e.message)}}

function render(){if(!state.data)return; if(state.tab==='home')app.innerHTML=home();else if(state.tab==='services')app.innerHTML=services();else if(state.tab==='wallet')app.innerHTML=wallet();else if(state.tab==='rewards'){app.innerHTML=rewards(); loadTrialBox();}else app.innerHTML=profile()}
async function loadTrialBox(){
  const box=document.getElementById('trialBox');
  if(!box) return;
  if(state.theme && state.theme.show_trial==='0'){ box.innerHTML=''; return; }
  try{
    const d=await api('/trial/status');
    if(d.available){
      box.innerHTML=`<section class="section"><div class="reward-card">
        <div style="display:flex;align-items:center;gap:12px">
          <span class="menu-ico">${icon('gift')}</span>
          <div class="grow"><strong>تست رایگان</strong><p class="page-subtitle">هنوز استفاده نکرده‌اید — همین حالا فعال کنید</p></div>
        </div>
        <button class="btn primary" style="width:100%;margin-top:12px" onclick="claimTrial()">دریافت تست رایگان</button>
      </div></section>`;
    } else if(d.used){
      box.innerHTML=`<section class="section"><div class="reward-card"><strong>تست رایگان</strong><p class="page-subtitle">قبلاً استفاده شده است.</p></div></section>`;
    } else { box.innerHTML=''; }
  }catch(e){ box.innerHTML=''; }
}
async function claimTrial(){
  try{
    const d=await withBusy('در حال ساخت تست رایگان','ممکن است چند ثانیه طول بکشد',()=>api('/trial/claim',{method:'POST',body:'{}'}));
    toast(d.message||'تست فعال شد'); await refresh(); setTab('services');
  }catch(e){toast(e.message)}
}

function renderAuthGate(issues){
  const items = (issues||[]).map(x=>{
    if(x.type==='channel'){
      const ch = x.channel||'';
      const link = ch.startsWith('@') ? 'https://t.me/'+ch.replace('@','') : (ch.startsWith('http')?ch:'');
      return `<div class="detail-card" style="margin-bottom:12px">
<strong>عضویت در کانال الزامی است</strong>
<p class="page-subtitle">${esc(x.message||'')}</p>
        ${link?`<button class="btn primary" style="width:100%;margin-top:8px" onclick="try{tg?.openTelegramLink('${esc(link)}')}catch(e){location.href='${esc(link)}'}">باز کردن کانال</button>`:''}
</div>`;
    }
    if(x.type==='phone'){
      return `<div class="detail-card" style="margin-bottom:12px">
<strong>احراز شماره موبایل</strong>
<p class="page-subtitle">${esc(x.message||'از داخل ربات شماره خود را ارسال کنید.')}</p>
<button class="btn primary" style="width:100%;margin-top:8px" onclick="try{tg?.close()}catch(e){}">بازگشت به ربات</button>
</div>`;
    }
    return `<div class="detail-card"><p class="page-subtitle">${esc(x.message||'')}</p></div>`;
  }).join('');
  app.innerHTML = `<h1 class="page-title">تکمیل احراز هویت</h1>
<p class="page-subtitle">برای استفاده از اپلیکیشن ابتدا موارد زیر را انجام دهید.</p>
    ${items}
<button class="btn" style="width:100%;margin-top:12px" onclick="refresh()">بررسی دوباره</button>`;
  if(loading && loading.parentNode) loading.remove();
}

async function refresh(opts={}){
  const soft = !!opts.soft;
  if(!soft) closeSheet();
  state.data = await api('/bootstrap');
  if(state.data.theme) applyTheme(state.data.theme);
  if(state.data.auth_required && (state.data.auth_issues||[]).length){
    renderAuthGate(state.data.auth_issues);
    return;
  }
  const unread = (state.data.notifications && state.data.notifications.unread) || 0;
  let badge = document.getElementById('notifyBadge');
  if(!badge){
    const nb=document.getElementById('notifyBtn');
    if(nb){ nb.insertAdjacentHTML('beforeend','<b id="notifyBadge" hidden>0</b>'); badge=document.getElementById('notifyBadge'); }
  }
  if(badge){ badge.hidden = !(unread>0); badge.textContent = num(unread); }
  if(loading && loading.parentNode) loading.remove();
  // soft poll: update ring/metrics without closing open sheets
  if(soft){
    const sheet = document.getElementById('sheet');
    const sheetOpen = sheet && sheet.classList.contains('is-open');
    if(!sheetOpen) render();
    // if sheet is open, state is still updated for next view
  } else {
    render();
  }
}

// Realtime volume ring: poll every 10s while miniapp is open
let _usagePollTimer = null;
function startUsagePolling(){
  stopUsagePolling();
  _usagePollTimer = setInterval(function(){
    if(document.visibilityState === 'hidden') return;
    refresh({soft:true}).catch(function(){});
  }, 10000);
}
function stopUsagePolling(){
  if(_usagePollTimer){ clearInterval(_usagePollTimer); _usagePollTimer = null; }
}
document.addEventListener('visibilitychange', function(){
  if(document.visibilityState === 'visible') refresh({soft:true}).catch(function(){});
});
window.addEventListener('pagehide', stopUsagePolling);
window.addEventListener('beforeunload', stopUsagePolling);

refresh().then(function(){
  startUsagePolling();
}).catch(function(e){
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
