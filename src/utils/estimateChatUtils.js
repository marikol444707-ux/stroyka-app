export const buildEstimateChatContext = (estimate = {}) => {
  const formatMoney = (value) => Number(value || 0).toLocaleString('ru-RU');
  let total = 0;

  const itemLines = (estimate.sections || []).flatMap(section => (
    (section.items || []).map(item => {
      const work = Number(item.priceWork || 0);
      const material = Number(item.priceMaterial || 0);
      const quantity = Number(item.quantity || 0);
      const sum = item.isImported ? work + material : quantity * (work + material);
      total += sum;
      return `[${section.name}] ${item.name} | ${quantity} ${item.unit} | работа ${work}₽ материал ${material}₽ итого ${sum}₽`;
    })
  ));

  return `Смета "${estimate.name}"\nИтого: ${formatMoney(total)} ₽\nПозиций: ${itemLines.length}\n\nПОЗИЦИИ:\n${itemLines.join('\n')}`;
};
