// Steady Hand console: polls /state about ten times a second and sends one-line commands to /cmd.
// Data and wording rules: docs/steady-contract.md. Every key may be missing on an older controller.
// A classic script on purpose: render() and poll() are globals, so tests can replace them.
const $ = id => document.getElementById(id);
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const fixed = (v, d) => Number.isFinite(v) ? v.toFixed(d) : '–';
const num = v => Number.isFinite(v) ? v : NaN;
const FONT = '12px "Segoe UI", system-ui, sans-serif';
const JOINTS = ['Shoulder turn', 'Shoulder lift', 'Elbow', 'Wrist bend', 'Wrist roll'];
const timeout = ms => AbortSignal.timeout ? AbortSignal.timeout(ms) : undefined;  // Safari before 16 has no AbortSignal.timeout

let link = 'wait';            // 'live' | 'down' (no good state for 2 s) | 'broken' (state arrives, drawing it failed) | 'wait'
let lastOk = 0, lastGood = null, sessions = [];
const sliders = {gain: {dragging: false, sentAt: 0}, cut: {dragging: false, sentAt: 0}};

// ---------- commands ----------
let noteTimer = 0;
function note(text) { $('cmdnote').textContent = text; clearTimeout(noteTimer); if (text) noteTimer = setTimeout(() => note(''), 6000); }
async function send(line) {
  try {
    const r = await fetch('/cmd?' + encodeURIComponent(line), {cache: 'no-store', signal: timeout(2000)});
    const reply = await r.json().catch(() => ({}));
    if (!r.ok || reply.ok === false) note('The controller did not accept “' + line + '”' + (reply.reason ? ': ' + reply.reason : '.'));
    else note('');
  } catch (e) { note('Could not reach the controller to send “' + line + '”.'); }
}
document.addEventListener('click', e => {
  const b = e.target.closest('[data-cmd]');
  if (b && !b.disabled) send(b.dataset.cmd);
});
$('status-act').addEventListener('click', e => { if (e.currentTarget.dataset.act === 'reload') location.reload(); });
$('griphold').onclick = e => send('grip hold ' + (e.currentTarget.getAttribute('aria-checked') === 'true' ? 'off' : 'on'));
for (const [id, label, cmd, d, unit] of [['gain', 'gainv', 'gain', 1, '×'], ['cut', 'cutv', 'cutoff', 1, ' Hz']]) {
  $(id).oninput = e => { sliders[id].dragging = true; $(label).textContent = (+e.target.value).toFixed(d) + unit; };
  $(id).onchange = e => { send(cmd + ' ' + (+e.target.value).toFixed(d)); sliders[id].dragging = false; sliders[id].sentAt = Date.now(); };
}
let pickTimer = 0;  // arrow keys on a closed select fire "change" at every step: switch only once the choice settles
$('userpick').onchange = e => { clearTimeout(pickTimer); pickTimer = setTimeout(() => send('user ' + e.target.value), 800); };
$('adduser').onsubmit = e => {
  e.preventDefault();
  const name = $('newname').value.trim(), ok = /^[A-Za-z0-9 -]{1,24}$/.test(name);
  $('newname').setAttribute('aria-invalid', String(!ok));
  if (!ok) { $('namenote').textContent = 'Use letters, digits, spaces and dashes; up to 24 characters.'; return; }
  $('namenote').textContent = 'Letters, digits, spaces and dashes; up to 24 characters.';
  send('user ' + name); $('newname').value = '';
};
let calSeenRunning = false, calClosed = false;
$('cal-close').onclick = () => { calClosed = true; $('procedure').hidden = true; };

// ---------- the 3D view (dashboard/arm3d.js, owned by the 3D lane); the 2D side view is the fallback ----------
let view = null;
function fallback() { try { view && view.dispose && view.dispose(); } catch (e) {} view = null; $('arm3d').hidden = true; $('arms').hidden = false; $('viewnote').hidden = false; }
const webgl = (() => { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (e) { return false; } })();
(webgl ? import('/dashboard/arm3d.js') : Promise.reject())
  .then(m => { view = m.mount($('arm3d')); if (!view || typeof view.update !== 'function') throw 0; })
  .catch(fallback);

