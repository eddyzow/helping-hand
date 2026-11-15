// Evaluate the real poll/link functions with fake fetch/render/DOM; no browser or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const js = fs.readFileSync(path.join(__dirname, '..', 'dashboard', 'app.js'), 'utf8').replace(/\r\n/g, '\n');
const source = js.match(/const COMMANDS = [\s\S]*?\n(?=setLink\('wait'\);)/);
assert(source, 'Inspect the changed poll fixture before running it.');
const controls = js.match(/function controls\(s\) \{[\s\S]*?\n\}\n(?=function grip)/);
assert(controls, 'Inspect the changed controls fixture before running it.');

const rollNote = {};
const controlScope = vm.createContext({ $: () => rollNote, pressed: () => {}, setText: () => {} });
vm.runInContext(controls[0], controlScope);
for (const value of [false, true, undefined]) {
  controlScope.controls({ roll_follows: value });
  assert.equal(rollNote.hidden, value !== false);
}
console.log('roll warning follows controller state');

async function poll(ok, payload, renderFails = false, lastOk = 0) {
  const state = { stale: true, text: {}, elements: {} };
  const element = id => state.elements[id] ??= { id, dataset: {}, disabled: false };
  const commands = ['hold-on', 'hold-off', 'gain', 'letgo', 'status-act'].map(element);
  const scope = vm.createContext({
    fetch: async () => ({ ok, status: ok ? 200 : 503, json: async () => payload }),
    timeout: () => undefined, lastOk, lastGood: lastOk, lastState: {}, link: 'wait',
    Date: { now: () => 10000 }, $: element, clock: String, fixed: String,
    meter: () => {}, drawStatus: () => {},
    setText: (key, value) => { state.text[key] = value; },
    render: () => { if (renderFails) throw Error('fake rendering failure'); scope.lastState = payload; },
    console: { warn: () => {} }, setTimeout: () => {},
    document: { querySelectorAll: () => commands,
      body: { classList: { toggle: (_, value) => { state.stale = value; } } } },
  });
  await vm.runInContext(source[0] + '\ntick()', scope);
  state.link = scope.link;
  state.lastOk = scope.lastOk;
  return state;
}

(async () => {
  const good = await poll(true, { steady: true, hold: true });
  assert(!good.stale && good.link === 'live' && !good.elements['hold-on'].disabled);
  const failures = [];
  for (const [name, state] of [
    ['HTTP error JSON', await poll(false, { error: 'unavailable' })],
    ['render failure', await poll(true, { steady: true, hold: true }, true)],
    ['invalid JSON shape', await poll(true, [])],
    ['HTTP failure beyond grace', await poll(false, {}, false, 7000)],
  ]) {
    if (!state.stale || state.link === 'live' || !state.elements['hold-on'].disabled || state.lastOk === 10000) failures.push([name, state]);
  }
  assert.deepEqual(failures, [], 'Invalid state must not enable controls and claim live readings.');
  console.log('dashboard poll checks pass');
  const calibrating = await poll(true, { steady: true, hold: false, calibration: { phase: 'rest' } });
  assert(!calibrating.elements['hold-on'].disabled, 'A live calibrating page must retain Hold so the user can prevent automatic resumption.');
  assert(['hold-off', 'gain', 'letgo'].every(id => calibrating.elements[id].disabled));
  console.log('calibration Hold control remains available');
})().catch(error => { console.error(error); process.exitCode = 1; });
