const state={config:null,feeds:{},status:{},weather:null,activeDialog:null};
const $=s=>document.querySelector(s);const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const loadJSON=async(path)=>{const r=await fetch(path+'?v='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error(`${path}: ${r.status}`);return r.json()};
function toast(msg){const el=$('#toast');el.textContent=msg;el.classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(()=>el.classList.remove('show'),2200)}
function age(d){if(!d)return'';const t=new Date(d).getTime();if(Number.isNaN(t))return'';const s=Math.max(1,(Date.now()-t)/1000);if(s<60)return Math.floor(s)+'s';if(s<3600)return Math.floor(s/60)+'m';if(s<172800)return Math.floor(s/3600)+'h';if(s<1209600)return Math.floor(s/86400)+'d';return new Date(d).toLocaleDateString('en-GB',{day:'numeric',month:'short'})}
function cardShell(id,c,body,footer=''){const collapsed=localStorage.getItem('dv.collapsed.'+id)==='1';return `<article class="card ${collapsed?'collapsed':''}" data-card="${esc(id)}"><div class="card-head"><div class="card-title"><span>${c.icon||'•'}</span>${esc(c.title)}</div><div class="card-tools"><span class="badge">${esc(c.badge||'')}</span><button class="collapse" data-collapse="${esc(id)}" type="button">${collapsed?'+':'−'}</button></div></div><div class="card-body">${body}</div>${footer?`<div class="card-footer">${footer}</div>`:''}</article>`}
function balancedItems(items=[],limit=8,preferred=[]){
  if(!items.length)return[];

  const groups=new Map();

  items.forEach(item=>{
    const source=(item.source||'Other').trim();
    const key=source.toLowerCase();

    if(!groups.has(key)){
      groups.set(key,{
        source,
        items:[]
      });
    }

    groups.get(key).items.push(item);
  });

  const preferredKeys=preferred.map(s=>String(s).toLowerCase());

  const order=[
    ...preferredKeys.filter(key=>groups.has(key)),
    ...[...groups.keys()].filter(key=>!preferredKeys.includes(key))
  ];

  const result=[];
  let index=0;

  while(result.length<limit){
    let added=false;

    for(const key of order){
      const group=groups.get(key);

      if(group && group.items[index]){
        result.push(group.items[index]);
        added=true;

        if(result.length>=limit)break;
      }
    }

    if(!added)break;
    index++;
  }

  return result;
}

function feedRows(items=[]){
  return `<div class="feed-list">${
    items.map(i=>`
      <div class="feed-row${dvSeenClass(i.url)}">
        <span class="source-icon">
          ${esc((i.source||'R')[0]?.toUpperCase()||'R')}
        </span>

        <a
          href="${esc(i.url||'#')}"
          target="_blank"
          rel="noopener noreferrer"
          title="${esc(i.title)}"
        >
          ${esc(i.title)}
        </a>

        <span class="meta">
          <span class="source">
            ${esc(i.source||'')}
          </span>
          ${age(i.published)}
        </span>
      </div>
    `).join('')
    || '<div class="error-note">No items yet.</div>'
  }</div>`;
}

function renderFeed(id,c){
  const group=state.feeds[c.feed_key]||[];

  const preview=balancedItems(
    group,
    c.limit||8,
    c.preview_sources||[]
  );

  const err=state.feeds.errors?.[c.feed_key];

  const body=
    feedRows(preview)
    +(err
      ? '<div class="error-note">Some sources are temporarily stale.</div>'
      : '');

  const freshness=state.feeds.generated_at
    ? age(state.feeds.generated_at)
    : '';

  return cardShell(
    id,
    {
      ...c,
      badge:freshness ? `RSS · ${freshness}` : 'RSS'
    },
    body,
    `<button
      class="more-btn"
      data-more="${esc(c.feed_key)}"
      type="button"
    >View more →</button>`
  );
}


// ============================================================


// ============================================================
// DAILY_VOID_LIFE_ADMIN_V1
// ============================================================

let dailyVoidLifeAdminLoading = null;


function dvEnsureLifeAdmin() {
  if (
    state.lifeAdmin ||
    dailyVoidLifeAdminLoading
  ) {
    return;
  }

  dailyVoidLifeAdminLoading =
    loadJSON('life_admin.json')
      .then(data => {
        state.lifeAdmin = data;
        render();
      })
      .catch(error => {
        console.error(
          'Life Admin load failed:',
          error
        );

        state.lifeAdmin = {
          items: [],
          error: true
        };

        render();
      })
      .finally(() => {
        dailyVoidLifeAdminLoading = null;
      });
}


function dvMoney(item) {
  if (
    item.amount === null ||
    item.amount === undefined
  ) {
    return '';
  }

  const currency =
    item.currency || 'GBP';

  try {
    return new Intl.NumberFormat(
      'en-GB',
      {
        style: 'currency',
        currency
      }
    ).format(item.amount);

  } catch (_) {
    return `${item.amount} ${currency}`;
  }
}


function dvAdminDate(value) {
  if (!value) return '';

  const parts = String(value)
    .split('-')
    .map(Number);

  if (parts.length !== 3) {
    return value;
  }

  const date = new Date(
    Date.UTC(
      parts[0],
      parts[1] - 1,
      parts[2],
      12
    )
  );

  return new Intl.DateTimeFormat(
    'en-GB',
    {
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC'
    }
  ).format(date);
}


function dvStatusIcon(status) {
  return {
    PAID: '✓',
    DUE: '•',
    RENEWS: '↻',
    EXPIRES: '!',
    REFUNDED: '↩',
    CANCELLED: '×'
  }[status] || '•';
}


function renderLifeAdmin(id, c) {
  if (!state.lifeAdmin) {
    dvEnsureLifeAdmin();

    return cardShell(
      id,
      {
        ...c,
        badge: 'GMAIL'
      },
      `
        <div class="life-admin-empty">
          Checking the paperwork…
        </div>
      `
    );
  }

  const allItems = Array.isArray(
    state.lifeAdmin.items
  )
    ? state.lifeAdmin.items
    : [];

  const limit = c.limit || 8;

  const items = allItems.slice(
    0,
    limit
  );

  const rows = items.map(item => {
    const money = dvMoney(item);

    const detail = [
      money,
      dvAdminDate(item.date)
    ]
      .filter(Boolean)
      .join(' · ');

    return `
      <div
        class="life-admin-row"
        data-status="${esc(item.status)}"
      >

        <div class="life-admin-icon">
          ${esc(dvStatusIcon(item.status))}
        </div>

        <div class="life-admin-main">

          <div class="life-admin-merchant">
            ${esc(item.merchant)}
          </div>

          <div class="life-admin-detail">
            ${esc(detail)}
          </div>

        </div>

        <div class="life-admin-status">
          ${esc(item.status)}
        </div>

      </div>
    `;
  }).join('');

  const body = `
    <div class="life-admin-widget">

      ${
        rows ||
        `
          <div class="life-admin-empty">
            Nothing demanding money or attention.
          </div>
        `
      }

      ${
        allItems.length > limit
          ? `
            <div class="life-admin-more">
              + ${allItems.length - limit} more
            </div>
          `
          : ''
      }

    </div>
  `;

  const footer = `
    <a
      class="life-admin-open"
      href="${esc(
        c.gmail_url ||
        'https://mail.google.com/'
      )}"
      target="_blank"
      rel="noopener noreferrer"
    >
      Open Gmail →
    </a>
  `;

  const badge = allItems.length
    ? `${allItems.length} ITEMS`
    : 'CLEAR';

  return cardShell(
    id,
    {
      ...c,
      badge
    },
    body,
    footer
  );
}


// DAILY_VOID_PRIVATE_CALENDAR_V1
// ============================================================

let dailyVoidCalendarLoading = null;


function dvLondonDateKey(date) {
  const parts = new Intl.DateTimeFormat(
    'en-GB',
    {
      timeZone: 'Europe/London',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }
  ).formatToParts(date);

  const values = {};

  parts.forEach(part => {
    if (part.type !== 'literal') {
      values[part.type] = part.value;
    }
  });

  return (
    `${values.year}-${values.month}-${values.day}`
  );
}


function dvAddDateDays(key, days) {
  const [year, month, day] = key
    .split('-')
    .map(Number);

  const date = new Date(
    Date.UTC(year, month - 1, day + days, 12)
  );

  return date.toISOString().slice(0, 10);
}


function dvEventDateKey(event) {
  if (event.all_day) {
    return String(event.start).slice(0, 10);
  }

  return dvLondonDateKey(
    new Date(event.start)
  );
}


function dvCalendarTime(event) {
  if (event.all_day) {
    return 'ALL DAY';
  }

  return new Intl.DateTimeFormat(
    'en-GB',
    {
      timeZone: 'Europe/London',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }
  ).format(
    new Date(event.start)
  );
}


function dvCalendarDateLabel(key) {
  const [year, month, day] = key
    .split('-')
    .map(Number);

  const date = new Date(
    Date.UTC(year, month - 1, day, 12)
  );

  return new Intl.DateTimeFormat(
    'en-GB',
    {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC'
    }
  ).format(date);
}


function dvEnsureCalendar() {
  if (
    state.calendar ||
    dailyVoidCalendarLoading
  ) {
    return;
  }

  dailyVoidCalendarLoading =
    loadJSON('calendar.json')
      .then(data => {
        state.calendar = data;
        render();
      })
      .catch(error => {
        console.error(
          'Calendar load failed:',
          error
        );

        state.calendar = {
          events: [],
          error: true
        };

        render();
      })
      .finally(() => {
        dailyVoidCalendarLoading = null;
      });
}


function dvCalendarRows(events, options = {}) {
  const {
    showDate = false
  } = options;

  return events.map(event => {
    const key = dvEventDateKey(event);

    const when = showDate
      ? dvCalendarDateLabel(key)
      : dvCalendarTime(event);

    return `
      <div class="calendar-row">

        <div class="calendar-when">
          ${esc(when)}
        </div>

        <div class="calendar-title">
          ${esc(event.title || 'Untitled event')}
        </div>

      </div>
    `;
  }).join('');
}


function dvCalendarSection(
  title,
  events,
  options = {}
) {
  if (!events.length && title !== 'TODAY') {
    return '';
  }

  let content;

  if (events.length) {
    content = dvCalendarRows(
      events,
      options
    );
  } else {
    content = `
      <div class="calendar-empty">
        ${title === 'TODAY' ? 'Nothing today.' : 'Nothing scheduled.'}
      </div>
    `;
  }

  return `
    <section class="calendar-section">

      <div class="calendar-section-title">
        ${esc(title)}
      </div>

      ${content}

    </section>
  `;
}


function renderCalendar(id, c) {
  if (!state.calendar) {
    dvEnsureCalendar();

    return cardShell(
      id,
      {
        ...c,
        badge: 'CALENDAR'
      },
      `
        <div class="calendar-loading">
          Reading the future…
        </div>
      `
    );
  }

  const events = Array.isArray(
    state.calendar.events
  )
    ? state.calendar.events
    : [];

  const today = dvLondonDateKey(
    new Date()
  );

  const tomorrow = dvAddDateDays(
    today,
    1
  );

  const todayEvents = events.filter(
    event =>
      dvEventDateKey(event) === today
  );

  const tomorrowEvents = events.filter(
    event =>
      dvEventDateKey(event) === tomorrow
  );

  const laterEvents = events.filter(
    event =>
      dvEventDateKey(event) > tomorrow
  );

  const limit = c.limit || 8;

  const laterLimit = 5;

  const laterVisible =
    laterEvents.slice(
      0,
      laterLimit
    );

  const laterHidden = Math.max(
    0,
    laterEvents.length - laterVisible.length
  );

  const body = `
    <div class="calendar-widget">

      ${dvCalendarSection(
        'TODAY',
        todayEvents
      )}

      ${dvCalendarSection(
        'TOMORROW',
        tomorrowEvents
      )}

      ${dvCalendarSection(
        'NEXT',
        laterVisible,
        {
          showDate: true
        }
      )}

      ${laterHidden > 0 ? `
        <div class="calendar-more">
          + ${laterHidden} more
        </div>
      ` : ''}

    </div>
  `;

  const badge = events.length
    ? `${events.length} UPCOMING`
    : 'CLEAR';

  const footer = `
    <a
      class="calendar-open"
      href="${esc(
        c.calendar_url ||
        'https://calendar.google.com/'
      )}"
      target="_blank"
      rel="noopener noreferrer"
    >
      Open Calendar →
    </a>
  `;

  return cardShell(
    id,
    {
      ...c,
      badge
    },
    body,
    footer
  );
}


function renderWeather(id,c){const w=state.weather;if(!w)return cardShell(id,c,'<div class="error-note">Weather not fetched yet.</div>');const days=(w.daily||[]).slice(0,4).map(d=>`<div><div>${esc(d.day)}</div><div>${esc(d.icon||'·')}</div><div><b>${esc(d.high)}°</b> / ${esc(d.low)}°</div></div>`).join('');return cardShell(id,c,`<div class="weather"><div class="weather-now"><div class="weather-icon">${esc(w.icon||'⛅')}</div><div><div class="weather-temp">${esc(w.temperature)}°C</div><div class="weather-condition">${esc(w.condition)}</div><div class="weather-place">${esc(w.place||'Your City')}</div></div><div class="weather-stats"><span>Feels ${esc(w.feels_like)}°</span><span>Humidity ${esc(w.humidity)}%</span><span>Wind ${esc(w.wind)} km/h</span></div></div><div class="forecast">${days}</div></div>`)}
function renderLinks(id,c){const body=`<div class="link-grid">${(c.links||[]).map(l=>`<a class="link-tile" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer"><span><span class="icon">${esc(l.icon||'🔗')}</span><small>${esc(l.title)}</small></span></a>`).join('')}</div>`;return cardShell(id,c,body)}
function renderChaplaincy(id,c){return cardShell(id,c,`<a class="funeral-link" href="${esc(c.funeral_notices_url)}" target="_blank" rel="noopener noreferrer"><span style="font-size:1.5rem">▧</span><span><b>Your Cityshire Funeral Notices</b><small>Recent notices and announcements</small></span></a>`)}
function renderSocial(id,c){return cardShell(id,c,`<div class="social-list">${(c.links||[]).map(l=>`<a class="social-link" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer"><span>${esc(l.title)}</span><span>${esc(l.note||'→')}</span></a>`).join('')}</div>`)}
function serviceStateClass(s){
  return s?.state==='ok'
    ? 'ok'
    : s?.state==='bad'
      ? 'bad'
      : 'warn';
}

function serviceName(s){
  if(!s)return '';

  return s.link
    ? `<a href="${esc(s.link)}" target="_blank" rel="noopener noreferrer">${esc(s.name)}</a>`
    : `<span class="service-name">${esc(s.name)}</span>`;
}

function childServiceRow(s){
  if(!s)return '';

  return `
    <div class="service-row service-child">
      <span class="status-dot ${serviceStateClass(s)}"></span>
      ${serviceName(s)}
      <span class="status-text">
        ${esc(s.label||s.state||'unknown')}
      </span>
      <span class="service-extra">
        ${esc(s.extra||'')}
      </span>
    </div>
  `;
}

function machineBlock(name,machine,children=[]){
  const stateClass=serviceStateClass(machine);

  const label=machine
    ? (machine.state==='ok' ? 'online' : machine.label||'unknown')
    : 'unknown';

  const extra=machine?.extra||'';

  return `
    <div class="machine-group">

      <div class="machine-row">
        <span class="status-dot ${stateClass}"></span>

        <strong class="machine-name">
          ${esc(name)}
        </strong>

        <span class="status-text">
          ${esc(label)}
        </span>

        <span class="service-extra">
          ${esc(extra)}
        </span>
      </div>

      <div class="machine-services">
        ${children.filter(Boolean).map(childServiceRow).join('')}
      </div>

    </div>
  `;
}

function renderServices(id,c){
  const services=state.status.services||[];

  const byName=Object.fromEntries(
    services.map(s=>[s.name,s])
  );

  const groups=c.groups||[];

  let body='<div class="service-list">';

  for(const group of groups){

    if(group.kind==='machine'){
      const primary=byName[group.primary];

      const children=(group.services||[])
        .map(name=>byName[name])
        .filter(Boolean);

      body+=machineBlock(
        group.title||group.primary,
        primary,
        children
      );

      continue;
    }

    if(group.kind==='list'){
      body+=`
        <div class="service-section-title">
          ${esc(group.title||'SERVICES')}
        </div>
      `;

      for(const name of group.services||[]){
        const service=byName[name];

        if(service){
          body+=childServiceRow(service);
        }
      }
    }
  }

  if(!groups.length){
    body+=services
      .map(childServiceRow)
      .join('');
  }

  body+='</div>';

  const freshness=state.status.generated_at
    ? age(state.status.generated_at)
    : '';

  return cardShell(
    id,
    {
      ...c,
      badge:freshness
        ? `LIVE · ${freshness}`
        : 'LIVE'
    },
    body
  );
}
function renderCard(id,c){if(c.type==='life_admin')return renderLifeAdmin(id,c);if(c.type==='calendar')return renderCalendar(id,c);if(c.type==='feed')return renderFeed(id,c);if(c.type==='weather')return renderWeather(id,c);if(c.type==='links')return renderLinks(id,c);if(c.type==='chaplaincy')return renderChaplaincy(id,c);if(c.type==='social')return renderSocial(id,c);if(c.type==='services')return renderServices(id,c);return cardShell(id,c,'<div class="error-note">Unknown card type.</div>')}
function render(){const root=$('#dashboard');root.innerHTML=state.config.columns.map(col=>`<section class="column">${col.map(id=>renderCard(id,state.config.cards[id])).join('')}</section>`).join('');root.querySelectorAll('[data-collapse]').forEach(b=>b.onclick=()=>{const id=b.dataset.collapse;const card=root.querySelector(`[data-card="${CSS.escape(id)}"]`);card.classList.toggle('collapsed');localStorage.setItem('dv.collapsed.'+id,card.classList.contains('collapsed')?'1':'0');b.textContent=card.classList.contains('collapsed')?'+':'−'});}
function setupSearch(){const input=$('#searchInput'),form=$('#searchForm');const routes={g:q=>'https://www.google.com/search?q='+encodeURIComponent(q),sp:q=>'https://www.startpage.com/sp/search?query='+encodeURIComponent(q),yt:q=>'https://www.youtube.com/results?search_query='+encodeURIComponent(q),gh:q=>'https://github.com/search?q='+encodeURIComponent(q),r:q=>'https://www.reddit.com/search/?q='+encodeURIComponent(q),x:q=>'https://x.com/search?q='+encodeURIComponent(q),itch:q=>'https://itch.io/search?q='+encodeURIComponent(q),fn:()=>state.config.cards.chaplaincy.funeral_notices_url};form.onsubmit=e=>{e.preventDefault();const raw=input.value.trim();if(!raw)return;const m=raw.match(/^!(\w+)\s*(.*)$/);window.open(m&&routes[m[1]]?routes[m[1]](m[2]):routes.sp(raw),'_blank','noopener')};$('#searchHints').innerHTML=state.config.search_hints.map(h=>`<button class="chip" type="button" data-fill="${esc(h.value)}">${esc(h.label)}</button>`).join('');$('#searchHints').querySelectorAll('[data-fill]').forEach(b=>b.onclick=()=>{input.value=b.dataset.fill;input.focus();if(b.dataset.fill==='!fn')form.requestSubmit()});window.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();input.focus();input.select()}})}

// DAILY_VOID_DYNAMIC_REFRESH_V22
async function refreshDailyVoid() {
  const button = document.querySelector('#refreshBtn');

  if (button) {
    button.disabled = true;
    button.classList.add('refreshing');
  }

  try {
    const [feeds, status, weather, calendar, lifeAdmin] = await Promise.all([
      loadJSON('feeds.json'),
      loadJSON('status.json'),
      loadJSON('weather.json'),
      loadJSON('calendar.json'),
      loadJSON('life_admin.json')
    ]);

    state.feeds = feeds;
    state.status = status;
    state.weather = weather;
    state.calendar = calendar;
    state.lifeAdmin = lifeAdmin;

    render();

  } catch (error) {
    console.error(
      'Daily Void refresh failed:',
      error
    );

  } finally {
    if (button) {
      button.disabled = false;
      button.classList.remove('refreshing');
    }
  }
}

function setupFooter(){function tick(){const n=new Date();$('#dateText').textContent=n.toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:'Europe/London'});$('#timeText').textContent=n.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/London'})}tick();setInterval(tick,30000);const quotes=['All things are temporary. Even this dashboard.','Check the server. Then stare briefly into the abyss.','News, death, code, weather: the four tabs of being.','Another day in the content mines. Bring tea.','The universe is indifferent, but the hover states are nice.'];$('#quote').onclick=()=>$('#quote').textContent=quotes[Math.floor(Math.random()*quotes.length)];if(localStorage.getItem('dv.compact')==='1')document.body.classList.add('compact');$('#compactBtn').onclick=()=>{document.body.classList.toggle('compact');localStorage.setItem('dv.compact',document.body.classList.contains('compact')?'1':'0')};$('#refreshBtn').onclick=()=>refreshDailyVoid()}
async function init(){try{state.config=await loadJSON('config.json');document.title=state.config.title||'The Daily Void';setupSearch();setupFooter();const [feeds,status,weather]=await Promise.allSettled([loadJSON('feeds.json'),loadJSON('status.json'),loadJSON('weather.json')]);if(feeds.status==='fulfilled')state.feeds=feeds.value;if(status.status==='fulfilled')state.status=status.value;if(weather.status==='fulfilled')state.weather=weather.value;render();if(feeds.status==='rejected')toast('Feeds not generated yet');}catch(e){console.error(e);document.body.innerHTML='<pre style="color:white;padding:20px">Daily Void failed to start: '+esc(e.message)+'</pre>'}}
init();



// ============================================================
// DAILY_VOID_FEED_OVERLAY_V1
// Expanded RSS/Reddit browser
// ============================================================

const dailyVoidFeedMeta = {
  technology: {
    title: 'TECHNOLOGY',
    sources: [
      'Hacker News',
      'Ars Technica',
      'The Verge',
      'Ubuntu',
      'Arch Linux'
    ]
  },

  news: {
    title: 'NEWS',
    sources: [
      'BBC',
      'Guardian',
      'Daily Mail'
    ]
  },

  reddit: {
    title: 'THE SWAMP',
    sources: [
      'r/LocalLLaMA',
      'r/selfhosted',
      'r/linux',
      'r/comfyui',
      'r/gamedev'
    ]
  }
};


let dailyVoidOverlayFeed = null;
let dailyVoidOverlaySource = 'all';


function dailyVoidOverlayEscape(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}


function dailyVoidFeedItems(feedKey) {
  const items = state?.feeds?.[feedKey];

  return Array.isArray(items)
    ? items
    : [];
}


function dailyVoidNormaliseSource(source) {
  return String(source || '').toLowerCase();
}


function dailyVoidOverlaySources(feedKey) {
  const meta = dailyVoidFeedMeta[feedKey] || {};
  const configured = meta.sources || [];

  const actual = dailyVoidFeedItems(feedKey)
    .map(item => item.source)
    .filter(Boolean);

  const found = [];

  for (const source of [...configured, ...actual]) {
    const key = dailyVoidNormaliseSource(source);

    if (!found.some(x => dailyVoidNormaliseSource(x) === key)) {
      found.push(source);
    }
  }

  return found;
}




function dailyVoidCloseFeedOverlay() {
  const overlay = document.getElementById('daily-void-feed-overlay');

  if (!overlay) return;

  overlay.classList.remove('is-open');

  document.body.classList.remove('feed-overlay-open');

  window.setTimeout(() => {
    overlay.remove();
  }, 140);

  dailyVoidOverlayFeed = null;
  dailyVoidOverlaySource = 'all';
}


function dailyVoidRenderOverlayItems() {
  const list = document.getElementById('daily-void-overlay-list');
  const count = document.getElementById('daily-void-overlay-count');

  if (!list || !dailyVoidOverlayFeed) return;

  let items = dailyVoidFeedItems(dailyVoidOverlayFeed);

  if (dailyVoidOverlaySource !== 'all') {
    const wanted = dailyVoidNormaliseSource(
      dailyVoidOverlaySource
    );

    items = items.filter(item =>
      dailyVoidNormaliseSource(item.source) === wanted
    );
  }

  if (count) {
    const noun =
      dailyVoidOverlayFeed === 'reddit'
        ? 'POSTS'
        : 'STORIES';

    count.textContent = `${items.length} ${noun}`;
  }

  if (!items.length) {
    list.innerHTML = `
      <div class="feed-overlay-empty">
        Nothing here at the mserver2t.
      </div>
    `;
    return;
  }

  list.innerHTML = items.map(item => {
    const title = dailyVoidOverlayEscape(item.title);
    const url = dailyVoidOverlayEscape(item.url || '#');
    const source = dailyVoidOverlayEscape(item.source || '');
    const when = dailyVoidOverlayEscape(
      age(item.published)
    );

    return `
      <article class="feed-overlay-item${dvSeenClass(item.url)}">

        <div class="feed-overlay-source">
          ${source}
        </div>

        <a
          class="feed-overlay-title"
          href="${url}"
          target="_blank"
          rel="noopener noreferrer"
        >
          ${title}
        </a>

        <div class="feed-overlay-age">
          ${when}
        </div>

      </article>
    `;
  }).join('');
}


function dailyVoidSelectOverlaySource(source) {
  dailyVoidOverlaySource = source;

  document
    .querySelectorAll('.feed-overlay-filter')
    .forEach(button => {
      const selected =
        dailyVoidNormaliseSource(button.dataset.source) ===
        dailyVoidNormaliseSource(source);

      button.classList.toggle(
        'active',
        selected
      );
    });

  dailyVoidRenderOverlayItems();
}


function dailyVoidOpenFeedOverlay(feedKey) {
  if (!dailyVoidFeedMeta[feedKey]) {
    return;
  }

  dailyVoidCloseFeedOverlay();

  dailyVoidOverlayFeed = feedKey;
  dailyVoidOverlaySource = 'all';

  const meta = dailyVoidFeedMeta[feedKey];
  const sources = dailyVoidOverlaySources(feedKey);

  const overlay = document.createElement('div');

  overlay.id = 'daily-void-feed-overlay';
  overlay.className = 'feed-overlay';

  overlay.innerHTML = `
    <div
      class="feed-overlay-backdrop"
      data-overlay-close="1"
    ></div>

    <section
      class="feed-overlay-panel"
      role="dialog"
      aria-modal="true"
      aria-label="${dailyVoidOverlayEscape(meta.title)}"
    >

      <header class="feed-overlay-header">

        <div>
          <div class="feed-overlay-kicker">
            THE DAILY VOID
          </div>

          <h2>
            ${dailyVoidOverlayEscape(meta.title)}
          </h2>
        </div>

        <button
          class="feed-overlay-close"
          type="button"
          data-overlay-close="1"
          aria-label="Close"
          title="Close"
        >
          ×
        </button>

      </header>

      <div class="feed-overlay-toolbar">

        <div class="feed-overlay-filters">

          <button
            class="feed-overlay-filter active"
            type="button"
            data-source="all"
          >
            All
          </button>

          ${sources.map(source => `
            <button
              class="feed-overlay-filter"
              type="button"
              data-source="${dailyVoidOverlayEscape(source)}"
            >
              ${dailyVoidOverlayEscape(
                source.replace(/^r\//i, '')
              )}
            </button>
          `).join('')}

        </div>

        <div
          id="daily-void-overlay-count"
          class="feed-overlay-count"
        ></div>

      </div>

      <div
        id="daily-void-overlay-list"
        class="feed-overlay-list"
      ></div>

    </section>
  `;

  document.body.appendChild(overlay);

  document.body.classList.add(
    'feed-overlay-open'
  );

  dailyVoidRenderOverlayItems();

  requestAnimationFrame(() => {
    overlay.classList.add('is-open');
  });

  const closeButton =
    overlay.querySelector('.feed-overlay-close');

  if (closeButton) {
    closeButton.focus();
  }
}


// Capture phase deliberately intercepts any old View More handler.
document.addEventListener(
  'click',
  event => {
    const more = event.target.closest(
      '.more-btn[data-more]'
    );

    if (more) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();

      dailyVoidOpenFeedOverlay(
        more.dataset.more
      );

      return;
    }

    const filter = event.target.closest(
      '.feed-overlay-filter'
    );

    if (filter) {
      event.preventDefault();

      dailyVoidSelectOverlaySource(
        filter.dataset.source || 'all'
      );

      return;
    }

    const close = event.target.closest(
      '[data-overlay-close]'
    );

    if (close) {
      event.preventDefault();

      dailyVoidCloseFeedOverlay();
    }
  },
  true
);


document.addEventListener(
  'keydown',
  event => {
    if (
      event.key === 'Escape' &&
      document.getElementById(
        'daily-void-feed-overlay'
      )
    ) {
      event.preventDefault();
      dailyVoidCloseFeedOverlay();
    }
  }
);



// ============================================================
// DAILY_VOID_BRIEF_READSTATE_V1
// ============================================================


// ------------------------------------------------------------
// READ STATE
// ------------------------------------------------------------

const DV_SEEN_KEY = 'dv.seen.v1';
const DV_SEEN_LIMIT = 800;


function dvSeenStore() {
  try {
    const parsed = JSON.parse(
      localStorage.getItem(DV_SEEN_KEY) || '{}'
    );

    return (
      parsed &&
      typeof parsed === 'object' &&
      !Array.isArray(parsed)
    )
      ? parsed
      : {};

  } catch (_) {
    return {};
  }
}


function dvSeenUrl(url) {
  try {
    const value = new URL(
      String(url || ''),
      window.location.href
    );

    value.hash = '';

    return value.href;

  } catch (_) {
    return String(url || '');
  }
}


function dvIsSeen(url) {
  if (!url) return false;

  const store = dvSeenStore();

  return Boolean(
    store[dvSeenUrl(url)]
  );
}


function dvSeenClass(url) {
  return dvIsSeen(url)
    ? ' seen'
    : '';
}


function dvMarkSeen(url) {
  if (!url) return;

  try {
    const store = dvSeenStore();

    store[dvSeenUrl(url)] = Date.now();

    const entries = Object.entries(store)
      .sort(
        (a, b) =>
          Number(b[1]) - Number(a[1])
      )
      .slice(0, DV_SEEN_LIMIT);

    localStorage.setItem(
      DV_SEEN_KEY,
      JSON.stringify(
        Object.fromEntries(entries)
      )
    );

  } catch (_) {}
}


document.addEventListener(
  'click',
  event => {
    const link = event.target.closest(
      '.feed-row a[href],'
      + '.feed-overlay-title[href]'
    );

    if (!link) return;

    dvMarkSeen(
      link.href
    );

    const row = link.closest(
      '.feed-row,'
      + '.feed-overlay-item'
    );

    if (row) {
      row.classList.add('seen');
    }
  },
  true
);


// ------------------------------------------------------------
// DAILY BRIEF
// ------------------------------------------------------------

function dvBriefDateKey(date) {
  const parts =
    new Intl.DateTimeFormat(
      'en-GB',
      {
        timeZone: 'Europe/London',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      }
    ).formatToParts(date);

  const values = {};

  parts.forEach(part => {
    if (part.type !== 'literal') {
      values[part.type] = part.value;
    }
  });

  return (
    `${values.year}-`
    + `${values.month}-`
    + `${values.day}`
  );
}


function dvBriefAddDays(key, days) {
  const [y, m, d] = key
    .split('-')
    .map(Number);

  return new Date(
    Date.UTC(
      y,
      m - 1,
      d + days,
      12
    )
  )
    .toISOString()
    .slice(0, 10);
}


function dvBriefEventDate(event) {
  if (!event) return '';

  if (event.all_day) {
    return String(
      event.start || ''
    ).slice(0, 10);
  }

  const date = new Date(
    event.start
  );

  if (Number.isNaN(date.getTime())) {
    return '';
  }

  return dvBriefDateKey(date);
}


function dvBriefDaysUntil(value) {
  if (!value) return null;

  const today = dvBriefDateKey(
    new Date()
  );

  const [ty, tm, td] = today
    .split('-')
    .map(Number);

  const [y, m, d] = String(value)
    .split('-')
    .map(Number);

  if (
    !y || !m || !d
  ) {
    return null;
  }

  const a = Date.UTC(
    ty, tm - 1, td
  );

  const b = Date.UTC(
    y, m - 1, d
  );

  return Math.round(
    (b - a) / 86400000
  );
}


function dvBriefMoney(item) {
  if (
    item.amount === null ||
    item.amount === undefined
  ) {
    return '';
  }

  try {
    return new Intl.NumberFormat(
      'en-GB',
      {
        style: 'currency',
        currency:
          item.currency || 'GBP'
      }
    ).format(
      item.amount
    );

  } catch (_) {
    return String(item.amount);
  }
}


function dvBriefCalendar() {
  const events =
    state.calendar?.events;

  if (!Array.isArray(events)) {
    return null;
  }

  const today = dvBriefDateKey(
    new Date()
  );

  const tomorrow = dvBriefAddDays(
    today,
    1
  );

  const todayCount = events.filter(
    event =>
      dvBriefEventDate(event)
      === today
  ).length;

  const tomorrowCount = events.filter(
    event =>
      dvBriefEventDate(event)
      === tomorrow
  ).length;

  if (
    todayCount === 0 &&
    tomorrowCount === 0
  ) {
    return 'No events today or tomorrow';
  }

  const parts = [];

  if (todayCount) {
    parts.push(
      `${todayCount} event${
        todayCount === 1 ? '' : 's'
      } today`
    );
  } else {
    parts.push(
      'No events today'
    );
  }

  if (tomorrowCount) {
    parts.push(
      `${tomorrowCount} tomorrow`
    );
  }

  return parts.join(' · ');
}


function dvBriefLifeAdmin() {
  const items =
    state.lifeAdmin?.items;

  if (!Array.isArray(items)) {
    return null;
  }

  const priorities = {
    DUE: 0,
    EXPIRES: 1,
    RENEWS: 2
  };

  const candidates = items
    .filter(
      item =>
        Object.hasOwn(
          priorities,
          item.status
        )
    )
    .map(item => ({
      ...item,
      days:
        dvBriefDaysUntil(
          item.date
        )
    }))
    .filter(
      item =>
        item.days !== null
        && item.days >= 0
    )
    .sort((a, b) => {
      if (a.days !== b.days) {
        return a.days - b.days;
      }

      return (
        priorities[a.status]
        - priorities[b.status]
      );
    });

  const item = candidates[0];

  if (!item) {
    return null;
  }

  const money = dvBriefMoney(
    item
  );

  let action = '';

  if (item.status === 'DUE') {
    action = 'due';
  }

  if (item.status === 'RENEWS') {
    action = 'renews';
  }

  if (item.status === 'EXPIRES') {
    action = 'expires';
  }

  const when =
    item.days === 0
      ? 'today'
      : item.days === 1
        ? 'tomorrow'
        : `in ${item.days} days`;

  return [
    item.merchant,
    money,
    action,
    when
  ]
    .filter(Boolean)
    .join(' ');
}


function dvBriefWeather() {
  const weather =
    state.weather;

  if (!weather) {
    return null;
  }

  const temp =
    weather.temperature;

  const condition =
    weather.condition;

  if (
    temp === undefined ||
    temp === null
  ) {
    return condition || null;
  }

  return [
    `${temp}°C`,
    condition
  ]
    .filter(Boolean)
    .join(' · ');
}


function dvBriefSystems() {
  const services =
    state.status?.services;

  if (!Array.isArray(services)) {
    return null;
  }

  const problems = services.filter(
    service =>
      service.state
      && service.state !== 'ok'
  );

  if (!problems.length) {
    return 'All systems online';
  }

  if (problems.length === 1) {
    return (
      `${problems[0].name} needs attention`
    );
  }

  return (
    `${problems.length} services need attention`
  );
}


function dvBriefHost() {
  return document.getElementById('dailyBrief');
}


function dvRenderDailyBrief() {
  const host = dvBriefHost();

  if (!host) return;

  const items = [
    dvBriefCalendar(),
    dvBriefLifeAdmin(),
    dvBriefWeather(),
    dvBriefSystems()
  ].filter(Boolean);

  host.innerHTML = `
    <div class="daily-brief-label">
      DAILY BRIEF
    </div>

    <div class="daily-brief-items">
      ${
        items.map(item => `
          <span class="daily-brief-item">
            ${esc(item)}
          </span>
        `).join('')
        ||
        `
          <span class="daily-brief-item">
            Gathering disturbances…
          </span>
        `
      }
    </div>
  `;
}


// Refresh the brief every time the dashboard re-renders.
if (
  typeof render === 'function'
  && !window.__dailyVoidBriefWrapped
) {
  window.__dailyVoidBriefWrapped = true;

  const dvRenderOriginal = render;

  render = function(...args) {
    const result =
      dvRenderOriginal(...args);

    queueMicrotask(
      dvRenderDailyBrief
    );

    return result;
  };
}


window.addEventListener(
  'DOMContentLoaded',
  () => {
    setTimeout(
      dvRenderDailyBrief,
      200
    );

    setTimeout(
      dvRenderDailyBrief,
      1200
    );
  }
);


setInterval(
  dvRenderDailyBrief,
  60000
);




// DAILY_VOID_BRIEF_STATIC_HOST_V2

function dvBriefRefreshEventually() {
  dvRenderDailyBrief();

  setTimeout(
    dvRenderDailyBrief,
    500
  );

  setTimeout(
    dvRenderDailyBrief,
    1500
  );
}

window.addEventListener(
  'load',
  dvBriefRefreshEventually
);



// ============================================================
// DAILY_VOID_MALOJA_WEEK_V1
// ============================================================

let dvMalojaWeekData = null;


function dvMalojaCountText(n) {
  const count =
    Number(n || 0);

  return (
    `${count} scrobble`
    + `${count === 1 ? '' : 's'}`
  );
}


function dvMalojaFeature(
  label,
  item
) {
  if (!item) {
    return '';
  }

  const artist =
    item.artist
      ? `${item.artist} · `
      : '';

  return `
    <a
      class="maloja-feature"
      href="${esc(
        item.link
        || 'https://music.example.com/'
      )}"
      target="_blank"
      rel="noopener noreferrer"
    >

      ${
        item.art
          ? `
            <img
              class="maloja-feature-art"
              src="${esc(item.art)}"
              alt=""
              loading="lazy"
            >
          `
          : `
            <div
              class="
                maloja-feature-art
                maloja-art-empty
              "
            ></div>
          `
      }

      <div class="maloja-feature-copy">

        <div class="maloja-feature-label">
          ${esc(label)}
        </div>

        <div class="maloja-feature-title">
          ${esc(item.name || '')}
        </div>

        <div class="maloja-feature-meta">
          ${esc(
            artist
            + dvMalojaCountText(
                item.count
              )
          )}
        </div>

      </div>

    </a>
  `;
}


function dvRenderMalojaWeek() {
  const host =
    document.getElementById(
      'malojaWeek'
    );

  if (!host) {
    return;
  }

  const data =
    dvMalojaWeekData;

  if (!data) {
    host.innerHTML = `
      <div class="maloja-loading">
        Listening for temporary disturbances…
      </div>
    `;

    return;
  }


  const count =
    Number(
      data.scrobbles || 0
    );


  if (!count) {
    host.innerHTML = `
      <div class="maloja-week-head">

        <div>
          <span class="maloja-week-label">
            MUSIC THIS WEEK
          </span>

          <span class="maloja-week-stat">
            WEEK ${esc(data.week || '')}
          </span>
        </div>

        <a
          class="maloja-open"
          href="https://music.example.com/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Open Maloja →
        </a>

      </div>

      <div class="maloja-empty">
        No scrobbles yet this week.
      </div>
    `;

    return;
  }


  const albums =
    Array.isArray(data.albums)
      ? data.albums
      : [];


  const albumRail = albums
    .filter(album => album.art)
    .slice(0, 6)
    .map(album => `
      <a
        class="maloja-cover-link"
        href="${esc(
          album.link
          || 'https://music.example.com/'
        )}"
        target="_blank"
        rel="noopener noreferrer"
        title="${esc(
          [
            album.artist,
            album.name
          ]
            .filter(Boolean)
            .join(' — ')
        )}"
      >
        <img
          class="maloja-cover"
          src="${esc(album.art)}"
          alt=""
          loading="lazy"
        >
      </a>
    `)
    .join('');


  host.innerHTML = `

    <div class="maloja-week-head">

      <div class="maloja-week-heading">

        <span class="maloja-week-label">
          MUSIC THIS WEEK
        </span>

        <span class="maloja-week-stat">
          WEEK ${esc(data.week)}
          ·
          ${esc(count)} SCROBBLES
        </span>

      </div>

      <a
        class="maloja-open"
        href="https://music.example.com/"
        target="_blank"
        rel="noopener noreferrer"
      >
        Open Maloja →
      </a>

    </div>


    <div class="maloja-features">

      ${dvMalojaFeature(
        'TOP ARTIST',
        data.top_artist
      )}

      ${dvMalojaFeature(
        'TOP TRACK',
        data.top_track
      )}

      ${dvMalojaFeature(
        'TOP ALBUM',
        data.top_album
      )}

    </div>


    ${
      albumRail
        ? `
          <div class="maloja-album-rail">
            ${albumRail}
          </div>
        `
        : ''
    }

  `;
}


async function dvLoadMalojaWeek() {
  try {
    dvMalojaWeekData =
      await loadJSON(
        'maloja.json'
      );

    dvRenderMalojaWeek();

  } catch (error) {
    console.error(
      'Maloja week load failed:',
      error
    );

    const host =
      document.getElementById(
        'malojaWeek'
      );

    if (host) {
      host.innerHTML = `
        <div class="maloja-loading">
          Maloja wandered off.
        </div>
      `;
    }
  }
}


window.addEventListener(
  'load',
  dvLoadMalojaWeek
);


// Refresh occasionally even if Daily Void stays open.
setInterval(
  dvLoadMalojaWeek,
  5 * 60 * 1000
);



// ============================================================
// DAILY_VOID_MACHINE_STATS_V1
// Private dashboard only.
// ============================================================

let dvMachineStatsData = null;


function dvMachineBytes(value) {
  const n = Number(value || 0);

  if (!n) return '—';

  const gib = (
    n / 1024 / 1024 / 1024
  );

  if (gib >= 10) {
    return `${gib.toFixed(1)} GB`;
  }

  return `${gib.toFixed(2)} GB`;
}


function dvMachineUptime(seconds) {
  let value = Math.max(
    0,
    Math.floor(
      Number(seconds || 0)
    )
  );

  const days = Math.floor(
    value / 86400
  );

  value %= 86400;

  const hours = Math.floor(
    value / 3600
  );

  const minutes = Math.floor(
    (value % 3600) / 60
  );

  if (days) {
    return `${days}d ${hours}h`;
  }

  if (hours) {
    return `${hours}h ${minutes}m`;
  }

  return `${minutes}m`;
}


function dvMachineMetric(
  label,
  value
) {
  return `
    <div class="machine-metric">
      <span class="machine-metric-label">
        ${esc(label)}
      </span>

      <span class="machine-metric-value">
        ${esc(value)}
      </span>
    </div>
  `;
}


function dvMachineBlock(
  title,
  machine
) {
  if (!machine) {
    return '';
  }

  if (!machine.online) {
    return `
      <div class="machine-stats-host">
        <div class="machine-stats-name">
          ${esc(title)}
          <span class="machine-stat-offline">
            OFFLINE
          </span>
        </div>
      </div>
    `;
  }

  const memory =
    machine.memory || {};

  const disk =
    machine.disk || {};

  const gpu =
    machine.gpu;

  const nvidia =
    Array.isArray(machine.nvidia)
      ? machine.nvidia
      : [];


  let gpuHtml = '';

  if (gpu) {
    const vram =
      gpu.vram_used_bytes
      && gpu.vram_total_bytes
        ? (
            `${dvMachineBytes(
              gpu.vram_used_bytes
            )} / `
            + `${dvMachineBytes(
              gpu.vram_total_bytes
            )}`
          )
        : '—';

    gpuHtml = `
      <div class="machine-gpu-block">

        <div class="machine-gpu-name">
          AMD GPU
        </div>

        <div class="machine-gpu-row">

        ${dvMachineMetric(
          'GPU',
          gpu.util_percent == null
            ? '—'
            : `${gpu.util_percent.toFixed(0)}%`
        )}

        ${dvMachineMetric(
          'HOTSPOT',
          gpu.hotspot_c == null
            ? '—'
            : `${gpu.hotspot_c.toFixed(0)}°`
        )}

        ${dvMachineMetric(
          'VRAM',
          vram
        )}

        ${dvMachineMetric(
          'POWER',
          gpu.power_w == null
            ? '—'
            : `${gpu.power_w.toFixed(0)} W`
        )}

        </div>

      </div>
    `;
  }


  const nvidiaHtml = nvidia
    .map(card => {

      const vram =
        card.vram_used_bytes
        && card.vram_total_bytes
          ? (
              `${dvMachineBytes(
                card.vram_used_bytes
              )} / `
              + `${dvMachineBytes(
                card.vram_total_bytes
              )}`
            )
          : '—';

      return `
        <div class="machine-gpu-block">

          <div class="machine-gpu-name">
            ${esc(
              card.name
              || 'NVIDIA GPU'
            )}
          </div>

          <div class="machine-gpu-row">

            ${dvMachineMetric(
              'GPU',
              card.util_percent == null
                ? '—'
                : `${card.util_percent.toFixed(0)}%`
            )}

            ${dvMachineMetric(
              'TEMP',
              card.temperature_c == null
                ? '—'
                : `${card.temperature_c.toFixed(0)}°`
            )}

            ${dvMachineMetric(
              'VRAM',
              vram
            )}

            ${dvMachineMetric(
              'POWER',
              card.power_w == null
                ? '—'
                : `${card.power_w.toFixed(0)} W`
            )}

          </div>

        </div>
      `;
    })
    .join('');


  return `
    <div class="machine-stats-host">

      <div class="machine-stats-name">
        ${esc(title)}

        <span class="machine-stats-uptime">
          up ${esc(
            dvMachineUptime(
              machine.uptime_seconds
            )
          )}
        </span>
      </div>

      <div class="machine-stats-row">

        ${dvMachineMetric(
          'CPU',
          machine.cpu_percent == null
            ? '—'
            : `${machine.cpu_percent.toFixed(0)}%`
        )}

        ${dvMachineMetric(
          'LOAD',
          (
            `${Number(
              machine.load_1 || 0
            ).toFixed(2)}`
            + ` / ${machine.cores || '?'}c`
          )
        )}

        ${dvMachineMetric(
          'RAM',
          memory.percent == null
            ? '—'
            : `${memory.percent.toFixed(0)}%`
        )}

        ${dvMachineMetric(
          'DISK',
          disk.percent == null
            ? '—'
            : `${disk.percent.toFixed(0)}%`
        )}

      </div>

      ${gpuHtml}
      ${nvidiaHtml}

    </div>
  `;
}


function dvFindServerCard() {
  const candidates = [
    ...document.querySelectorAll(
      '.card,'
      + '.dashboard-card,'
      + '[data-card],'
      + 'article,'
      + 'section'
    )
  ];

  const matches = candidates
    .filter(element => {
      const text =
        (
          element.textContent
          || ''
        ).toUpperCase();

      return (
        text.includes('SERVER')
        &&
        text.includes('SERVER 1')
        &&
        text.includes('SERVER 2')
      );
    })
    .sort(
      (a, b) =>
        a.textContent.length
        - b.textContent.length
    );

  return matches[0] || null;
}


function dvRenderMachineStats() {
  const card =
    dvFindServerCard();

  if (
    !card
    || !dvMachineStatsData
  ) {
    return;
  }

  let panel =
    card.querySelector(
      '.machine-stats-panel'
    );

  if (!panel) {
    panel =
      document.createElement(
        'div'
      );

    panel.className =
      'machine-stats-panel';

    const heading =
      card.querySelector(
        '.card-header,'
        + '.card-head'
      );

    if (heading) {
      heading.after(panel);
    } else {
      card.append(panel);
    }
  }


  panel.innerHTML = `
    ${dvMachineBlock(
      'SERVER 1',
      dvMachineStatsData.server1
    )}

    ${dvMachineBlock(
      'SERVER 2',
      dvMachineStatsData.server2
    )}
  `;
}


async function dvLoadMachineStats() {
  try {
    dvMachineStatsData =
      await loadJSON(
        'machine_stats.json'
      );

    dvRenderMachineStats();

  } catch (error) {
    console.error(
      'Machine stats load failed:',
      error
    );
  }
}


window.addEventListener(
  'load',
  () => {
    setTimeout(
      dvLoadMachineStats,
      300
    );
  }
);


setInterval(
  dvLoadMachineStats,
  120000
);


// The dashboard renderer may recreate the SERVER card.
if (
  typeof render === 'function'
  && !window.__dvMachineStatsWrapped
) {
  window.__dvMachineStatsWrapped = true;

  const dvMachineOriginalRender =
    render;

  render = function(...args) {
    const result =
      dvMachineOriginalRender(
        ...args
      );

    setTimeout(
      dvRenderMachineStats,
      0
    );

    return result;
  };
}

