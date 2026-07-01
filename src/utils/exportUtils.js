export const exportToExcelFile = (data = [], filename = 'export') => {
  const headers = Object.keys(data[0] || {});
  const rows = data.map(row => headers.map(header => row[header] || '').join('\t'));
  const blob = new Blob(['\ufeff' + [headers.join('\t'), ...rows].join('\n')], {
    type: 'text/tab-separated-values;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename + '.xls';
  link.click();
  URL.revokeObjectURL(url);
};
