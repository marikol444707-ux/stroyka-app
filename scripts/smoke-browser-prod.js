#!/usr/bin/env node

const fs = require('fs');
const net = require('net');
const os = require('os');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

const BASE_URL = (process.env.BASE_URL || 'https://stroyka26.pro').replace(/\/$/, '');
const WAIT_MS = Number(process.env.BROWSER_SMOKE_WAIT_MS || 9000);
const START_TIMEOUT_MS = Number(process.env.BROWSER_SMOKE_START_TIMEOUT_MS || 20000);
const AUTH_EMAIL = (process.env.BROWSER_SMOKE_EMAIL || process.env.SMOKE_EMAIL || '').trim().toLowerCase();
const AUTH_PASSWORD = process.env.BROWSER_SMOKE_PASSWORD || process.env.SMOKE_PASSWORD || '';
const AUTH_2FA_CODE = (process.env.BROWSER_SMOKE_2FA_CODE || process.env.SMOKE_2FA_CODE || '').trim();
const AUTH_DATA_JSON = process.env.BROWSER_SMOKE_AUTH_DATA_JSON || '';
const DEFAULT_URLS = ['/', '/app'];
const FORBIDDEN_RENDER_MARKERS = [
  'Приложение нужно обновить',
  'Cannot read properties',
  'is not a function',
  'Ошибка подключения к серверу',
  'Minified React error',
];
const HANGING_RENDER_MARKERS = [
  'Загружаю данные объекта',
  'Сейчас подтягиваются сметы',
];

const urls = (process.env.BROWSER_SMOKE_URLS || DEFAULT_URLS.join(','))
  .split(',')
  .map((value) => value.trim())
  .filter(Boolean)
  .map((value) => value.startsWith('http') ? value : `${BASE_URL}${value.startsWith('/') ? value : `/${value}`}`);

const chromeCandidates = [
  process.env.CHROME_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
].filter(Boolean);

function commandPath(name) {
  const result = spawnSync('which', [name], { encoding: 'utf8' });
  return result.status === 0 ? result.stdout.trim() : '';
}

function findChrome() {
  for (const candidate of chromeCandidates) {
    if (candidate && fs.existsSync(candidate)) return candidate;
  }
  for (const command of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome']) {
    const resolved = commandPath(command);
    if (resolved) return resolved;
  }
  return '';
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function postJson(pathname, payload, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BASE_URL}${pathname}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const text = await response.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch (_error) {
      data = { detail: text.slice(0, 240) };
    }
    return { response, data };
  } finally {
    clearTimeout(timer);
  }
}

async function loginForSmoke() {
  if (AUTH_DATA_JSON) {
    let data = null;
    try {
      data = JSON.parse(AUTH_DATA_JSON);
    } catch (error) {
      throw new Error(`BROWSER_SMOKE_AUTH_DATA_JSON is not valid JSON: ${error.message}`);
    }
    if (!data?.authToken) throw new Error('BROWSER_SMOKE_AUTH_DATA_JSON must include authToken');
    return data;
  }
  if (!AUTH_EMAIL || !AUTH_PASSWORD) return null;
  const { response, data } = await postJson('/login', {
    email: AUTH_EMAIL,
    password: AUTH_PASSWORD,
  });
  if (!response.ok) {
    throw new Error(`authenticated browser smoke login failed: HTTP ${response.status} ${data.detail || ''}`.trim());
  }
  if (data.twoFactorSetupRequired) {
    console.log('SKIP authenticated browser smoke: login requires initial 2FA setup');
    return null;
  }
  if (data.twoFactorRequired) {
    if (!AUTH_2FA_CODE) {
      console.log('SKIP authenticated browser smoke: login requires 2FA; set BROWSER_SMOKE_2FA_CODE or SMOKE_2FA_CODE');
      return null;
    }
    const verified = await postJson('/login/2fa/verify', {
      challengeToken: data.challengeToken,
      code: AUTH_2FA_CODE,
    });
    if (!verified.response.ok) {
      throw new Error(`authenticated browser smoke 2FA failed: HTTP ${verified.response.status} ${verified.data.detail || ''}`.trim());
    }
    if (!verified.data.authToken) {
      throw new Error('authenticated browser smoke 2FA did not return authToken');
    }
    return verified.data;
  }
  if (!data.authToken) {
    throw new Error('authenticated browser smoke login did not return authToken');
  }
  return data;
}

async function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

