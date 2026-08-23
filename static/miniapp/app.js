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
  card: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M7 15h4"/></svg>'
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
      if(mark) mark.innerHTML = '<img src="'+esc(theme.logo_url)+'" alt="" style="width:100%;height:100%;object-fit:contain;border-radius:inherit">';
    } else if(mark && theme.brand_mark){ mark.textContent = theme.brand_mark; }
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
 return `<h1 class="page-title">سلام ${esc(state.data.user.first_name||'دوست من')} 👋</h1>
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
  return `<div class="service-list">${list.map(s=>`<button class="service-mini" onclick="openService(${s.id})"><div class="service-icon">${icon("vpn")}</div><div class="grow"><strong>${esc(s.name)}</strong><small>${statusFa(s.status)} · ${num(s.remaining_days)} روز · ${num(s.remaining_gb)} GB</small></div><span class="chev">‹</span></button>`).join('')}</div>`;
}

/* ===================== SERVICES + BUY FLOW ===================== */
function services(){
  return `<div class="detail-head"><div><h1 class="page-title">سرویس‌ها</h1><p class="page-subtitle">سرویس‌های فعال و خرید سرویس جدید</p></div></div>
  <div class="actions" style="margin-bottom:16px"><button class="btn primary" style="width:100%" onclick="startBuyFlow()">🛒 خرید سرویس جدید</button></div>
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
          <span class="chev">‹</span>
        </button>`).join('')}
      </div>`);
  } else if(b.step===2){
    showSheet(`<h2>خرید سرویس جدید</h2>
      <p class="page-subtitle">۲ — دسته‌بندی مناسب را انتخاب کنید</p>
      <div class="menu-list">
        ${(b.categories||[]).map(c=>`
          <button class="menu-item" onclick="buySelectCat(${c.id})">
            <span class="menu-ico">📁</span>
            <span class="grow"><strong>${esc(c.name)}</strong></span>
            <span class="chev">‹</span>
          </button>`).join('')}
        ${b.has_uncategorized?`<button class="menu-item" onclick="buySelectCat(0)"><span class="menu-ico">📦</span><span class="grow"><strong>همه محصولات</strong></span><span class="chev">‹</span></button>`:''}
        <button class="btn" style="width:100%;margin-top:8px" onclick="state.buy.step=1;renderBuyStep()">🔙 بازگشت</button>
      </div>`);
  } else if(b.step===3){
    showSheet(`<h2>خرید سرویس جدید</h2>
      <p class="page-subtitle">۳ — محصول مورد نظر را انتخاب کنید</p>
      <div class="plan-grid">${(b.products||[]).map(p=>`
        <article class="plan">
          <h3>${esc(p.name)}</h3>
          <p class="desc">${esc(p.description||'')}</p>
          <div class="specs">
            <span class="spec">${num(p.volume_gb)} GB</span>
            <span class="spec">${num(p.duration_days)} روز</span>
            ${p.hourly_enabled?`<span class="spec">ساعتی: ${money(p.hourly_price)}</span>`:''}
          </div>
          <div class="price"><strong>${money(p.price).replace(' تومان','')}</strong><span>تومان</span></div>
          <button class="btn primary" style="width:100%" onclick="buySelectProduct(${p.id})">انتخاب</button>
        </article>`).join('')||'<div class="empty">محصولی نیست</div>'}
      <button class="btn" style="width:100%;margin-top:8px" onclick="state.buy.step=2;renderBuyStep()">🔙 بازگشت</button>
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
  // If hourly available → ask mode first
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
        <button class="btn primary" onclick="buyChooseMode('full')">🛒 خرید کامل</button>
        <button class="btn" onclick="buyChooseMode('hourly')">⏱ خرید ساعتی</button>
      </div>
      <div class="form-row"><label>کد تخفیف (اختیاری)</label><input id="buyCoupon" placeholder="مثلاً OFF20"></div>
      <button class="btn" style="width:100%;margin-top:8px" onclick="state.buy.step=3;renderBuyStep()">🔙 بازگشت</button>`);
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
      coupon_code: state.buy.coupon||''
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
      ? `<p class="page-subtitle" style="margin-top:10px">⚠️ با تایید، مبلغ از کیف پول کسر و سرویس ساخته می‌شود.</p>
         <button class="btn primary" style="width:100%" onclick="confirmWalletBuy()">✅ تایید و پرداخت از کیف پول</button>`
      : `<p class="page-subtitle" style="margin-top:10px">موجودی کافی نیست. می‌توانید کارت‌به‌کارت کنید.</p>
         <button class="btn primary" style="width:100%" onclick="startCardPay()">💳 کارت به کارت و ارسال رسید</button>`
    }
    <button class="btn" style="width:100%;margin-top:8px" onclick="closeSheet()">انصراف</button>`);
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
    const d = await api('/orders/'+state.buy.order.order_id+'/confirm-wallet',{method:'POST',body:'{}'});
    closeSheet(); haptic('medium'); toast(d.message||'خرید موفق');
    state.buy=null; await refresh();
  }catch(e){ toast(e.message); }
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
      <button class="btn" style="width:100%;margin-top:10px" onclick="copyText('${esc(d.card.card_number)}')">📋 کپی شماره کارت</button>
      <div class="form-row" style="margin-top:14px">
        <label>تصویر رسید</label>
        <input type="file" id="receiptFile" accept="image/*" capture="environment">
      </div>
      <button class="btn primary" style="width:100%" onclick="uploadBuyReceipt()">ارسال رسید برای تایید</button>`);
  }catch(e){ toast(e.message); }
}

