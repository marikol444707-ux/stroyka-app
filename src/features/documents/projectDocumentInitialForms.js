export const createProjectDocumentForm = () => ({
  side: 'customer',
  docType: 'Договор',
  number: '',
  docDate: '',
  counterparty: '',
  signStatus: 'Не подписан',
  scanUrl: '',
  amount: '',
  notes: '',
  revisesDocumentId: null,
  basisContractDocumentId: null,
});

export const createProjectLetterForm = () => ({
  side: 'customer',
  direction: 'outgoing',
  subject: '',
  body: '',
  counterparty: '',
  letterDate: '',
  fileUrl: '',
});

export const createSupervisorActForm = () => ({
  actType: 'Осмотр',
  description: '',
  findings: '',
  recommendations: '',
  date: '',
});
