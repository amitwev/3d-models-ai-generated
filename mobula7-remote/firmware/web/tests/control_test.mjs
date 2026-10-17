// Headless test of the phone control page with a fake WebSocket.
// Run: node mobula7-remote/firmware/web/tests/control_test.mjs
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const here = path.dirname(fileURLToPath(import.meta.url));
const pageUrl = pathToFileURL(path.join(here, '..', 'control.html')).href + '?ws=ws://fake/';

const fakeWs = () => {
  window.__sent = [];
  class FakeWS {
    constructor(url) {
      this.url = url;
      this.readyState = 0;
      window.__fakeWs = this;
      setTimeout(() => { this.readyState = 1; this.onopen && this.onopen({}); }, 0);
    }
    send(t) { window.__sent.push(t); }
    close() { this.readyState = 3; this.onclose && this.onclose({}); }
    receive(t) { this.onmessage && this.onmessage({ data: t }); }
  }
  FakeWS.OPEN = 1;
  window.WebSocket = FakeWS;
};

const parse = (m) => {
  const [tag, r, p, t, y, b, c] = m.split(',');
  return { tag, r: +r, p: +p, t: +t, y: +y, b: +b, c: +c };
};

async function pointer(page, sel, type, x, y, id) {
  await page.$eval(sel, (el, a) => {
    el.dispatchEvent(new PointerEvent(a.type, {
      bubbles: true, cancelable: true, pointerId: a.id, pointerType: 'touch',
      clientX: a.x, clientY: a.y, isPrimary: a.id === 1,
    }));
  }, { type, x, y, id });
}

async function lastMsg(page) {
  const sent = await page.evaluate(() => window.__sent);
  assert.ok(sent.length > 0, 'no messages sent');
  return parse(sent[sent.length - 1]);
}

const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const page = await browser.newPage({ viewport: { width: 844, height: 390 }, hasTouch: true });
const requests = [];
page.on('request', (r) => requests.push(r.url()));
await page.addInitScript(fakeWs);
await page.goto(pageUrl);
await page.waitForTimeout(120);

// 1. Initial message: centred sticks, throttle low, nothing pressed.
{
  const sent = await page.evaluate(() => window.__sent);
  assert.ok(sent.length >= 1, 'should send within 120 ms');
  assert.equal(sent[0], 'S,1500,1500,1000,1500,0,0');
}

const L = await page.$eval('#left', (e) => e.getBoundingClientRect().toJSON());
const R = await page.$eval('#right', (e) => e.getBoundingClientRect().toJSON());
const lc = { x: L.x + L.width / 2, y: L.y + L.height / 2 };
const rc = { x: R.x + R.width / 2, y: R.y + R.height / 2 };

// 2. Touching does not jump the throttle; dragging up raises it and it stays.
await pointer(page, '#left', 'pointerdown', lc.x, lc.y, 1);
await page.waitForTimeout(40);
assert.equal((await lastMsg(page)).t, 1000, 'touch alone must not change throttle');
await pointer(page, '#left', 'pointermove', lc.x, lc.y - L.height, 1);  // drag a full pad height up
await page.waitForTimeout(40);
assert.ok((await lastMsg(page)).t >= 1950, 'throttle up');

// 3. Second finger on the right pad while the first is still down.
await pointer(page, '#right', 'pointerdown', rc.x, rc.y, 2);
await pointer(page, '#right', 'pointermove', rc.x + R.width, rc.y, 2);
await page.waitForTimeout(40);
{
  const m = await lastMsg(page);
  assert.ok(m.r >= 1950, `roll right, got ${m.r}`);
  assert.ok(m.t >= 1950, 'throttle unchanged by right stick');
}
await pointer(page, '#right', 'pointerup', rc.x + R.width, rc.y, 2);
await pointer(page, '#left', 'pointerup', lc.x, lc.y - L.height, 1);
await page.waitForTimeout(40);
{
  const m = await lastMsg(page);
  assert.equal(m.r, 1500, 'roll recentres');
  assert.equal(m.y, 1500, 'yaw recentres');
  assert.ok(m.t >= 1950, 'throttle holds after release');
}

// 4. Calibrate button sends calib=1 exactly once.
await page.evaluate(() => { window.__sent.length = 0; });
await page.click('#calib');
await page.waitForTimeout(100);
{
  const msgs = (await page.evaluate(() => window.__sent)).map(parse);
  assert.equal(msgs.filter((m) => m.c === 1).length, 1, 'one calib message');
  assert.equal(msgs[msgs.length - 1].c, 0);
}

// 5. Status from the remote: armed -> red text, calibrate disabled.
await page.evaluate(() => window.__fakeWs.receive('T,1,0,0'));
await page.waitForTimeout(20);
assert.match(await page.textContent('#status'), /חמוש/);
assert.equal(await page.$eval('#calib', (b) => b.disabled), true);

// 6. BEEP held -> b=1, released -> b=0.
await page.dispatchEvent('#beep', 'pointerdown', { pointerId: 3 });
await page.waitForTimeout(40);
assert.equal((await lastMsg(page)).b, 1);
await page.dispatchEvent('#beep', 'pointerup', { pointerId: 3 });
await page.waitForTimeout(40);
assert.equal((await lastMsg(page)).b, 0);

// 7. Silence from the remote for > 1 s -> "no link".
await page.waitForTimeout(1100);
assert.match(await page.textContent('#status'), /אין קשר/);

// 8. No network requests besides the page itself.
assert.deepEqual(requests.filter((u) => !u.startsWith('file:')), []);

await browser.close();
console.log('control page tests passed');
