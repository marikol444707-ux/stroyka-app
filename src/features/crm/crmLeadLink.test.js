import { rememberCrmLeadFromLocation, takeRememberedCrmLead } from './crmLeadLink';

const memoryStorage = () => {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) || null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
};

test('remembers a CRM lead from the owner notification link and reads it once', () => {
  const storage = memoryStorage();
  expect(rememberCrmLeadFromLocation('?page=crm&lead=15', storage)).toBe('15');
  expect(takeRememberedCrmLead(storage)).toBe('15');
  expect(takeRememberedCrmLead(storage)).toBe('');
});

test('ignores a lead id that is not opened on the CRM page', () => {
  const storage = memoryStorage();
  expect(rememberCrmLeadFromLocation('?lead=15', storage)).toBe('');
  expect(rememberCrmLeadFromLocation('?page=crm&lead=abc', storage)).toBe('');
});
