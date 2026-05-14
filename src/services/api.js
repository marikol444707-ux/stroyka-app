// API сервис СтройКа
const API = window.location.hostname==='localhost'?'http://localhost:8001':'http://192.168.1.82:8001';

const request = async (url, options = {}) => {
  const resp = await fetch(API + url, {
    headers: {'Content-Type': 'application/json'},
    ...options
  });
  return resp.json();
};

export const api = {
  // Проекты
  getProjects: () => request('/projects'),
  createProject: (data) => request('/projects', {method:'POST', body:JSON.stringify(data)}),
  updateProject: (id, data) => request('/projects/'+id, {method:'PUT', body:JSON.stringify(data)}),
  deleteProject: (id) => request('/projects/'+id, {method:'DELETE'}),

  // Пользователи
  getUsers: () => request('/users'),
  createUser: (data) => request('/users', {method:'POST', body:JSON.stringify(data)}),

  // Склад
  getInvoices: () => request('/warehouse-invoices'),
  createInvoice: (data) => request('/warehouse-invoices', {method:'POST', body:JSON.stringify(data)}),

  // Финансы
  getProjectPayments: () => request('/project-payments'),
  createPayment: (data) => request('/project-payments', {method:'POST', body:JSON.stringify(data)}),

  // ИИ
  aiChat: (messages) => request('/ai-chat', {method:'POST', body:JSON.stringify({messages})}),
  scanInvoice: (image) => request('/scan-invoice', {method:'POST', body:JSON.stringify({image})}),

  // Онлайн
  pingOnline: (data) => request('/online', {method:'POST', body:JSON.stringify(data)}),
  getOnline: () => request('/online'),
};

export default API;
