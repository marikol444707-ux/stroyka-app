import fs from 'fs';
import path from 'path';

// Exercise the served viewer, not a duplicated implementation or exact JS text.
const viewerSource = fs.readFileSync(
  path.resolve(__dirname, '../dev_control/browser_worker/viewer.py'), 'utf8',
);
const html = viewerSource.match(/VIEWER_HTML = r"""([\s\S]*?)"""/)[1];
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const body = html.match(/<body>([\s\S]*?)<script>/)[1];
const q = (selector) => document.querySelector(selector);
const response = (value) => ({ ok: true, json: async () => value });
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};
const settle = async () => {
  for (let i = 0; i < 20; i += 1) await Promise.resolve();
};

describe('Jev viewer frame lifecycle', () => {
  let jobs;
  let routes;
  let originalFetch;
  let originalCreateObjectURL;
  let originalRevokeObjectURL;

  beforeEach(() => {
    jest.useFakeTimers();
    sessionStorage.clear();
    document.body.innerHTML = body;
    originalFetch = global.fetch;
    originalCreateObjectURL = URL.createObjectURL;
    originalRevokeObjectURL = URL.revokeObjectURL;
    URL.createObjectURL = jest.fn(() => `blob:frame-${URL.createObjectURL.mock.calls.length}`);
    URL.revokeObjectURL = jest.fn();
    jobs = [{
      job_id: 'a'.repeat(32), status: 'running', created_at_ms: 100,
      metadata: { display_name: 'First run' },
      evidence_files: ['/jobs/first/evidence/000001.jpg'],
      result: { checks: ['result retained'] },
    }, {
      job_id: 'b'.repeat(32), status: 'passed', created_at_ms: 200,
      metadata: { display_name: 'Second run' }, evidence_files: [],
      result: { checks: ['second result retained'] },
    }];
    routes = new Map();
    global.fetch = jest.fn(async (url) => {
      if (routes.has(url)) return routes.get(url)();
      if (url === '/jobs') return response({ jobs });
      if (url === '/viewer/demo-capabilities') return response({ enabled: false });
      const job = jobs.find((item) => url === `/jobs/${item.job_id}`);
      if (job) return response(job);
      if (url.endsWith('.jpg')) return { ok: true, blob: async () => new Blob(['image']) };
      throw new Error(`Unexpected viewer request: ${url}`);
    });
    // The IIFE owns its state, just as it does on the real viewer page.
    window.eval(script);
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
    global.fetch = originalFetch;
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
    sessionStorage.clear();
    document.body.innerHTML = '';
  });

  async function connect() {
    q('#token').value = 'test-only-viewer-token';
    await q('#connect').onclick();
    expect(q('#frame').getAttribute('src')).toBe('blob:frame-1');
    expect(q('#frame').classList.contains('hidden')).toBe(false);
  }

  async function refresh() {
    jest.advanceTimersByTime(1500);
    await settle();
  }

  test.each(['queued', 'running', 'passed', 'failed', 'cancelled'])(
    'missing evidence clears the old image and preserves the %s result', async (status) => {
      await connect();
      jobs[0] = { ...jobs[0], status, evidence_files: ['/jobs/first/progress.json'] };
      await refresh();
      expect(q('#frame').hasAttribute('src')).toBe(false);
      expect(q('#frame').classList.contains('hidden')).toBe(true);
      expect(q('#frameLabel').classList.contains('hidden')).toBe(true);
      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:frame-1');
      expect(q('#empty').classList.contains('hidden')).toBe(false);
      const terminal = ['passed', 'failed', 'cancelled'].includes(status);
      expect(q('#empty').textContent).toContain(terminal ? 'срок их хранения истёк' : 'Ожидаем первый кадр');
      expect(q('#status').textContent).toBe(status);
      expect(q('#timeline').textContent).toContain('result retained');
      expect(q('#stop').disabled).toBe(terminal);
    },
  );

  test('switching runs clears the previous image and details before the new request finishes', async () => {
    await connect();
    const detail = deferred();
    routes.set(`/jobs/${jobs[1].job_id}`, () => detail.promise);
    q('#jobs').children[1].onclick();
    expect(q('#frame').hasAttribute('src')).toBe(false);
    expect(q('#timeline').textContent).toBe('');
    expect(q('#stop').disabled).toBe(true);
    expect(q('#status').textContent).toBe('не выбран');
    detail.resolve(response(jobs[1]));
    await settle();
    expect(q('#runName').textContent).toBe('Second run');
    expect(q('#status').textContent).toBe('passed');
    expect(q('#timeline').textContent).toContain('second result retained');
    expect(q('#frame').hasAttribute('src')).toBe(false);
  });

  test('an old image response cannot repaint a newly selected run', async () => {
    await connect();
    const image = deferred();
    jobs[0].evidence_files = ['/jobs/first/evidence/000002.jpg'];
    routes.set(jobs[0].evidence_files[0], () => ({ ok: true, blob: () => image.promise }));
    await refresh();
    q('#jobs').children[1].onclick();
    image.resolve(new Blob(['late old image']));
    await settle();
    expect(q('#frame').hasAttribute('src')).toBe(false);
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    await refresh();
    expect(q('#runName').textContent).toBe('Second run');
    expect(q('#frame').hasAttribute('src')).toBe(false);
  });

  test('an old detail response cannot restore the previous run after switching', async () => {
    await connect();
    const detail = deferred();
    routes.set(`/jobs/${jobs[0].job_id}`, () => detail.promise);
    await refresh();
    q('#jobs').children[1].onclick();
    detail.resolve(response(jobs[0]));
    await settle();
    expect(q('#runName').textContent).toBe('Выберите запуск');
    expect(q('#frame').hasAttribute('src')).toBe(false);
    await refresh();
    expect(q('#runName').textContent).toBe('Second run');
    expect(q('#status').textContent).toBe('passed');
  });

  test('expired evidence clears the old frame without erasing a successful result', async () => {
    await connect();
    jobs[0] = { ...jobs[0], status: 'passed', evidence_files: ['/jobs/first/evidence/000002.jpg'] };
    routes.set(jobs[0].evidence_files[0], () => ({ ok: false, status: 404, json: async () => ({}) }));
    await refresh();
    expect(q('#frame').hasAttribute('src')).toBe(false);
    expect(q('#status').textContent).toBe('passed');
    expect(q('#timeline').textContent).toContain('result retained');
    expect(q('#timeline').textContent).toContain('Ошибка загрузки изображения');
    expect(q('#stop').disabled).toBe(true);
  });
});
