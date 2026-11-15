// Evaluate only the real poll function with fake fetch/render/DOM; no browser or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'steady_dashboard.html'), 'utf8').replace(/\r\n/g, '\n');
const source = html.match(/async function tick\(\) \{[\s\S]*?\n\}\s*\ntick\(\);/);
assert(source, 'Inspect the changed poll fixture before running it.');

async function poll(ok, payload, renderFails = false) {
  const state = { stale: true, text: {} };
  const scope = vm.createContext({
    fetch: async () => ({ ok, json: async () => payload }),
    timeout: () => undefined, lastOk: 0, Date: { now: () => 10000 },
    stale: value => { state.stale = value; },
    setText: (key, value) => { state.text[key] = value; },
    render: () => { if (renderFails) throw Error('fake rendering failure'); },
    console: { warn: () => {} }, setTimeout: () => {},
    document: { body: { classList: { contains: () => state.stale } } },
  });
  await vm.runInContext(source[0].replace(/tick\(\);$/, 'tick()'), scope);
  return state;
}

(async () => {
  const good = await poll(true, { steady: true, hold: true });
  assert(!good.stale && good.text.link === 'Live from the arm');
  const failures = [];
  for (const [name, state] of [
    ['HTTP error JSON', await poll(false, { error: 'unavailable' })],
    ['render failure', await poll(true, { steady: true, hold: true }, true)],
  ]) {
    if (!state.stale || state.text.link === 'Live from the arm') failures.push([name, state]);
  }
  assert.deepEqual(failures, [], 'Invalid state must not enable controls and claim live readings.');
  console.log('dashboard poll checks pass');
})().catch(error => { console.error(error); process.exitCode = 1; });
