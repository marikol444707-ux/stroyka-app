export const createNewEstimateForm = () => ({
  projectId: '',
  projectName: '',
  name: '',
  version: '1.0',
  smetaType: 'Заказчик',
  workPackage: 'Основная',
  status: 'Активная',
  templateId: '',
});

export const createGenerateEstimateForm = () => ({
  description: '',
  projectId: '',
  projectName: '',
  pricelistId: '',
  area: '',
  name: '',
  version: '1.0',
  smetaType: 'Заказчик',
  workPackage: 'Основная',
  status: 'Активная',
});

export const createGeneratePricelistForm = () => ({
  description: '',
  name: '',
  forWho: '',
  coefficient: 1.0,
});

export const createFromEstimateForm = () => ({
  estimateId: '',
  name: '',
  forWho: '',
  coefficient: 1.0,
});

export const createDistributeBrigadeForm = () => ({
  brigadeName: '',
  contractorType: 'Своя бригада',
  contractorId: '',
  pricelistId: '',
});

export const createEstimateSectionForm = () => ({name: ''});

export const createEstimateItemForm = () => ({
  sectionId: '',
  itemType: 'work',
  name: '',
  unit: 'м2',
  quantity: '',
  priceWork: '',
  priceMaterial: '',
  measurementBasis: '',
});