// ---------- drawing ----------
function fit(canvas) {  // sharp lines on high-density screens; the CSS decides the size
  const ratio = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== Math.round(w * ratio) || canvas.height !== Math.round(h * ratio)) { canvas.width = Math.round(w * ratio); canvas.height = Math.round(h * ratio); }
  const ctx = canvas.getContext('2d'); ctx.setTransform(ratio, 0, 0, ratio, 0, 0); ctx.clearRect(0, 0, w, h);
  return [ctx, w, h];
}
function line(ctx, points, colour, width) {
  ctx.strokeStyle = colour; ctx.lineWidth = width; ctx.lineJoin = ctx.lineCap = 'round'; ctx.beginPath();
  points.forEach(([a, b], i) => i ? ctx.lineTo(a, b) : ctx.moveTo(a, b)); ctx.stroke();
}
function shake(values) {  // take away a one-second running average: the slow reach goes, the shake stays
  return values.map((v, i) => { const part = values.slice(Math.max(0, i - 5), i + 6); return v - part.reduce((a, b) => a + b, 0) / part.length; });
}
function traces(history) {  // both channels on one scale, so a flat arm line means a still arm
  const end = history.length ? history[history.length - 1][0] : 0, recent = history.filter(p => p[0] >= end - 6.5);
  const hand = shake(recent.map(p => p[1])).slice(5, -5), arm = shake(recent.map(p => p[2])).slice(5, -5);
  const reach = Math.max(4, ...hand.map(Math.abs), ...arm.map(Math.abs));  // a fixed ±4 mm ruler unless the shake is bigger
  for (const [id, values, colour, width] of [['tracehand', hand, css('--raw'), 1.8], ['tracearm', arm, css('--plum'), 2.4]]) {
    const [ctx, w, h] = fit($(id));
    ctx.strokeStyle = css('--line'); ctx.lineWidth = 1;
    for (const y of [3, h / 2, h - 3]) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
    if (values.length > 1) line(ctx, values.map((v, i) => [i / (values.length - 1) * w, h / 2 - v / reach * (h / 2 - 3)]), colour, width);
  }
  setText('scalenote', 'Both traces: last 6 s, the same scale; each band spans ±' + reach.toFixed(1) + ' mm.');
}
function chart(history) {
  const [ctx, w, h] = fit($('chart')), left = 52, top = 8, bottom = h - 22;
  ctx.fillStyle = css('--soft'); ctx.font = FONT;
  ctx.fillText('30 s ago', left, h - 4); ctx.textAlign = 'right'; ctx.fillText('now', w, h - 4); ctx.textAlign = 'left';
  if (history.length < 2) return;
  const t1 = history[history.length - 1][0], t0 = t1 - 30;
  history = history.filter(p => p[0] >= t0);
  const values = history.flatMap(p => [p[1], p[2]]);
  let lo = Math.min(...values), hi = Math.max(...values);
  if (hi - lo < 20) { const mid = (hi + lo) / 2; lo = mid - 10; hi = mid + 10; }
  const x = t => left + (t - t0) / 30 * (w - left), y = v => bottom - (v - lo) / (hi - lo) * (bottom - top);
  ctx.strokeStyle = css('--line'); ctx.lineWidth = 1;
  for (let i = 0; i < 4; i++) { const v = top + (bottom - top) * i / 3; ctx.beginPath(); ctx.moveTo(left, v); ctx.lineTo(w, v); ctx.stroke(); }
  ctx.fillText(Math.round(hi) + ' mm', 0, top + 4); ctx.fillText(Math.round(lo) + ' mm', 0, bottom + 4);
  line(ctx, history.map(p => [x(p[0]), y(p[1])]), css('--raw'), 1.4);
  line(ctx, history.map(p => [x(p[0]), y(p[2])]), css('--plum'), 2.4);
}
function arms(raw, out) {  // the 2D fallback: a side view tilted a little toward the viewer
  const [ctx, w, h] = fit($('arms'));
  if (!Array.isArray(raw) || !raw.length) return;
  const scale = Math.min(w / 520, h / 420), px = p => [w * 0.22 + (p[0] - 0.45 * p[1]) * scale, h - 26 - (p[2] + 0.25 * p[1]) * scale];
  ctx.strokeStyle = css('--line'); ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(8, h - 26); ctx.lineTo(w - 8, h - 26); ctx.stroke();
  for (const [chain, colour, width, alpha] of [[raw, css('--raw'), 3, 0.55], [Array.isArray(out) ? out : [], css('--plum'), 6, 1]]) {
    ctx.globalAlpha = alpha; ctx.fillStyle = colour; line(ctx, chain.map(px), colour, width);
    chain.forEach(p => { const [a, b] = px(p); ctx.beginPath(); ctx.arc(a, b, width * 0.75, 0, 7); ctx.fill(); });
  }
  ctx.globalAlpha = 1;
}
function trendChart(trend) {  // shake in the top band, grip effort in the bottom band; time from the rows' own stamps
  const has = Array.isArray(trend) && trend.length > 1;
  $('notrend').hidden = has; $('trendbox').hidden = !has;
  if (!has) { setText('trendspan', 'about one point a second'); return; }
  const [ctx, w, h] = fit($('trendchart')), left = 56, top = 8, split = Math.round(h * 0.6), gtop = split + 22, bottom = h - 22;
  const t1 = trend[trend.length - 1][0], span = Math.max(60, t1 - trend[0][0]), x = t => left + (t - (t1 - span)) / span * (w - left);
  const hi = Math.max(1, ...trend.flatMap(p => [p[1], p[2]])) * 1.15, y = v => split - v / hi * (split - top);
  const g = v => bottom - Math.min(100, Math.max(0, v)) / 100 * (bottom - gtop);
  ctx.strokeStyle = css('--line'); ctx.lineWidth = 1;
  for (const v of [top, split, gtop, bottom]) { ctx.beginPath(); ctx.moveTo(left, v); ctx.lineTo(w, v); ctx.stroke(); }
  ctx.fillStyle = '#e4dacd'; ctx.beginPath(); ctx.moveTo(x(trend[0][0]), bottom);
  trend.forEach(p => ctx.lineTo(x(p[0]), g(p[3] || 0))); ctx.lineTo(x(t1), bottom); ctx.closePath(); ctx.fill();
  line(ctx, trend.map(p => [x(p[0]), g(p[3] || 0)]), '#b3a596', 1.2);
  line(ctx, trend.map(p => [x(p[0]), y(p[1])]), css('--raw'), 1.6);
  line(ctx, trend.map(p => [x(p[0]), y(p[2])]), css('--plum'), 2.4);
  ctx.fillStyle = css('--soft'); ctx.font = FONT;
  ctx.fillText(hi.toFixed(1) + ' mm', 0, top + 8); ctx.fillText('0 mm', 0, split + 4);
  ctx.fillText('100% grip', 0, gtop + 8); ctx.fillText('0%', 0, bottom + 4);
  const ago = span < 120 ? Math.round(span) + ' s ago' : Math.round(span / 60) + ' min ago';
  ctx.fillText(ago, left, h - 4); ctx.textAlign = 'right'; ctx.fillText('now', w, h - 4); ctx.textAlign = 'left';
  setText('trendspan', 'about one point a second, ' + trend.length + ' points over the last ' + ago.replace(' ago', ''));
}
function sessionChart(list) {
  const [ctx, w, h] = fit($('sessionchart'));
  const hi = Math.max(1, ...list.flatMap(s => [num(s.mean_tremor_mm), num(s.mean_arm_mm)]).filter(Number.isFinite)) * 1.15;
  const left = 46, top = 10, bottom = h - 22;
  const x = i => list.length < 2 ? (left + w) / 2 : left + 6 + i / (list.length - 1) * (w - left - 12), y = v => bottom - v / hi * (bottom - top);
  ctx.strokeStyle = css('--line'); ctx.lineWidth = 1;
  for (const v of [top, bottom]) { ctx.beginPath(); ctx.moveTo(left, v); ctx.lineTo(w, v); ctx.stroke(); }
  for (const [key, colour] of [['mean_tremor_mm', css('--raw')], ['mean_arm_mm', css('--plum')]]) {
    const pts = list.map((s, i) => [x(i), y(num(s[key]))]).filter(p => Number.isFinite(p[1]));
    line(ctx, pts, colour, 2); ctx.fillStyle = colour;
    pts.forEach(([a, b]) => { ctx.fillRect(a - 3, b - 3, 6, 6); });  // one mark per session
  }
  ctx.fillStyle = css('--soft'); ctx.font = FONT;
  ctx.fillText(hi.toFixed(1) + ' mm', 0, top + 4); ctx.fillText('0 mm', 0, bottom + 4);
  ctx.fillText('oldest', left, h - 4); ctx.textAlign = 'right'; ctx.fillText('newest', w, h - 4); ctx.textAlign = 'left';
}

