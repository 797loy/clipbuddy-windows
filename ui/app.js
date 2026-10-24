/* 剪贴宝前端逻辑。后端通过 window.pywebview.api 暴露；直接用浏览器打开 index.html 会进入演示模式。 */
'use strict';

const $ = (s) => document.querySelector(s);
const PETS = { cat: '🐱', dog: '🐶', bear: '🐻', rabbit: '🐰', fox: '🦊', panda: '🐼', mix: '🐾', none: '' };
const PET_NAMES = { cat: '猫', dog: '狗', bear: '熊', rabbit: '兔', fox: '狐', panda: '熊猫', mix: '混合', none: '无图标' };
const MIX = ['🐱', '🐶', '🐻', '🐰', '🦊', '🐼'];
const THEMES = { auto: ['🌓', '跟随系统'], light: ['☀️', '浅色'], dark: ['🌙', '深色'] };
const ICON_MORE = '<svg viewBox="0 0 24 24"><circle cx="5.5" cy="12" r="1.9"/><circle cx="12" cy="12" r="1.9"/><circle cx="18.5" cy="12" r="1.9"/></svg>';

let S = { history: [], favorites: [], settings: { theme: 'auto', pet: 'cat', max_items: 20, position: 'cursor', auto_hide: true, autostart: false }, env: { hotkeys: { toggle: [], clear: [] } } };
let tab = 'history', query = '', sel = 0, kbd = false, view = [], cat = '全部';
let api = null;

/* ───────── 后端调用 ───────── */
async function call(name, ...args) {
  try { return await api[name](...args); } catch (e) { console.error(name, e); }
}
function setState(s) { if (s && s.history) { S = s; applyTheme(); render(); } }
async function refresh() { setState(await call('get_state')); }