function fileToBase64(file){
  return new Promise((resolve,reject)=>{
    const r=new FileReader();
    r.onload=()=>resolve(r.result);
    r.onerror=reject;
    r.readAsDataURL(file);
  });
}

async function uploadBuyReceipt(){
  const f = document.getElementById('receiptFile')?.files?.[0];
  if(!f){ toast('تصویر رسید را انتخاب کنید'); return; }
  if(!state.buy?.order) return;
  try{
    const b64 = await fileToBase64(f);
    const d = await api('/orders/'+state.buy.order.order_id+'/receipt',{method:'POST',body:JSON.stringify({photo:b64})});
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
        <button class="menu-item" onclick="svcAction(${s.id},'refresh')"><span class="grow"><strong>🔄 بروزرسانی</strong></span></button>
        <button class="menu-item" onclick="svcAction(${s.id},'toggle')"><span class="grow"><strong>⏯ خاموش / روشن</strong></span></button>
        <button class="menu-item" onclick="svcAction(${s.id},'reset')"><span class="grow"><strong>🔐 بازنشانی اشتراک</strong></span></button>
        <button class="menu-item" onclick="svcAction(${s.id},'hourly_toggle')"><span class="grow"><strong>⏱ توقف/شروع ساعتی</strong></span></button>
        <button class="menu-item" onclick="svcRename(${s.id})"><span class="grow"><strong>✏️ تغییر نام</strong></span></button>
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
    showSheet(`<h2>واریز ${money(amount)}</h2>
      <p class="page-subtitle">مبلغ را به کارت زیر واریز کنید، سپس تصویر رسید را همین‌جا آپلود کنید. پیام همزمان در ربات هم ارسال می‌شود.</p>
      <div class="detail-card"><strong>${esc(d.card.card_number)}</strong>
        <p class="page-subtitle">${esc(d.card.owner_name||'')}${d.card.bank_name?' · '+esc(d.card.bank_name):''}</p></div>
      <button class="btn" style="width:100%;margin-top:10px" onclick="copyText('${esc(d.card.card_number)}')">کپی شماره کارت</button>
      <div class="form-row" style="margin-top:12px"><label>تصویر رسید</label><input type="file" id="chargeReceipt" accept="image/*"></div>
      <button class="btn primary" style="width:100%" onclick="uploadChargeReceipt()">ارسال رسید</button>`);
  }catch(e){toast(e.message)}
}
async function uploadChargeReceipt(){
  const f=document.getElementById('chargeReceipt')?.files?.[0];
  if(!f||!state.pendingChargeId){toast('تصویر را انتخاب کنید');return}
  try{
    const b64=await fileToBase64(f);
    const d=await api('/wallet/topup/receipt',{method:'POST',body:JSON.stringify({charge_id:state.pendingChargeId,photo:b64})});
    closeSheet(); toast(d.message||'رسید ثبت شد');
  }catch(e){toast(e.message)}
}
function showTransactions(){showSheet(`<h2>تاریخچه تراکنش‌ها</h2>${transactions(state.data.wallet.transactions)}`)}

