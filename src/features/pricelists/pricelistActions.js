import { createPricelistForm, createPricelistItemForm } from './pricelistInitialForms';

export const createPricelistActions = ({
  API,
  editingItem,
  editingPlItem,
  inlineEditPlData,
  inlineEditPrice,
  loadPricelistItems,
  newPlItem,
  newPricelist,
  refreshData,
  selectedPricelist,
  setEditingItem,
  setEditingPlItem,
  setInlineEditPl,
  setInlineEditPlData,
  setInlineEditPrice,
  setNewPlItem,
  setNewPricelist,
  setPricelistItems,
  setSelectedPricelist,
  setShowForm,
}) => {
  const savePricelist = async () => {
    if (!newPricelist.name) return;
    if (editingItem) await fetch(API + '/pricelists/' + editingItem.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(newPricelist)});
    else await fetch(API + '/pricelists', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(newPricelist)});
    await refreshData();
    setNewPricelist(createPricelistForm());
    setEditingItem(null);
    setShowForm(false);
  };

  const deletePricelist = async (id) => {
    if (window.confirm('Удалить прайс-лист?')) {
      await fetch(API + '/pricelists/' + id, {method: 'DELETE'});
      await refreshData();
      if (selectedPricelist && selectedPricelist.id === id) {
        setSelectedPricelist(null);
        setPricelistItems([]);
      }
    }
  };

  const copyPricelist = async (pl) => {
    const name = prompt('Название копии:', 'Копия — ' + pl.name);
    if (!name) return;
    await fetch(API + '/pricelists/' + pl.id + '/copy', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name})});
    await refreshData();
  };

  const savePlItem = async () => {
    if (!newPlItem.name || !newPlItem.price) return;
    const data = {...newPlItem, price: Number(newPlItem.price), pricelistId: selectedPricelist.id};
    if (editingPlItem && editingPlItem.id) await fetch(API + '/pricelist-items/' + editingPlItem.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    else await fetch(API + '/pricelist-items', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    await loadPricelistItems(selectedPricelist.id);
    setNewPlItem(createPricelistItemForm());
    setEditingPlItem(null);
  };

  const startInlinePlEdit = (item) => {
    setInlineEditPl(item.id);
    setInlineEditPrice(String(item.price ?? ''));
    setInlineEditPlData({name: item.name || '', unit: item.unit || 'м2', price: String(item.price ?? ''), category: item.category || ''});
  };

  const cancelInlinePlEdit = () => {
    setInlineEditPl(null);
    setInlineEditPrice('');
    setInlineEditPlData(createPricelistItemForm());
  };

  const saveInlinePlItem = async (item) => {
    const data = inlineEditPlData.name ? inlineEditPlData : {...item, price: inlineEditPrice};
    if (!String(data.name || '').trim() || String(data.price || '').trim() === '') return;
    await fetch(API + '/pricelist-items/' + item.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...item, ...data, price: Number(data.price), pricelistId: selectedPricelist.id})});
    await loadPricelistItems(selectedPricelist.id);
    cancelInlinePlEdit();
  };

  const deletePlItem = async (id) => {
    await fetch(API + '/pricelist-items/' + id, {method: 'DELETE'});
    await loadPricelistItems(selectedPricelist.id);
  };

  return {
    savePricelist,
    deletePricelist,
    copyPricelist,
    savePlItem,
    startInlinePlEdit,
    cancelInlinePlEdit,
    saveInlinePlItem,
    deletePlItem,
  };
};
