import { browserStorage, captureFirstTouchUtm, FIRST_TOUCH_UTM_TTL_MS } from './firstTouchUtm';

const memoryStorage = (initial = null) => {
  const values = new Map(initial ? [['stroykaFirstTouchUtm', initial]] : []);
  return {
    getItem: (key) => values.get(key) || null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
    values,
  };
};

test('keeps the first ad source for 30 days after the visitor leaves the landing URL', () => {
  const storage = memoryStorage();
  const now = Date.parse('2026-11-21T00:00:00Z');
  const first = captureFirstTouchUtm({
    search: '?utm_source=netip&utm_medium=telegram&utm_campaign=ads',
    storage,
    now,
  });
  const later = captureFirstTouchUtm({
    search: '?utm_source=bloknot&utm_medium=telegram&utm_campaign=ads',
    storage,
    now: now + FIRST_TOUCH_UTM_TTL_MS - 1000,
  });
  expect(first).toEqual({ utm_source: 'netip', utm_medium: 'telegram', utm_campaign: 'ads' });
  expect(later).toEqual(first);
});

test('uses the current link when the browser blocks localStorage', () => {
  const original = Object.getOwnPropertyDescriptor(window, 'localStorage');
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    get() {
      throw new DOMException('blocked');
    },
  });
  try {
    expect(browserStorage('localStorage').getItem('stroykaFirstTouchUtm')).toBeNull();
    expect(captureFirstTouchUtm({
      search: '?utm_source=netip&utm_medium=telegram&utm_campaign=ads',
      storage: browserStorage('localStorage'),
    })).toEqual({
      utm_source: 'netip',
      utm_medium: 'telegram',
      utm_campaign: 'ads',
    });
  } finally {
    Object.defineProperty(window, 'localStorage', original);
  }
});

test('forgets an ad source after 30 days and can remember the next visit', () => {
  const now = Date.parse('2026-11-21T00:00:00Z');
  const storage = memoryStorage(JSON.stringify({
    savedAt: now - FIRST_TOUCH_UTM_TTL_MS - 1,
    utm: { utm_source: 'netip' },
  }));
  expect(captureFirstTouchUtm({
    search: '?utm_source=bloknot&utm_medium=telegram',
    storage,
    now,
  })).toEqual({ utm_source: 'bloknot', utm_medium: 'telegram' });
});