async function waitForChrome(port, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError = '';
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) return await response.json();
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error.message;
    }
    await sleep(250);
  }
  throw new Error(`Chrome DevTools did not start: ${lastError}`);
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
    this.events = [];
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('CDP websocket timeout')), 10000);
      this.ws.addEventListener('open', () => {
        clearTimeout(timer);
        resolve();
      }, { once: true });
      this.ws.addEventListener('error', () => {
        clearTimeout(timer);
        reject(new Error('CDP websocket error'));
      }, { once: true });
    });
    this.ws.addEventListener('message', (event) => {
      const data = JSON.parse(event.data);
      if (data.id && this.pending.has(data.id)) {
        const { resolve, reject } = this.pending.get(data.id);
        this.pending.delete(data.id);
        if (data.error) reject(new Error(data.error.message || JSON.stringify(data.error)));
        else resolve(data.result || {});
        return;
      }
      if (data.method) this.events.push(data);
    });
  }

  send(method, params = {}, timeoutMs = 15000) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`CDP command timeout: ${method}`));
        }
      }, timeoutMs);
    });
  }

  close() {
    try {
      this.ws?.close();
    } catch (_error) {}
  }
}

function textOfRemoteObject(result) {
  return String(result?.result?.value ?? '');
}

function relevantConsoleErrors(events) {
  return events
    .filter((event) => {
      if (event.method === 'Runtime.exceptionThrown') return true;
      if (event.method === 'Log.entryAdded') {
        const level = event.params?.entry?.level;
        return level === 'error';
      }
      if (event.method === 'Runtime.consoleAPICalled') {
        return event.params?.type === 'error' || event.params?.type === 'assert';
      }
      return false;
    })
    .map((event) => {
      if (event.method === 'Runtime.exceptionThrown') {
        const details = event.params?.exceptionDetails || {};
        return details.exception?.description || details.exception?.value || details.text || 'Runtime.exceptionThrown';
      }
      if (event.method === 'Log.entryAdded') {
        const entry = event.params?.entry || {};
        return entry.text || entry.url || 'Log.entryAdded';
      }
      const args = event.params?.args || [];
      return args.map((arg) => arg.value || arg.description || '').filter(Boolean).join(' ') || 'console.error';
    })
    .filter((message) => {
      const text = String(message || '');
      if (/Failed to load resource: the server responded with a status of 404/i.test(text)) return false;
      if (/Failed to load resource: the server responded with a status of 405/i.test(text)) return false;
      if (/Failed to load resource: the server responded with a status of 401/i.test(text)) return false;
      return true;
    })
    .filter(Boolean);
}

function validatePage(url, info) {
  const text = (info.bodyText || '').replace(/\s+/g, ' ').trim();
  const consoleErrors = relevantConsoleErrors(info.events);
  if (consoleErrors.length) {
    throw new Error(`console/runtime errors on ${url}: ${consoleErrors.slice(0, 3).join(' | ')}`);
  }
  if (text.length < 30) {
    throw new Error(`rendered almost empty body on ${url}: title="${info.title || ''}" href="${info.href || ''}" readyState="${info.readyState || ''}" text="${text.slice(0, 200)}"`);
  }
  const marker = FORBIDDEN_RENDER_MARKERS.find((needle) => text.includes(needle));
  if (marker) {
    throw new Error(`rendered error marker "${marker}": ${text.slice(0, 500)}`);
  }
  const hangingMarker = HANGING_RENDER_MARKERS.find((needle) => text.includes(needle));
  if (hangingMarker) {
    throw new Error(`rendered stuck loading marker "${hangingMarker}": ${text.slice(0, 500)}`);
  }
  console.log(`OK   browser ${url}`);
}

async function readPageInfo(client) {
  const bodyText = textOfRemoteObject(await client.send('Runtime.evaluate', {
    expression: 'document.body ? document.body.innerText : ""',
    returnByValue: true,
  }));
  const title = textOfRemoteObject(await client.send('Runtime.evaluate', {
    expression: 'document.title || ""',
    returnByValue: true,
  }));
  const href = textOfRemoteObject(await client.send('Runtime.evaluate', {
    expression: 'location.href',
    returnByValue: true,
  }));
  const readyState = textOfRemoteObject(await client.send('Runtime.evaluate', {
    expression: 'document.readyState || ""',
    returnByValue: true,
  }));
  return { bodyText, title, href, readyState, events: client.events.slice() };
}