/* ===================== REWARDS / PROFILE ===================== */
function rewards(){
  const l=state.data.loyalty;const next=l.next_min?num(l.next_min-l.points):'∞';
  return `<h1 class="page-title">باشگاه مشتریان</h1><p class="page-subtitle">با خرید و دعوت دوستان، امتیاز جمع کن.</p>
  <section class="reward-card"><div class="level"><div><div class="eyebrow">سطح فعلی</div><strong>${esc(l.level)}</strong></div><span class="pill">${num(l.points)} امتیاز</span></div>
  <div class="progress"><i style="width:${Math.round(l.progress*100)}%"></i></div>
  <div class="eyebrow" style="margin-top:9px">${l.next_min?num(next)+' امتیاز تا سطح بعدی':'بالاترین سطح'}</div></section>
  <section class="section"><div class="section-head"><h2>دعوت دوستان</h2></div>
  <div class="reward-card"><strong>${num(state.data.referrals.total)} دعوت</strong>
  <p class="page-subtitle">${num(state.data.referrals.active)} کاربر فعال</p>
  ${state.data.referrals.link?`<div class="ref-link"><input id="refInput" readonly value="${esc(state.data.referrals.link)}"><button class="btn primary" onclick="copyRef()">کپی</button></div>`:'<p class="page-subtitle">BOT_USERNAME را تنظیم کنید.</p>'}
  </div></section>`;
}
function profile(){
  const u=state.data.user;const initial=(u.first_name||'ی').slice(0,1);
  return `<h1 class="page-title">پروفایل</h1><p class="page-subtitle">حساب تلگرامی شما</p>
  <section class="profile"><div class="avatar">${u.photo_url?`<img src="${esc(u.photo_url)}" style="width:100%;height:100%;border-radius:inherit;object-fit:cover">`:esc(initial)}</div>
  <div><h2>${esc(u.first_name||'کاربر')} ${esc(u.last_name||'')}</h2><p>${u.username?'@'+esc(u.username):'کاربر تلگرام'} · ID ${num(u.telegram_id)}</p></div></section>
  <div class="menu-list">
    <button class="menu-item" onclick="renderNotifications()"><span>◌</span><span class="grow"><strong>اعلان‌ها</strong><small>${num(state.data.notifications.unread)} خوانده‌نشده</small></span><span class="chev">‹</span></button>
    <button class="menu-item" onclick="renderNews()"><span>▣</span><span class="grow"><strong>اخبار</strong><small>اطلاعیه‌ها</small></span><span class="chev">‹</span></button>
    <button class="menu-item" onclick="openSupport()"><span class="menu-ico">${icon('support')}</span><span class="grow"><strong>پشتیبانی و تیکت</strong><small>ارسال پیام و پیگیری</small></span><span class="chev">‹</span></button>
    <button class="menu-item" onclick="startBuyFlow()"><span class="menu-ico">${icon('purchase')}</span><span class="grow"><strong>خرید سرویس جدید</strong><small>مرحله‌ای</small></span><span class="chev">‹</span></button>
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
        <button class="btn primary" style="width:100%" onclick="newTicket()">✍️ تیکت جدید</button>
      </div>
      <div class="section-head"><h2>تیکت‌های من</h2></div>
      <div class="menu-list">${state.support.tickets.length?state.support.tickets.map(t=>`
        <button class="menu-item" onclick="openTicket(${t.id})">
          <span class="grow"><strong>#${t.id} · ${esc(t.subject||'تیکت')}</strong>
          <small>${statusFa(t.status)} · ${new Date(t.updated_at||t.created_at).toLocaleDateString('fa-IR')}</small></span>
          <span class="chev">‹</span>
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
function renderNews(){app.innerHTML=`<div class="detail-head"><button class="back" onclick="render()">›</button><div><h1 class="page-title">اخبار</h1><p class="page-subtitle">آخرین خبرها</p></div></div>${newsList(state.data.news)}`}
function renderNotifications(){
  const n=state.data.notifications;
  app.innerHTML=`<div class="detail-head"><button class="back" onclick="render()">›</button><div><h1 class="page-title">اعلان‌ها</h1><p class="page-subtitle">${num(n.unread)} خوانده‌نشده</p></div></div>
  <div class="service-list">${n.items.length?n.items.map(x=>`<button class="menu-item" onclick="readNotif(${x.id})"><span>${x.is_read?'○':'●'}</span><span class="grow"><strong>${esc(x.title)}</strong><small>${esc(x.body)}</small></span></button>`).join(''):`<div class="empty"><strong>اعلان جدیدی ندارید</strong></div>`}</div>`;
}
function openNews(id){const n=state.data.news.find(x=>x.id===id);if(!n)return;showSheet(`<h2>${esc(n.title)}</h2>${n.image_url?`<img src="${esc(n.image_url)}" style="width:100%;border-radius:16px;margin-bottom:12px">`:''}<p style="color:var(--muted);font-size:13px;line-height:2">${esc(n.content||n.summary||'')}</p>`)}
function copyText(t){navigator.clipboard?.writeText(t).then(()=>toast('کپی شد')).catch(()=>toast('امکان کپی نیست'))}
function copyRef(){copyText(document.getElementById('refInput')?.value)}
function bannerClick(link){if(!link)return;try{tg?.openLink(link)}catch(e){location.href=link}}
async function readNotif(id){try{await api('/notifications/read',{method:'POST',body:JSON.stringify({id})});await refresh();renderNotifications()}catch(e){toast(e.message)}}

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
