export const createPricelistForm = (overrides = {}) => ({
  name: '',
  description: '',
  forWho: '',
  coefficient: 1.0,
  ...overrides,
});

export const createPricelistItemForm = (overrides = {}) => ({
  name: '',
  unit: 'м2',
  price: '',
  category: '',
  ...overrides,
});