async function waitForRenderedPage(client) {
  const deadline = Date.now() + WAIT_MS;
  let info = { bodyText: '', title: '', href: '', readyState: '', events: [] };
  while (Date.now() < deadline) {
    info = await readPageInfo(client);
    const text = (info.bodyText || '').replace(/\s+/g, ' ').trim();
    const hasEnoughText = text.length >= 30;
    const hasForbiddenMarker = FORBIDDEN_RENDER_MARKERS.some((needle) => text.includes(needle));
    const hasHangingMarker = HANGING_RENDER_MARKERS.some((needle) => text.includes(needle));
    if (hasEnoughText && !hasHangingMarker) return info;
    if (hasForbiddenMarker) return info;
    if (relevantConsoleErrors(info.events).length) return info;
    await sleep(info.readyState === 'complete' ? 500 : 250);
  }
  return info;
}

async function stopProcess(child) {
  if (!child || child.exitCode !== null || child.signalCode) return;
  await new Promise((resolve) => {
    let settled = false;
    const done = () => {
      if (settled) return;
      settled = true;
      clearTimeout(killTimer);
      clearTimeout(doneTimer);
      resolve();
    };
    const killTimer = setTimeout(() => {
      try {
        child.kill('SIGKILL');
      } catch (_error) {}
    }, 1500);
    const doneTimer = setTimeout(done, 3500);
    child.once('exit', done);
    try {
      child.kill('SIGTERM');
    } catch (_error) {
      done();
    }
  });
}

async function inspectPage(port, url) {
  const targetResponse = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' });
  if (!targetResponse.ok) throw new Error(`cannot create Chrome target: HTTP ${targetResponse.status}`);
  const target = await targetResponse.json();
  const client = new CdpClient(target.webSocketDebuggerUrl);
  await client.connect();
  try {
    await client.send('Runtime.enable');
    await client.send('Page.enable');
    await client.send('Log.enable');
    await client.send('Page.navigate', { url }, 45000);
    return await waitForRenderedPage(client);
  } finally {
    client.close();
    await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`).catch(() => {});
  }
}

async function inspectAuthenticatedPage(port, url, authData) {
  const targetResponse = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' });
  if (!targetResponse.ok) throw new Error(`cannot create Chrome target: HTTP ${targetResponse.status}`);
  const target = await targetResponse.json();
  const client = new CdpClient(target.webSocketDebuggerUrl);
  await client.connect();
  try {
    await client.send('Runtime.enable');
    await client.send('Page.enable');
    await client.send('Log.enable');
    await client.send('Page.addScriptToEvaluateOnNewDocument', {
      source: `
        try {
          localStorage.setItem('authToken', ${JSON.stringify(authData.authToken || '')});
          localStorage.setItem('user', ${JSON.stringify(JSON.stringify(authData))});
          sessionStorage.removeItem('authExpiredNotice');
        } catch (error) {}
      `,
    });
    await client.send('Page.navigate', { url }, 45000);
    return await waitForRenderedPage(client);
  } finally {
    client.close();
    await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`).catch(() => {});
  }
}

async function main() {
  if (typeof WebSocket !== 'function') {
    throw new Error('Node.js WebSocket is not available. Use Node 22+ or set up a browser smoke runner with WebSocket support.');
  }
  const chrome = findChrome();
  if (!chrome) {
    throw new Error('Chrome/Chromium not found. Set CHROME_PATH to run browser smoke.');
  }

  const port = await freePort();
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'stroyka-browser-smoke-'));
  const chromeProcess = spawn(chrome, [
    '--headless=new',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--no-first-run',
    '--no-default-browser-check',
    '--hide-scrollbars',
    '--ignore-certificate-errors',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    '--window-size=390,1200',
    'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });

  const stderr = [];
  chromeProcess.stderr.on('data', (chunk) => {
    stderr.push(String(chunk));
  });

  try {
    console.log(`Browser smoke: ${BASE_URL}`);
    console.log(`INFO chrome=${chrome}`);
    await waitForChrome(port, START_TIMEOUT_MS);
    for (const url of urls) {
      const info = await inspectPage(port, url);
      validatePage(url, info);
    }
    const authData = await loginForSmoke();
    if (authData) {
      const authUrl = `${BASE_URL}/app`;
      const info = await inspectAuthenticatedPage(port, authUrl, authData);
      validatePage(`${authUrl} [auth:${authData.role || authData.email || authData.name || 'user'}]`, info);
    }
    console.log('Browser smoke OK');
  } finally {
    await stopProcess(chromeProcess);
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(`FAIL ${error.message}`);
  process.exit(1);
});