/* ───────── 主题（就地切换，不刷新） ───────── */
const mq = window.matchMedia('(prefers-color-scheme: dark)');
function applyTheme() {
  const t = S.settings.theme;
  const dark = t === 'dark' || (t === 'auto' && mq.matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  $('#themeIcon').textContent = THEMES[t][0];
  $('#petIcon').textContent = S.settings.pet === 'none' ? '∅' : (PETS[S.settings.pet] || '🐾');
}
mq.addEventListener('change', applyTheme);

/* ───────── 工具函数 ───────── */
function typeOf(text) {
  const t = text.trim();
  if (/^https?:\/\/\S+$/i.test(t) || /^www\.\S+\.\S+$/i.test(t)) return ['链接', 'link'];
  if (/^[\w.+-]+@[\w-]+(\.[\w-]+)+$/.test(t)) return ['邮箱', 'mail'];
  if (/^1[3-9]\d{9}$/.test(t)) return ['手机号', 'num'];
  if (/^[\d\s.,+\-()¥$€%:/]+$/.test(t)) return ['数字', 'num'];
  if (/[{};]\s*$/m.test(t) && /\n/.test(t) || /^\s*(def |class |import |from |function |const |let |var |#include|<\/?\w+)/m.test(t) || /=>|<\/\w+>/.test(t)) return ['代码', 'code'];
  return ['文本', 'text'];
}
function ago(ts) {
  const d = Math.max(0, Date.now() / 1000 - ts);
  if (d < 45) return '刚刚';
  if (d < 3600) return Math.round(d / 60) + ' 分钟前';
  if (d < 86400) return Math.floor(d / 3600) + ' 小时前';
  const dt = new Date(ts * 1000), now = new Date();
  const hm = String(dt.getHours()).padStart(2, '0') + ':' + String(dt.getMinutes()).padStart(2, '0');
  if (d < 172800 && now.getDate() !== dt.getDate()) return '昨天 ' + hm;
  return (dt.getMonth() + 1) + '月' + dt.getDate() + '日';
}
function hash(s) { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0; return Math.abs(h); }
function petFor(it, i) {
  const p = S.settings.pet;
  if (p === 'none') return null;
  return p === 'mix' ? MIX[hash(it.id) % MIX.length] : PETS[p];
}
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

/* ───────── 渲染 ───────── */
function render() {
  const src = tab === 'history' ? S.history : S.favorites;
  const q = query.trim().toLowerCase();
  view = src.filter((it) =>
    (cat === '全部' || typeOf(it.text)[0] === cat) &&
    (!q || it.text.toLowerCase().includes(q))
  );
  if (sel >= view.length) sel = view.length - 1;
  if (sel < 0) sel = 0;
  renderCats();

  $('#cntH').textContent = S.history.length;
  $('#cntF').textContent = S.favorites.length;
  $('#footBtn').textContent = tab === 'history' ? '清空历史' : '＋ 新建常用语';
  $('#footBtn').className = 'link' + (tab === 'history' ? ' danger' : '');
  $('#footBtn').style.visibility = (tab === 'history' && !S.history.length) ? 'hidden' : 'visible';
  moveThumb();

  const list = $('#list');
  const frag = document.createDocumentFragment();
  if (!view.length) {
    const e = el('div', 'empty');
    const msg = q ? ['🔍', '没有找到匹配的内容', '换个关键词试试'] :
      cat !== '全部' ? ['🏷️', '该分类下没有内容', '切换到「全部」查看'] :
      tab === 'history' ? ['✂️', '还没有复制记录', '复制一段文字，它就会出现在这里'] :
        ['⭐', '还没有常用语', '在卡片的 ⋯ 菜单里加入，或点右下角新建'];
    e.append(el('div', 'big', msg[0]));
    const b = el('b', null, msg[1]);
    e.append(b, document.createTextNode(msg[2]));
    frag.append(e);
  }
  view.forEach((it, i) => frag.append(card(it, i)));
  list.replaceChildren(frag);
}

function renderCats() {
  document.querySelectorAll('#cats button').forEach((b) => b.classList.toggle('on', b.dataset.cat === cat));
}
document.querySelectorAll('#cats button').forEach((b) => b.addEventListener('click', () => {
  cat = b.dataset.cat; sel = 0; kbd = false; render(); $('#list').scrollTop = 0;
}));

function card(it, i) {
  const c = el('div', 'card' + ((kbd || query) && i === sel ? ' sel' : ''));
  c.dataset.i = i;
  const pet = petFor(it, i);
  c.append(pet ? el('div', 'pet', pet) : el('div', 'pet num', String(i + 1)));

  const body = el('div', 'body');
  body.append(el('div', 'text', it.text.replace(/^\s+/, '').slice(0, 400)));
  const meta = el('div', 'meta');
  const [label, cls] = typeOf(it.text);
  meta.append(el('span', 'chip ' + cls, label));
  meta.append(el('span', null, ago(it.ts)));
  meta.append(el('span', null, it.text.length + ' 字'));
  if (tab === 'history' && it.fav) meta.append(el('span', 'star', '★'));
  body.append(meta);
  c.append(body);

  const more = el('button', 'more');
  more.innerHTML = ICON_MORE;
  more.title = '更多操作';
  more.addEventListener('click', (e) => { e.stopPropagation(); openItemMenu(it, more.getBoundingClientRect()); });
  c.append(more);

  c.addEventListener('click', () => pasteItem(it));
  c.addEventListener('contextmenu', (e) => { e.preventDefault(); openItemMenu(it, { right: e.clientX, bottom: e.clientY, top: e.clientY }); });
  return c;
}

function moveThumb() {
  const btn = document.querySelector('#tabs button[data-tab="' + tab + '"]');
  const thumb = document.querySelector('#tabs .thumb');
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b === btn));
  thumb.style.width = btn.offsetWidth + 'px';
  thumb.style.transform = 'translateX(' + (btn.offsetLeft - 3) + 'px)';
}

/* ───────── 菜单 ───────── */
const menu = $('#menu'), scrim = $('#scrim');
function openMenu(items, anchor) {
  menu.replaceChildren();
  items.forEach((m) => {
    if (m === '-') { menu.append(document.createElement('hr')); return; }
    const b = el('button', m.danger ? 'danger' : '');
    b.append(el('span', 'ico', m.icon || ''), el('span', null, m.label));
    if (m.checked) b.append(el('span', 'tick', '✓'));
    b.addEventListener('click', () => { closeMenu(); m.run(); });
    menu.append(b);
  });
  menu.classList.add('on'); scrim.classList.add('on');
  const w = menu.offsetWidth, h = menu.offsetHeight;
  let x = anchor.right - w, y = anchor.bottom + 6;
  x = Math.max(8, Math.min(x, innerWidth - w - 8));
  if (y + h > innerHeight - 8) y = Math.max(8, anchor.top - h - 6);
  menu.style.left = x + 'px'; menu.style.top = y + 'px';
}
function closeMenu() { menu.classList.remove('on'); scrim.classList.remove('on'); }
scrim.addEventListener('click', closeMenu);
scrim.addEventListener('contextmenu', (e) => { e.preventDefault(); closeMenu(); });

function openItemMenu(it, rect) {
  const inFav = tab === 'fav' || it.fav;
  openMenu([
    { icon: '📄', label: '仅复制', run: () => copyOnly(it) },
    { icon: inFav ? '☆' : '⭐', label: inFav ? '移出常用语' : '加入常用语', run: () => toggleFav(it) },
    '-',
    { icon: '🗑', label: tab === 'fav' ? '删除常用语' : '删除', danger: true, run: () => removeItem(it) },
  ], rect);
}

/* ───────── 条目操作 ───────── */
const srcName = () => (tab === 'history' ? 'history' : 'fav');
function pasteItem(it) { call('paste', srcName(), it.id); }
async function copyOnly(it) { setState(await call('copy_only', srcName(), it.id)); toast('已复制，可手动 Ctrl+V'); }
async function toggleFav(it) {
  const was = tab === 'fav' || it.fav;
  setState(await call('toggle_fav', srcName(), it.id));
  toast(was ? '已移出常用语' : '已加入常用语');
}
async function removeItem(it) { setState(await call('delete', srcName(), it.id)); toast('已删除'); }
async function clearAll() {
  if (!S.history.length) return;
  setState(await call('clear_history'));
  toast('已清空历史', { action: '撤销', run: async () => { setState(await call('undo_clear')); }, ms: 5000 });
}

/* ───────── Toast ───────── */
let toastTimer;
function toast(msg, opt = {}) {
  $('#toastMsg').textContent = msg;
  const act = $('#toastAct');
  act.className = opt.action ? 'show' : '';
  act.textContent = opt.action || '';
  act.onclick = () => { hideToast(); opt.run && opt.run(); };
  $('#toast').classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(hideToast, opt.ms || 1600);
}
function hideToast() { $('#toast').classList.remove('on'); }
window.toast = toast;

/* ───────── 设置面板 / 新建常用语 ───────── */
const sheet = $('#sheet'), composer = $('#composer');
function seg(options, current, onPick) {
  const wrap = el('div', 'mini-seg');
  options.forEach(([val, label]) => {
    const b = el('button', val === current ? 'on' : '', label);
    b.addEventListener('click', () => onPick(val));
    wrap.append(b);
  });
  return wrap;
}
function row(title, sub, control) {
  const r = el('div', 'srow');
  const left = el('div');
  left.append(el('span', null, title));
  if (sub) left.append(el('small', null, sub));
  r.append(left);
  if (control) r.append(control);
  return r;
}
function toggle(on, onPick) {
  const s = el('button', 'switch' + (on ? ' on' : ''));
  s.addEventListener('click', () => onPick(!on));
  return s;
}
function buildSheet() {
  const st = S.settings, body = $('#sheetBody');
  body.replaceChildren(
    row('历史保留条数', '超出后自动清理最旧的', seg([[10, '10'], [20, '20'], [50, '50'], [100, '100']], st.max_items, (v) => setSetting('max_items', v))),
    row('呼出位置', null, seg([['cursor', '鼠标附近'], ['center', '屏幕居中']], st.position, (v) => setSetting('position', v))),
    row('点击外部自动收起', null, toggle(st.auto_hide, (v) => setSetting('auto_hide', v))),
    row('开机自启', '登录 Windows 后在后台运行', toggle(st.autostart, (v) => setSetting('autostart', v))),
  );
  const hk = S.env.hotkeys, fmt = (a) => a.map((k) => k.replace(/\b\w/g, (c) => c.toUpperCase())).join(' / ');
  const note = el('div', 'srow note');
  note.append(document.createTextNode('呼出 / 隐藏：' + fmt(hk.toggle || [])), document.createElement('br'),
    document.createTextNode('清空历史：' + fmt(hk.clear || [])), document.createElement('br'),
    document.createTextNode('↑↓ 选择，Enter 粘贴，Ctrl+1…9 快速粘贴，Esc 关闭'), document.createElement('br'),
    document.createTextNode('剪贴宝 v' + ((S.env && S.env.version) || '1.1.0')));
  const quit = el('div', 'srow');
  const qb = el('button', 'btn danger', '退出程序');
  qb.addEventListener('click', () => call('quit_app'));
  quit.append(el('span', null, '完全退出后台运行'), qb);
  body.append(note, quit);
}
async function setSetting(key, val) { setState(await call('set_setting', key, val)); buildSheet(); }
function openSheet() { closeMenu(); buildSheet(); sheet.classList.add('on'); scrim.classList.add('on'); scrim.dataset.for = 'sheet'; }
function closeSheet() { sheet.classList.remove('on'); if (scrim.dataset.for === 'sheet') { scrim.classList.remove('on'); scrim.dataset.for = ''; } }
scrim.addEventListener('click', () => { closeSheet(); closeComposer(); });

function openComposer() { $('#phraseInput').value = ''; composer.classList.add('on'); scrim.classList.add('on'); scrim.dataset.for = 'composer'; setTimeout(() => $('#phraseInput').focus(), 60); }
function closeComposer() { composer.classList.remove('on'); if (scrim.dataset.for === 'composer') { scrim.classList.remove('on'); scrim.dataset.for = ''; } }
async function savePhrase() {
  const v = $('#phraseInput').value;
  if (!v.trim()) return;
  setState(await call('add_phrase', v));
  closeComposer(); toast('已保存到常用语');
}

/* ───────── 顶栏下拉 ───────── */
$('#themeBtn').addEventListener('click', (e) => {
  const r = e.currentTarget.getBoundingClientRect();
  openMenu(Object.entries(THEMES).map(([k, [ic, name]]) => ({
    icon: ic, label: name, checked: S.settings.theme === k,
    run: () => { S.settings.theme = k; applyTheme(); call('set_setting', 'theme', k); },   // 就地生效
  })), r);
});
$('#petBtn').addEventListener('click', (e) => {
  const r = e.currentTarget.getBoundingClientRect();
  openMenu(Object.keys(PETS).map((k) => ({
    icon: PETS[k] || '∅', label: PET_NAMES[k], checked: S.settings.pet === k,
    run: () => { S.settings.pet = k; applyTheme(); render(); call('set_setting', 'pet', k); },
  })), r);
});
$('#gearBtn').addEventListener('click', openSheet);
$('#sheetClose').addEventListener('click', closeSheet);
$('#closeBtn').addEventListener('click', () => call('hide'));
$('#phraseCancel').addEventListener('click', closeComposer);
$('#phraseSave').addEventListener('click', savePhrase);
$('#footBtn').addEventListener('click', () => (tab === 'history' ? clearAll() : openComposer()));

document.querySelectorAll('#tabs button').forEach((b) => b.addEventListener('click', () => {
  tab = b.dataset.tab; sel = 0; kbd = false; render(); $('#list').scrollTop = 0;
}));
$('#q').addEventListener('input', (e) => { query = e.target.value; sel = 0; render(); });

/* ───────── 键盘 ───────── */
function anyOverlay() { return menu.classList.contains('on') || sheet.classList.contains('on') || composer.classList.contains('on'); }
document.addEventListener('keydown', (e) => {
  if (e.isComposing) return;
  if (composer.classList.contains('on')) {
    if (e.key === 'Escape') closeComposer();
    else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) savePhrase();
    return;
  }
  if (e.key === 'Escape') {
    if (menu.classList.contains('on')) closeMenu();
    else if (sheet.classList.contains('on')) closeSheet();
    else if (query) { query = ''; $('#q').value = ''; render(); }
    else call('hide');
    return;
  }
  if (anyOverlay()) return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    if (!view.length) return;
    kbd = true;
    sel = e.key === 'ArrowDown' ? Math.min(view.length - 1, sel + 1) : Math.max(0, sel - 1);
    render();
    const c = document.querySelector('.card.sel'); if (c) c.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter' && view[sel]) {
    e.preventDefault(); pasteItem(view[sel]);
  } else if (e.ctrlKey && /^[1-9]$/.test(e.key) && view[+e.key - 1]) {
    e.preventDefault(); pasteItem(view[+e.key - 1]);
  } else if (e.key === 'Tab') {
    e.preventDefault(); tab = tab === 'history' ? 'fav' : 'history'; sel = 0; render();
  }
});
document.addEventListener('contextmenu', (e) => e.preventDefault());