// ---------- the status strip ----------
const GLYPHS = {
  ok: '<rect x="1.5" y="1.5" width="21" height="21" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M6 12.5l4 4L18 8" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>',
  warn: '<path d="M12 2.8L22.6 21H1.4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M12 9v5.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><circle cx="12" cy="17.7" r="1.4" fill="currentColor"/>',
  pause: '<rect x="1.5" y="1.5" width="21" height="21" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9 7v10M15 7v10" stroke="currentColor" stroke-width="2.8" stroke-linecap="round"/>',
  off: '<circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><path d="M5 19L19 5" stroke="currentColor" stroke-width="2.2"/>',
};
const WORD = {ok: 'Normal', warn: 'Attention', stop: 'Stopped'};
const clock = ms => new Date(ms).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit', second: '2-digit'});
function joinNames(list) { return list.length < 2 ? list[0] : list.slice(0, -1).join(', ') + ' and ' + list[list.length - 1]; }
function statusOf(s) {  // what the arm is doing, in words; the first match wins
  if (link === 'down' || link === 'wait') {
    return {cls: 'stop', glyph: 'off', text: lastOk ? 'Not connected: no numbers since ' + clock(lastOk) + '. The arm may still be moving; watch it.'
      : link === 'wait' ? 'Connecting to the controller…' : 'Not connected: waiting for the controller. Start it with python steady.py.'};
  }
  if (link === 'broken') return {cls: 'stop', glyph: 'off', act: ['Reload the page', null, 'reload'],
    text: 'Not updating: the page could not show the latest numbers' + (lastGood ? ' (last shown ' + clock(lastGood) + ')' : '') + '. The arm may still be moving.'};
  const why = s.why_still || '', phase = s.calibration && s.calibration.phase, limits = Array.isArray(s.limits) ? s.limits.filter(Boolean).map(String) : [];
  if (phase === 'rest' || phase === 'move' || why === 'calibrating')
    return {cls: 'stop', glyph: 'pause', text: 'Calibrating: the arm is held until the steps below finish.', act: ['Cancel calibration', 'calibrate cancel']};
  if (s.hold === true || why === 'holding')
    return {cls: 'stop', glyph: 'pause', text: 'HOLDING: the arm is frozen. Press Continue, or the Hold key, to follow again.', act: ['Continue', 'hold off']};
  if (why === 'limit' || limits.length) {
    const who = limits.length ? joinNames([limits[0][0].toUpperCase() + limits[0].slice(1), ...limits.slice(1)]) : 'A joint';
    const bend = limits.some(n => /elbow|bend|lift/i.test(n)) ? 'bend' : 'go';
    return {cls: 'warn', glyph: 'warn', text: who + (limits.length > 1 ? ' at their limits' : ' at its limit') + ': the arm cannot ' + bend + ' further. Move your hand back, or lower the sensitivity.'};
  }
  if (why === 'easing') return {cls: 'warn', glyph: 'warn', text: 'Easing in: the arm is catching up with your hand gently.'};
  if (s.steady === false) return {cls: 'warn', glyph: 'warn', text: 'Tremor filter OFF: the arm copies the shake.', act: ['Turn the filter on', 'filter on']};
  if (s.steady === true) return {cls: 'ok', glyph: 'ok', text: 'Following your hand, tremor filter on.' + ('why_still' in s ? '' : ' This controller does not report limits.')};
  return {cls: 'warn', glyph: 'warn', text: 'Connected, but this controller does not say whether the arm is following.'};
}
let lastState = {};
function drawStatus() {
  const st = statusOf(lastState), box = $('status'), act = $('status-act');
  if (link === 'live' && lastState.test && lastState.test.running) st.text += ' Hold-still test running: keep the leader still.';  // the test panel is below the fold
  if (box.dataset.class !== st.cls) box.dataset.class = st.cls;
  if ($('glyph').dataset.g !== st.glyph) { $('glyph').innerHTML = GLYPHS[st.glyph]; $('glyph').dataset.g = st.glyph; }
  setText('status-word', WORD[st.cls]); setText('status-text', st.text);
  act.hidden = !st.act;
  if (st.act) {
    setText('status-act', st.act[0]);
    if (st.act[1]) { act.dataset.cmd = st.act[1]; delete act.dataset.act; } else { delete act.dataset.cmd; act.dataset.act = st.act[2]; }
    act.disabled = link !== 'live' && st.act[2] !== 'reload';
  }
}

