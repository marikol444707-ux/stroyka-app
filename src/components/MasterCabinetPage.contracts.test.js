import { resolveMasterContractDocument } from './MasterCabinetPage';

test('selects only the price rows of the master brigade contract', () => {
  const selected = resolveMasterContractDocument({
    user: {id: 17, name: 'Иванов Иван'},
    contracts: [],
    brigadeContracts: [
      {id: 91, contractorId: 17, brigadeName: 'Иванов Иван'},
      {id: 92, contractorId: 18, brigadeName: 'Петров Пётр'},
    ],
    brigadeContractItems: [
      {id: 1, contractId: '91', name: 'Штукатурка', priceBrigade: 500},
      {id: 2, contract_id: 92, name: 'Покраска', priceBrigade: 700},
    ],
  });

  expect(selected.contract).toEqual(expect.objectContaining({id: 91}));
  expect(selected.items).toEqual([
    expect.objectContaining({id: 1, priceBrigade: 500}),
  ]);
});

test('does not attach brigade price rows to a staff contract with the same id', () => {
  const staffContract = {id: 91, masterId: 17, masterName: 'Иванов Иван'};
  const selected = resolveMasterContractDocument({
    user: {id: 17, name: 'Иванов Иван'},
    contracts: [staffContract],
    brigadeContracts: [{id: 91, contractorId: 17, brigadeName: 'Иванов Иван'}],
    brigadeContractItems: [
      {id: 1, contractId: 91, name: 'Штукатурка', priceBrigade: 500},
    ],
  });

  expect(selected.contract).toBe(staffContract);
  expect(selected.items).toEqual([]);
});

test('does not use a matching name when the contract belongs to another positive user id', () => {
  const selected = resolveMasterContractDocument({
    user: {id: 17, name: 'Иванов Иван'},
    contracts: [],
    brigadeContracts: [
      {id: 91, contractorId: 18, brigadeName: 'Иванов Иван'},
    ],
    brigadeContractItems: [
      {id: 1, contractId: 91, name: 'Штукатурка', priceBrigade: 500},
    ],
  });

  expect(selected).toEqual({contract: null, items: []});
});

test('uses the legacy name fallback only when the brigade contract has no owner id', () => {
  const legacyContract = {id: 93, contractorId: 0, brigadeName: 'Иванов Иван'};
  const selected = resolveMasterContractDocument({
    user: {id: 17, name: 'Иванов Иван'},
    contracts: [],
    brigadeContracts: [legacyContract],
    brigadeContractItems: [
      {id: 3, contract_id: '93', name: 'Стяжка', priceBrigade: 800},
    ],
  });

  expect(selected.contract).toBe(legacyContract);
  expect(selected.items).toEqual([
    expect.objectContaining({id: 3, priceBrigade: 800}),
  ]);
});