/* ───────── 后端回调 ───────── */
window.onShow = async () => {
  const shell = $('#shell');
  shell.classList.remove('enter'); void shell.offsetWidth; shell.classList.add('enter');
  closeMenu(); closeSheet(); closeComposer(); hideToast();
  query = ''; $('#q').value = ''; sel = 0; kbd = false; cat = '全部';
  await refresh();
  $('#list').scrollTop = 0;
  $('#q').focus();
};
window.onChanged = () => refresh();

/* ───────── 启动 ───────── */
function boot() {
  api = window.pywebview.api;
  refresh().then(() => $('#q').focus());
}
if (window.pywebview && window.pywebview.api) boot();
else window.addEventListener('pywebviewready', boot);

/* 浏览器直接打开 index.html 时的演示数据，方便调 UI */
if (!/pywebview/i.test(navigator.userAgent) && location.protocol === 'file:') {
  setTimeout(() => {
    if (api) return;
    const now = Math.floor(Date.now() / 1000), mk = (t, ago) => ({ id: Math.random().toString(36).slice(2, 8), text: t, ts: now - ago });
    const mock = {
      history: [mk('https://github.com/anthropics', 20), mk('你好，下午三点的会议改到四点，请大家准时参加，会议室不变。\n如有冲突请提前告知。', 400),
        mk('def hello():\n    print("hi")', 3000), mk('13812345678', 9000), mk('hello@example.com', 90000)],
      favorites: [mk('北京市海淀区中关村大街 1 号', 5000)],
      settings: { theme: 'auto', pet: 'cat', max_items: 20, position: 'cursor', auto_hide: true, autostart: false },
      env: { hotkeys: { toggle: ['ctrl+shift+v', 'f8'], clear: ['ctrl+shift+c'] } },
    };
    const snap = () => JSON.parse(JSON.stringify(Object.assign({}, mock, { history: mock.history.map((h) => Object.assign({}, h, { fav: mock.favorites.some((f) => f.text === h.text) })) })));
    const find = (s, id) => (s === 'history' ? mock.history : mock.favorites).find((x) => x.id === id);
    let cleared = [];
    api = {
      get_state: async () => snap(), paste: async () => true, hide: async () => true, quit_app: async () => true,
      copy_only: async () => snap(),
      toggle_fav: async (s, id) => { const it = find(s, id); const i = mock.favorites.findIndex((f) => f.text === it.text); i >= 0 ? mock.favorites.splice(i, 1) : mock.favorites.unshift(Object.assign({}, it, { id: id + 'f' })); return snap(); },
      delete: async (s, id) => { const l = s === 'history' ? mock.history : mock.favorites; l.splice(l.findIndex((x) => x.id === id), 1); return snap(); },
      clear_history: async () => { cleared = mock.history; mock.history = []; return snap(); },
      undo_clear: async () => { mock.history = cleared; return snap(); },
      add_phrase: async (t) => { mock.favorites.unshift(mk(t, 0)); return snap(); },
      set_setting: async (k, v) => { mock.settings[k] = v; return snap(); },
    };
    refresh();
  }, 300);
}