// ---------- panels ----------
function setText(id, text) { if ($(id).textContent !== text) $(id).textContent = text; }  // keeps live regions quiet
function meter(id, pct) { $(id).style.transform = 'scaleX(' + (Number.isFinite(pct) ? Math.min(100, Math.max(0, pct)) / 100 : 0) + ')'; }
function pressed(id, on) { $(id).setAttribute('aria-pressed', String(on)); }
function duration(sec) { return !Number.isFinite(sec) ? '–' : sec < 60 ? Math.round(sec) + ' s' : sec < 3600 ? Math.floor(sec / 60) + ' min ' + String(Math.round(sec % 60)).padStart(2, '0') + ' s' : Math.floor(sec / 3600) + ' h ' + Math.round(sec % 3600 / 60) + ' min'; }
const mean = list => list.length ? list.reduce((a, b) => a + b, 0) / list.length : NaN;

function measure(s) {
  const phase = s.calibration && s.calibration.phase;
  const hand = num(s.tremor_mm), arm = num(s.out_mm), held = s.hold === true || ['holding', 'calibrating'].includes(s.why_still) || phase === 'rest' || phase === 'move';
  setText('hand', fixed(hand, 1)); setText('arm', fixed(arm, 1));
  setText('freq', hand >= 0.3 && Number.isFinite(s.tremor_hz) ? 'main rate ' + fixed(s.tremor_hz, 1) + ' Hz' : 'no tremor found');
  setText('armnote', held ? 'held still' : s.steady === false ? 'filter off' : '');
  const top = [4, 10, 20, 50].find(v => v >= Math.max(hand || 0, arm || 0)) || 50, step = top / (top === 4 ? 4 : 5);  // one fixed 0-4 mm ruler for the demo
  meter('m-hand', hand / top * 100); meter('m-arm', arm / top * 100);
  const key = String(top);
  if ($('ticks').dataset.top !== key) {
    $('ticks').dataset.top = key;
    const ticks = []; for (let v = 0; v <= top + 1e-9; v += step) ticks.push(v);
    $('ticks').replaceChildren(...ticks.map((v, i) => { const t = document.createElement('span'); t.style.left = v / top * 100 + '%'; t.textContent = (Number.isInteger(v) ? v : v.toFixed(1)) + (i === ticks.length - 1 ? ' mm' : ''); return t; }));
  }
  const tooSmall = !(hand >= 0.15);
  setText('removed', held || tooSmall ? '–' : fixed(s.removed_pct, 0));
  setText('mode', held ? 'Not measured while the arm is held: a frozen arm is not a filtered one.' : tooSmall ? 'Too little shake to measure.'
    : s.steady === false ? 'Filter off: the arm copies the shake, so little is removed.' : '1 − arm ÷ hand, same 4 s window.');
}
function controls(s) {
  pressed('filter-on', s.steady === true); pressed('filter-off', s.steady === false);
  pressed('hold-on', s.hold === true); pressed('hold-off', s.hold === false);
  for (const [id, label, key, d, unit, sentence] of [['gain', 'gainv', 'gain', 1, '×', 'sensitivity'], ['cut', 'cutv', 'cutoff', 1, ' Hz', 'the filter cut-off']]) {
    const has = Number.isFinite(s[key]); $(id).disabled = !has;
    if (!has) { setText(label, '–'); continue; }
    if (!sliders[id].dragging && Date.now() - sliders[id].sentAt > 1000) { $(id).value = s[key]; setText(label, s[key].toFixed(d) + unit); }  // the poll after a change may still carry the old value
  }
  setText('gainnote', Number.isFinite(s.gain) ? 'The arm moves ' + s.gain.toFixed(1) + ' times as far as your hand, around the neutral pose.' : 'This controller does not report sensitivity.');
  $('neutral').disabled = !('gain' in s);  // neutral pose came with sensitivity in contract v2
  setText('neutralnote', 'gain' in s ? 'Your hand\'s pose now becomes the centre that sensitivity scales around.' : 'This controller has no neutral pose to set.');
}
function grip(s) {
  const g = s.grip && typeof s.grip === 'object' ? s.grip : null, follower = Array.isArray(s.follower) ? s.follower : [];
  const claw = g && Number.isFinite(g.claw_pct) ? g.claw_pct : num(follower[5]);
  setText('g-squeeze', g ? fixed(g.squeeze_pct, 0) + ' %' : '–'); meter('gm-squeeze', g ? g.squeeze_pct : NaN);
  setText('g-held', g ? (g.hold === false ? 'off' : fixed(g.held_pct, 0) + ' %') : '–'); meter('gm-held', g && g.hold !== false ? g.held_pct : NaN);
  setText('g-claw', Number.isFinite(claw) ? Math.round(claw) + ' % open' : '–'); meter('gm-claw', claw);
  $('griphold').setAttribute('aria-checked', String(!!(g && g.hold))); $('griphold').disabled = !g; $('letgo').disabled = !g;
  setText('gripnote', !g ? 'This controller does not report the grip; only the claw opening is shown.'
    : g.hold ? 'The claw keeps your tightest squeeze until you open your hand wide or press Let go.' : 'Grip hold is off: the claw copies the trigger.');
  const parts = [];
  if (Number.isFinite(s.grip_effort)) parts.push('claw ' + Math.round(s.grip_effort) + ' %');
  if (Number.isFinite(s.arm_load)) parts.push('hardest-working joint ' + Math.round(s.arm_load) + ' %');
  setText('loads', parts.length ? 'Motor load readings, estimates: ' + parts.join(', ') + '.' + (Number.isFinite(s.speed_mm_s) ? ' Claw speed ' + Math.round(s.speed_mm_s) + ' mm/s.' : '') : '');
}
let usersKey = '';
function profile(s) {
  const u = s.user && typeof s.user === 'object' ? s.user : null;
  $('noprofile').hidden = !!u; $('profilebox').hidden = !u;
  setText('f-user', u ? String(u.name || '–') : '–');
  setText('f-cal', !u ? '–' : u.calibrated ? 'Done' : 'Not yet');
  if (!u) return;
  const names = Array.isArray(u.names) && u.names.length ? u.names.map(String) : [String(u.name)], key = names.join('\n') + '\n' + u.name;
  if (key !== usersKey && document.activeElement !== $('userpick')) {
    usersKey = key;
    $('userpick').replaceChildren(...names.map(n => new Option(n, n, false, n === u.name)));
  }
  const gains = Array.isArray(u.gains) ? u.gains : [], ranges = Array.isArray(u.range_deg) ? u.range_deg : [];
  $('calstate').innerHTML = '';
  $('calstate').append(u.calibrated ? 'Calibrated for ' + u.name : 'Not calibrated yet', Object.assign(document.createElement('span'), {className: 'method',
    textContent: u.calibrated ? 'Per-joint gains below come from the last calibration.' : 'Movements use the default gain 1.0 until this person is calibrated.'}));
  $('gains').hidden = !u.calibrated || !gains.length;
  if (u.calibrated) $('gainrows').replaceChildren(...JOINTS.map((j, i) => row([j, Number.isFinite(ranges[i]) ? Math.round(ranges[i]) + '°' : '–', Number.isFinite(gains[i]) ? gains[i].toFixed(2) + '×' : '–'])));
  const phase = s.calibration && s.calibration.phase, running = phase === 'rest' || phase === 'move';
  $('calibrate').disabled = running || !('calibration' in s);
  setText('calibrate', running ? 'Calibration running' : u.calibrated ? 'Calibrate again' : 'Start calibration');
}
function row(cells) { const tr = document.createElement('tr'); for (const c of cells) tr.insertCell().textContent = c; return tr; }
function procedure(s) {
  const c = s.calibration && typeof s.calibration === 'object' ? s.calibration : null, phase = c ? c.phase : 'idle';
  const running = phase === 'rest' || phase === 'move';
  if (running) { calSeenRunning = true; calClosed = false; }
  const show = running || (phase === 'done' && calSeenRunning && !calClosed);  // a "done" left over from before this page opened is not news
  $('procedure').hidden = !show;
  if (!show) return;
  const u = s.user || {}, order = ['rest', 'move', 'done'], at = order.indexOf(phase);
  setText('cal-who', u.name ? String(u.name) : 'this profile');
  for (const li of $('cal-steps').children) { const i = order.indexOf(li.dataset.step); li.dataset.now = String(i === at); li.dataset.past = String(i < at); }
  $('cal-close').hidden = running;  // cancelling is the status strip's action while it runs
  setText('cal-left', running ? String(Math.max(0, Math.ceil(num(c.seconds_left) || 0))) : 'Saved');
  setText('cal-unit', running ? 'seconds left' : 'calibration finished');
  setText('cal-note', running ? 'The arm is held while this runs.' : 'Profile updated.');
  $('cal-cover').hidden = phase !== 'move'; $('cal-result').hidden = phase !== 'done';
  if (phase === 'rest') setText('cal-instr', 'Hold the leader arm still in a comfortable pose, hand relaxed. This becomes the neutral pose.');
  if (phase === 'move') {
    setText('cal-instr', 'Move every joint as far as is comfortable. Squeeze the trigger as far as is comfortable, then open your hand wide.');
    const seen = Array.isArray(c.seen) ? c.seen : [], items = [...JOINTS.map((j, i) => [j, num(seen[i])]), ['Trigger', num(c.trigger_seen)]];
    $('cal-cover').replaceChildren(...items.map(([name, v]) => {
      const pct = Number.isFinite(v) ? Math.round(Math.min(1, Math.max(0, v)) * 100) : NaN, d = document.createElement('div');
      d.className = pct >= 100 ? 'full' : '';
      d.innerHTML = '<div class="row"><b></b><span></span></div><div class="track"><i></i></div>';
      d.querySelector('b').textContent = name; d.querySelector('span').textContent = Number.isFinite(pct) ? (pct >= 100 ? 'covered' : pct + ' %') : '–';
      d.querySelector('i').style.transform = 'scaleX(' + (Number.isFinite(pct) ? pct / 100 : 0) + ')';
      return d;
    }));
  }
  if (phase === 'done') {
    setText('cal-instr', 'Saved for ' + (u.name || 'this profile') + '. Each gain makes this person\'s comfortable range cover the arm\'s range (limited to 1.0 to 3.0).');
    const gains = Array.isArray(u.gains) ? u.gains : [], ranges = Array.isArray(u.range_deg) ? u.range_deg : [];
    $('cal-rows').replaceChildren(...JOINTS.map((j, i) => row([j, Number.isFinite(ranges[i]) ? Math.round(ranges[i]) + '°' : '–', Number.isFinite(gains[i]) ? gains[i].toFixed(2) + '×' : '–'])));
  }
  const tr = u.trigger;
  setText('cal-trigger', phase === 'done' && tr ? 'Trigger positions: rest ' + fixed(tr.rest, 0) + ', squeezed ' + fixed(tr.squeezed, 0) + ', open ' + fixed(tr.open, 0) + ' (the leader\'s own scale).' : '');
}
const UNIT = {score: '', deg: '°', degrees: '°', min: ' min', minutes: ' min', s: ' s', seconds: ' s'};
function fmtAct(v, unit) {
  if (!Number.isFinite(v)) return ['–', ''];
  const u = unit in UNIT ? UNIT[unit] : unit ? ' ' + unit : '';
  return [String(Math.round(v * 10) / 10), u];
}
let actKey = '';
function activities(s) {
  let list = Array.isArray(s.activities) ? s.activities.filter(a => a && a.title) : [];
  const t = s.test && typeof s.test === 'object' ? s.test : null;
  if (!list.length && t) list = [{id: 'hold_still', title: 'Hold still', unit: 'score', last: t.score, detail: '10 seconds; 100 means no shake. A display scale, not a clinical measure.'}];
  $('noact').hidden = list.length > 0; $('acts').hidden = !list.length;
  const key = JSON.stringify(list);
  if (key !== actKey) {
    actKey = key;
    $('actrows').replaceChildren(...list.map(a => {
      const tr = document.createElement('tr'), first = tr.insertCell();
      const b = document.createElement('b'); b.textContent = a.title; first.append(b);
      if (a.detail) first.append(Object.assign(document.createElement('span'), {className: 'method', textContent: a.detail}));
      for (const [v, label] of [[a.last, 'Last'], [a.best, 'Best']]) {
        const [n, u] = fmtAct(num(v), a.unit), td = tr.insertCell(); td.className = 'v'; td.dataset.label = label; td.textContent = n;
        if (u && n !== '–') td.append(Object.assign(document.createElement('small'), {textContent: u.trim()}));
      }
      const runs = tr.insertCell(); runs.dataset.label = 'Runs'; runs.textContent = Number.isFinite(a.runs) ? String(a.runs) : '–';
      const act = tr.insertCell();
      if (a.id === 'hold_still' && t) { const btn = document.createElement('button'); btn.className = 'btn secondary'; btn.dataset.cmd = 'test'; btn.dataset.test = '1'; act.append(btn); }
      return tr;
    }));
  }
  const running = !!(t && t.running);
  for (const btn of $('actrows').querySelectorAll('[data-test]')) { btn.disabled = running; btn.textContent = running ? 'Running' : 'Start test'; }
  $('testrun').hidden = !running;
  if (running) {
    setText('testleft', String(Math.max(0, Math.ceil(num(t.seconds_left) || 0))));
    meter('testbar', (10 - num(t.seconds_left)) * 10);
  }
  setText('testlast', t && !running && t.score != null ? 'Last hold-still test: ' + t.score + ' out of 100' + (Number.isFinite(t.tremor_mm) ? ', hand shake during it ' + fixed(t.tremor_mm, 1) + ' mm.' : '.') : '');
}
function summary(s) {
  const trend = Array.isArray(s.trend) ? s.trend.filter(p => Array.isArray(p)) : [], acts = Array.isArray(s.activities) ? s.activities : [];
  const act = id => acts.find(a => a && a.id === id) || {};
  const hand = mean(trend.map(p => p[1]).filter(Number.isFinite)), arm = mean(trend.map(p => p[2]).filter(Number.isFinite));
  const items = [['Length', duration(num(s.t))]];
  if (Number.isFinite(hand)) items.push(['Hand shake, mean', fixed(hand, 1) + ' mm'], ['Arm shake, mean', fixed(arm, 1) + ' mm']);
  if (Number.isFinite(act('steady_time').last)) items.push(['Filter on', fixed(act('steady_time').last, 1) + ' min']);
  if (Number.isFinite(act('hold_still').runs)) items.push(['Hold-still tests', String(act('hold_still').runs)]);
  if (Number.isFinite(act('grip_hold').last)) items.push(['Longest held grip', fixed(act('grip_hold').last, 0) + ' s']);
  const key = JSON.stringify(items);
  if ($('summary').dataset.key !== key) {
    $('summary').dataset.key = key;
    $('summary').replaceChildren(...items.map(([k, v]) => { const d = document.createElement('div'); d.append(Object.assign(document.createElement('dt'), {textContent: k}), Object.assign(document.createElement('dd'), {textContent: v})); return d; }));
  }
  setText('f-session', duration(num(s.t)));
}
let obsKey = '';
function observations(list) {  // rebuilt only when the server's list changes
  list = Array.isArray(list) ? list.filter(o => o && o.title) : [];
  const key = JSON.stringify(list); if (key === obsKey) return; obsKey = key;
  $('noobs').hidden = list.length > 0;
  $('obs').replaceChildren(...list.map(o => {
    const li = document.createElement('li'), r = document.createElement('div'), b = document.createElement('b'), v = document.createElement('span');
    r.className = 'row'; b.textContent = o.title; v.textContent = o.value || ''; v.className = 'num';
    r.append(b, v); li.append(r); if (o.text) li.append(Object.assign(document.createElement('p'), {textContent: o.text})); return li;
  }));
}
function voice(v, now) {
  const on = !!(v && (v.heard || v.said));
  $('novoice').hidden = on; $('voice').hidden = !on;
  if (!on) { setText('voiceago', ''); return; }
  setText('heard', v.heard ? '“' + v.heard + '”' : '–'); setText('said', v.said ? '“' + v.said + '”' : '–');
  const ago = Number.isFinite(v.at) && Number.isFinite(now) ? now - v.at : NaN;  // "at" is on the same clock as /state's t
  setText('voiceago', ago >= 0 && ago < 3600 ? (ago < 60 ? Math.round(ago) + ' s ago' : Math.round(ago / 60) + ' min ago') : '');
}
function sessionRow(s) {
  const best = Math.max(-1, ...(Array.isArray(s.tests) ? s.tests : []).map(t => num(t && t.score)).filter(Number.isFinite));
  const when = new Date(s.start), today = when.toDateString() === new Date().toDateString(), length = s.duration_s < 60 ? Math.round(s.duration_s) + ' s' : Math.round(s.duration_s / 60) + ' min';
  const tr = row([today ? when.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}) : when.toLocaleDateString([], {month: 'short', day: 'numeric'}), length, fixed(s.mean_tremor_mm, 1),
    fixed(s.mean_arm_mm, 1), fixed(s.removed_pct, 0) + '%', Number.isFinite(s.steady_share_pct) ? Math.round(s.steady_share_pct) + '%' : '–', best < 0 ? '–' : String(best)]);
  tr.title = when.toLocaleString();
  return tr;
}
function showSessions() {
  $('nosessions').hidden = sessions.length > 0; $('sessions').hidden = !sessions.length;
  if (!sessions.length) return;
  sessionChart(sessions);
  $('rows').replaceChildren(...sessions.slice(-5).reverse().map(sessionRow));
}
async function loadSessions() {  // a failed fetch keeps what is shown; an older server (which answers with the page) counts as no sessions
  try {
    const r = await fetch('/sessions', {cache: 'no-store', signal: timeout(3000)});
    if (!r.ok) return;
    const list = await r.json().catch(() => []);
    sessions = Array.isArray(list) ? list.filter(x => x && typeof x === 'object') : [];
    showSessions();
  } catch (e) {}
}

