#!/usr/bin/env node
// cdp.mjs - zero-dependency CDP client for the DevHome browser control plane.
// Talks to the Opera Developer instances that `devbrowser` launches (visible
// :9000, headless :9001, or any -Port you started). Loopback only by design.
// Requires Node 22+ (global WebSocket). No npm install needed.
//
// Usage: node cdp.mjs [--port N] [command ...]
//   (bare)                     status: browser version + tab list
//   tabs                       list page targets (index, id, title, url)
//   new <url>                  open a new tab, print its id
//   goto <tab> <url>           navigate a tab (tab = index or id prefix)
//   eval <tab> <js>            evaluate JS in the tab, print the result
//   text <tab>                 print the tab's document.body.innerText
//   screenshot <tab> <out.png> capture the tab to a PNG file
//   close <tab>                close a tab

import {writeFileSync} from 'node:fs';

const TIMEOUT_MS = 20000;

function fail(msg) {
  console.error(`cdp.mjs: ${msg}`);
  process.exit(1);
}

// --- argument parsing ------------------------------------------------------
const argv = process.argv.slice(2);
let port = 9000;
const rest = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--port') {
    port = Number(argv[++i]);
    if (!Number.isInteger(port) || port < 1024 || port > 65535) fail('--port must be 1024-65535');
  } else {
    rest.push(argv[i]);
  }
}
const base = `http://127.0.0.1:${port}`;
const cmd = rest.shift() ?? 'status';

// --- HTTP endpoint helpers -------------------------------------------------
async function http(path, method = 'GET') {
  let res;
  try {
    res = await fetch(base + path, {method, signal: AbortSignal.timeout(TIMEOUT_MS)});
  } catch (e) {
    fail(`cannot reach ${base}${path} (${e.cause?.code ?? e.message}). Is devbrowser running on port ${port}? Check: devbrowser`);
  }
  if (!res.ok) fail(`${base}${path} -> HTTP ${res.status}`);
  const body = await res.text();
  try { return JSON.parse(body); } catch { return body; }
}

async function pageTargets() {
  const all = await http('/json/list');
  return all.filter(t => t.type === 'page');
}

async function resolveTab(spec) {
  if (spec === undefined) fail('missing <tab> argument (use an index from `tabs` or an id prefix)');
  const pages = await pageTargets();
  if (pages.length === 0) fail('no page targets open');
  if (/^\d{1,3}$/.test(spec)) {
    const idx = Number(spec);
    if (idx >= pages.length) fail(`tab index ${idx} out of range (0-${pages.length - 1})`);
    return pages[idx];
  }
  const hits = pages.filter(t => t.id.startsWith(spec));
  if (hits.length === 1) return hits[0];
  fail(hits.length === 0 ? `no tab id starts with '${spec}'` : `ambiguous tab id prefix '${spec}' (${hits.length} matches)`);
}

// --- CDP over WebSocket ----------------------------------------------------
function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const timer = setTimeout(() => reject(new Error('WebSocket connect timeout')), TIMEOUT_MS);
    ws.onopen = () => { clearTimeout(timer); resolve(ws); };
    ws.onerror = () => { clearTimeout(timer); reject(new Error(`WebSocket connect failed: ${wsUrl}`)); };
  });
}

function makeSession(ws) {
  let nextId = 1;
  const pending = new Map();
  ws.onmessage = ev => {
    const msg = JSON.parse(ev.data);
    if (msg.id !== undefined && pending.has(msg.id)) {
      const {resolve, reject, timer} = pending.get(msg.id);
      pending.delete(msg.id);
      clearTimeout(timer);
      if (msg.error) reject(new Error(`${msg.error.message} (CDP ${msg.error.code})`));
      else resolve(msg.result);
    }
  };
  return (method, params = {}) => new Promise((resolve, reject) => {
    const id = nextId++;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${method} timed out`)); }, TIMEOUT_MS);
    pending.set(id, {resolve, reject, timer});
    ws.send(JSON.stringify({id, method, params}));
  });
}

async function withTab(spec, fn) {
  const tab = await resolveTab(spec);
  if (!tab.webSocketDebuggerUrl) fail(`tab ${tab.id} has no webSocketDebuggerUrl (DevTools already attached?)`);
  const ws = await connect(tab.webSocketDebuggerUrl);
  try {
    return await fn(makeSession(ws), tab);
  } finally {
    ws.close();
  }
}

async function evalIn(send, expression) {
  const r = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  if (r.exceptionDetails) fail(`page threw: ${r.exceptionDetails.exception?.description ?? r.exceptionDetails.text}`);
  return r.result.value;
}

// --- commands --------------------------------------------------------------
const printTabs = pages => {
  pages.forEach((t, i) => console.log(`[${i}] ${t.id}  ${t.title || '(untitled)'}  ${t.url}`));
  if (pages.length === 0) console.log('(no page targets)');
};

const commands = {
  async status() {
    const v = await http('/json/version');
    console.log(`endpoint: ${base}`);
    console.log(`browser:  ${v.Browser}${/HeadlessChrome/.test(v['User-Agent'] ?? '') ? ' (headless)' : ''}`);
    printTabs(await pageTargets());
  },
  async tabs() {
    printTabs(await pageTargets());
  },
  async new() {
    const url = rest.shift() ?? fail('usage: new <url>');
    const t = await http(`/json/new?${encodeURIComponent(url)}`, 'PUT');
    console.log(`[new] ${t.id}  ${t.url}`);
  },
  async goto() {
    const [tab, url] = [rest.shift(), rest.shift()];
    if (!url) fail('usage: goto <tab> <url>');
    await withTab(tab, async send => {
      await send('Page.navigate', {url});
      console.log(`navigated -> ${url}`);
    });
  },
  async eval() {
    const [tab, js] = [rest.shift(), rest.shift()];
    if (js === undefined) fail('usage: eval <tab> <js>');
    const value = await withTab(tab, send => evalIn(send, js));
    console.log(typeof value === 'string' ? value : JSON.stringify(value, null, 2));
  },
  async text() {
    const value = await withTab(rest.shift(), send => evalIn(send, 'document.body ? document.body.innerText : ""'));
    console.log(value);
  },
  async screenshot() {
    const [tab, out] = [rest.shift(), rest.shift()];
    if (!out) fail('usage: screenshot <tab> <out.png>');
    await withTab(tab, async send => {
      await send('Page.enable');
      const shot = await send('Page.captureScreenshot', {format: 'png'});
      writeFileSync(out, Buffer.from(shot.data, 'base64'));
      console.log(`wrote ${out} (${shot.data.length * 3 / 4 | 0} bytes)`);
    });
  },
  async close() {
    const tab = await resolveTab(rest.shift());
    await http(`/json/close/${tab.id}`);
    console.log(`closed ${tab.id}`);
  },
};

const run = commands[cmd] ?? fail(`unknown command '${cmd}' (status|tabs|new|goto|eval|text|screenshot|close)`);
run().catch(e => fail(e.message));