// ---------- one state ----------
function render(s) {
  lastState = s;
  measure(s); controls(s); grip(s); profile(s); procedure(s); activities(s); summary(s);
  const history = Array.isArray(s.history) ? s.history.filter(p => Array.isArray(p)) : [];
  traces(history); chart(history);
  if (view) { try { view.update(s); } catch (e) { fallback(); } }
  if (!$('arms').hidden) arms(s.raw_chain, s.out_chain);
  trendChart(s.trend); observations(s.insights); voice(s.voice, s.t);
}

// ---------- the link: "live" only after an HTTP-OK, parsed, fully drawn state ----------
const COMMANDS = () => [...document.querySelectorAll('[data-cmd], #gain, #cut, #userpick, #newname, #adduser button, #griphold')];
function setLink(next) {
  link = next;
  document.body.classList.toggle('stale', link !== 'live');
  const f = $('f-link');
  f.dataset.state = link;
  setText('f-link', link === 'live' ? 'Live ' + clock(lastOk) : link === 'broken' ? 'Not updating' : link === 'wait' ? 'Connecting…' : 'Not connected');
  const phase = lastState.calibration && lastState.calibration.phase, calibrating = phase === 'rest' || phase === 'move';
  const reason = link === 'down' ? 'Controls are off: not connected to the controller.'
    : link === 'broken' ? 'Controls are off: the page is not updating, so it could not show what a command did.'
    : link === 'live' && calibrating ? 'Controls wait while calibration runs. Cancel it from the bar above, or press Hold to keep the arm held afterwards.' : '';
  if (link !== 'live' || calibrating) for (const el of COMMANDS()) if (el.id !== 'status-act' && !(link === 'live' && el.id === 'hold-on')) el.disabled = true;  // Hold stays available in calibration, so the arm can stay held when it ends;  // the strip's own action is drawStatus()'s
  setText('locked', reason); $('locked').hidden = !reason;
  if (link === 'down' || link === 'broken') {  // never leave old numbers looking live
    const s = lastState;
    for (const id of ['hand', 'arm', 'removed', 'g-squeeze', 'g-held', 'g-claw']) setText(id, '–');
    for (const id of ['gm-squeeze', 'gm-held', 'gm-claw', 'm-hand', 'm-arm']) meter(id, NaN);
    setText('scalenote', lastGood && Number.isFinite(s.tremor_mm) ? 'Not live. Last values at ' + clock(lastGood) + ': hand ' + fixed(s.tremor_mm, 1) + ' mm, arm ' + fixed(s.out_mm, 1) + ' mm.' : 'Not live.');
  }
  $('viewstale').hidden = link === 'live' || !lastGood;
  drawStatus();
}
async function poll() {  // throws on anything but an HTTP-OK JSON object
  const r = await fetch('/state', {cache: 'no-store', signal: timeout(1000)});
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const s = await r.json();
  if (!s || typeof s !== 'object' || Array.isArray(s)) throw new Error('/state is not an object');
  return s;
}
async function tick() {
  let s = null;
  try { s = await poll(); } catch (e) { s = null; }
  if (s) {
    for (const el of COMMANDS()) el.disabled = false;  // render() then disables what this state does not support
    try { render(s); lastOk = lastGood = Date.now(); setLink('live'); }
    catch (e) { console.warn('dashboard: could not draw this state', e); setLink('broken'); }
  } else if (!lastOk || Date.now() - lastOk > 2000) setLink('down');  // a single missed poll is not yet "lost"
  setTimeout(tick, link === 'live' ? 100 : 1000);  // one request at a time; slower while the arm is gone
}
setLink('wait');
tick();
setInterval(loadSessions, 5000); loadSessions();
addEventListener('resize', showSessions);
