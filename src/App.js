import React, { useState, useEffect } from 'react';

const API = 'http://localhost:8000';
const daysInMonth = Array.from({length: 31}, (_, i) => String(i + 1));

const ROLES = {
  директор: ['dashboard', 'projects', 'clients', 'warehouse', 'staff', 'users', 'pricelists', 'suppliers', 'journal', 'accounting', 'analytics', 'checklists'],
  зам_директора: ['dashboard', 'projects', 'clients', 'warehouse', 'staff', 'pricelists', 'suppliers', 'journal', 'analytics', 'accounting'],
  главный_инженер: ['dashboard', 'projects', 'warehouse', 'staff', 'journal', 'checklists'],
  прораб: ['dashboard', 'projects', 'warehouse', 'staff', 'journal', 'checklists'],
  кладовщик: ['warehouse', 'suppliers'],
  бухгалтер: ['dashboard', 'staff', 'journal', 'accounting'],
  мастер: ['master'],
  заказчик: ['client_view'],
};

const ROLE_LABELS = {
  директор: '👑 Директор', зам_директора: '🏢 Зам. директора',
  главный_инженер: '⚙️ Главный инженер', прораб: '🔨 Прораб',
  кладовщик: '📦 Кладовщик', бухгалтер: '💰 Бухгалтер',
  мастер: '👷 Мастер', заказчик: '🏠 Заказчик',
};

const ROLE_GROUPS = [
  { key: 'директор', label: '👑 Руководство', roles: ['директор', 'зам_директора'] },
  { key: 'инженер', label: '⚙️ Инженерный состав', roles: ['главный_инженер', 'прораб'] },
  { key: 'рабочие', label: '👷 Мастера', roles: ['мастер'] },
  { key: 'снабжение', label: '📦 Снабжение', roles: ['кладовщик'] },
  { key: 'бухгалтерия', label: '💰 Бухгалтерия', roles: ['бухгалтер'] },
  { key: 'заказчики', label: '🏠 Заказчики', roles: ['заказчик'] },
];

const EXPENSE_CATEGORIES = [
  { id: 'materials', label: '📦 Материалы', color: '#ff6b00' },
  { id: 'works', label: '👷 Работы', color: '#28a745' },
  { id: 'delivery', label: '🚚 Доставка', color: '#007bff' },
  { id: 'equipment', label: '🔧 Техника/аренда', color: '#8e44ad' },
  { id: 'utilities', label: '⚡ Коммунальные', color: '#ffc107' },
  { id: 'design', label: '📋 Проектирование', color: '#17a2b8' },
  { id: 'unexpected', label: '❓ Непредвиденные', color: '#dc3545' },
  { id: 'other', label: '📌 Прочее', color: '#6c757d' },
];

const inputStyle = { width: '100%', padding: '10px', marginBottom: '10px', border: '1px solid #ddd', borderRadius: '6px', boxSizing: 'border-box' };
const btnOrange = { padding: '10px 20px', backgroundColor: '#ff6b00', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '15px' };
const btnGray = { padding: '6px 12px', backgroundColor: '#6c757d', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' };
const btnRed = { padding: '6px 12px', backgroundColor: '#dc3545', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' };
const btnGreen = { padding: '6px 12px', backgroundColor: '#28a745', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' };
const btnBlue = { padding: '6px 12px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' };

function App() {
  const [user, setUser] = useState(null);
  const [page, setPage] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regCode, setRegCode] = useState('');
  const [loginError, setLoginError] = useState('');
  const [activePage, setActivePage] = useState('dashboard');
  const [projects, setProjects] = useState([]);
  const [clients, setClients] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [history, setHistory] = useState([]);
  const [staff, setStaff] = useState([]);
  const [piecework, setPiecework] = useState([]);
  const [users, setUsers] = useState([]);
  const [pricelists, setPricelists] = useState([]);
  const [pricelistItems, setPricelistItems] = useState([]);
  const [inviteCodes, setInviteCodes] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [supplyRequests, setSupplyRequests] = useState([]);
  const [supplierOffers, setSupplierOffers] = useState([]);
  const [supplyHistory, setSupplyHistory] = useState([]);
  const [workJournal, setWorkJournal] = useState([]);
  const [masterProfile, setMasterProfile] = useState(null);
  const [masterProfiles, setMasterProfiles] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [interimActs, setInterimActs] = useState([]);
  const [timesheet, setTimesheet] = useState({});
  const [checklists, setChecklists] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showTimesheet, setShowTimesheet] = useState(false);
  const [showPiecework, setShowPiecework] = useState(false);
  const [showInvites, setShowInvites] = useState(false);
  const [showOffers, setShowOffers] = useState(null);
  const [showSupplyHistory, setShowSupplyHistory] = useState(false);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [showPhotoModal, setShowPhotoModal] = useState(null);
  const [showAiModal, setShowAiModal] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [consentChecked, setConsentChecked] = useState(false);
  const [journalFilter, setJournalFilter] = useState('');
  const [accountingTab, setAccountingTab] = useState('contracts');
  const [rejectComment, setRejectComment] = useState('');
  const [rejectingEntry, setRejectingEntry] = useState(null);
  const [editingItem, setEditingItem] = useState(null);
  const [selectedStaff, setSelectedStaff] = useState(null);
  const [selectedPricelist, setSelectedPricelist] = useState(null);
  const [expandedProject, setExpandedProject] = useState(null);
  const [expandedClient, setExpandedClient] = useState(null);
  const [expandedGroup, setExpandedGroup] = useState(null);
  const [searchUser, setSearchUser] = useState('');
  const [newTask, setNewTask] = useState('');
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [selectedWorks, setSelectedWorks] = useState({});
  const [masterProjectId, setMasterProjectId] = useState('');
  const [newPiecework, setNewPiecework] = useState({ staffId: '', description: '', unit: 'м²', quantity: '', pricePerUnit: '', project: '', comment: '' });
  const [newProject, setNewProject] = useState({ name: '', client: '', status: 'Планирование', budget: '', deadline: '', progress: 0, tasks: [], pricelistId: null });
  const [newClient, setNewClient] = useState({ name: '', phone: '', email: '', status: 'Активный', notes: '', deals: [] });
  const [newMaterial, setNewMaterial] = useState({ name: '', unit: 'шт', quantity: '', price: '', minQuantity: '', project: '' });
  const [newStaff, setNewStaff] = useState({ name: '', role: '', phone: '', salary: '', project: '', payType: 'оклад' });
  const [newUser, setNewUser] = useState({ name: '', email: '', password: '', role: 'прораб' });
  const [newPricelist, setNewPricelist] = useState({ name: '', description: '', coefficient: 1.0 });
  const [newPlItem, setNewPlItem] = useState({ name: '', unit: 'м²', price: '', category: '', specialization: '' });
  const [newInviteRole, setNewInviteRole] = useState('мастер');
  const [newSupplier, setNewSupplier] = useState({ name: '', phone: '', email: '', specialization: '', rating: 5.0, notes: '', status: 'Активный' });
  const [newRequest, setNewRequest] = useState({ materialName: '', quantity: '', unit: 'шт', project: '', notes: '' });
  const [newOffer, setNewOffer] = useState({ supplierId: '', pricePerUnit: '', deliveryDays: '', notes: '' });
  const [newContract, setNewContract] = useState({ masterId: '', masterName: '', contractType: 'ГПХ', contractNumber: '', project: '', startDate: '', endDate: '' });
  const [newAct, setNewAct] = useState({ masterId: '', masterName: '', project: '', periodStart: '', periodEnd: '' });
  const [newChecklist, setNewChecklist] = useState({ project: '', title: '', items: [] });
  const [newChecklistItem, setNewChecklistItem] = useState('');
  const [profileData, setProfileData] = useState({ fullName: '', passport: '', inn: '', contractType: 'ГПХ', bankAccount: '', bankName: '', phone: '', specialization: '' });
  const [movement, setMovement] = useState({ id: '', type: 'приход', quantity: '', project: '', invoicePhoto: '' });
  const [smetaFile, setSmetaFile] = useState(null);

  useEffect(() => {
    if (user) {
      loadAll();
      const allowed = ROLES[user.role] || [];
      if (!allowed.includes(activePage)) setActivePage(allowed[0] || 'dashboard');
      if (user.role === 'мастер') loadMasterProfile();
    }
  }, [user]);

  const loadAll = async () => {
    const [p, c, m, h, s, pw, u, pl, ic, sup, sr, so, sh, wj, mp, ct, ia] = await Promise.all([
      fetch(`${API}/projects`).then(r => r.json()),
      fetch(`${API}/clients`).then(r => r.json()),
      fetch(`${API}/materials`).then(r => r.json()),
      fetch(`${API}/warehouse-history`).then(r => r.json()),
      fetch(`${API}/staff`).then(r => r.json()),
      fetch(`${API}/piecework`).then(r => r.json()),
      fetch(`${API}/users`).then(r => r.json()),
      fetch(`${API}/pricelists`).then(r => r.json()),
      fetch(`${API}/invite-codes`).then(r => r.json()),
      fetch(`${API}/suppliers`).then(r => r.json()),
      fetch(`${API}/supply-requests`).then(r => r.json()),
      fetch(`${API}/supplier-offers`).then(r => r.json()),
      fetch(`${API}/supply-history`).then(r => r.json()),
      fetch(`${API}/work-journal`).then(r => r.json()),
      fetch(`${API}/master-profiles`).then(r => r.json()),
      fetch(`${API}/contracts`).then(r => r.json()),
      fetch(`${API}/interim-acts`).then(r => r.json()),
    ]);
    setProjects(p); setClients(c); setMaterials(m);
    setHistory(h); setStaff(s); setPiecework(pw);
    setUsers(u); setPricelists(pl); setInviteCodes(ic);
    setSuppliers(sup); setSupplyRequests(sr);
    setSupplierOffers(so); setSupplyHistory(sh);
    setWorkJournal(wj); setMasterProfiles(mp);
    setContracts(ct); setInterimActs(ia);
  };

  const loadMasterProfile = async () => {
    const profile = await fetch(`${API}/master-profile/${user.id}`).then(r => r.json());
    setMasterProfile(profile);
    if (!profile.profileCompleted) setShowProfileForm(true);
  };

  const loadPricelistItems = async (plId) => {
    const items = await fetch(`${API}/pricelists/${plId}/items`).then(r => r.json());
    setPricelistItems(items);
  };

  const loadTimesheet = async (staffId) => {
    const res = await fetch(`${API}/timesheet/${staffId}`).then(r => r.json());
    const ts = {};
    res.days.forEach(d => ts[`${staffId}-${d}`] = true);
    setTimesheet(prev => ({ ...prev, ...ts }));
  };

  const uploadPhoto = async (file) => {
    setUploadingPhoto(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`${API}/upload-photo`, { method: 'POST', body: formData });
      const data = await res.json();
      setUploadingPhoto(false);
      return data.url;
    } catch {
      setUploadingPhoto(false);
      return '';
    }
  };

  const handleLogin = async () => {
    setLoginError('');
    try {
      const res = await fetch(`${API}/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
      if (!res.ok) { setLoginError('Неверный email или пароль'); return; }
      setUser(await res.json());
    } catch { setLoginError('Ошибка подключения'); }
  };

  const handleRegister = async () => {
    if (!regName || !regEmail || !regPassword || !regCode) { setLoginError('Заполните все поля'); return; }
    setLoginError('');
    try {
      const res = await fetch(`${API}/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: regName, email: regEmail, password: regPassword, code: regCode }) });
      if (!res.ok) { const err = await res.json(); setLoginError(err.detail); return; }
      setUser(await res.json());
    } catch { setLoginError('Ошибка подключения'); }
  };

  const saveProfile = async () => {
    if (!profileData.fullName || !profileData.inn || !profileData.bankAccount) { alert('Заполните обязательные поля'); return; }
    if (!consentChecked) { alert('Необходимо дать согласие на обработку персональных данных (152-ФЗ)'); return; }
    const res = await fetch(`${API}/master-profile`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...profileData, userId: user.id }) });
    setMasterProfile(await res.json());
    setShowProfileForm(false);
  };

  const canAccess = (p) => user && (ROLES[user.role] || []).includes(p);
  const isFinanceRole = () => ['директор', 'зам_директора', 'бухгалтер'].includes(user?.role);
  const statusColor = (s) => s === 'В работе' || s === 'Активный' ? '#ff6b00' : s === 'Завершён' ? '#28a745' : '#6c757d';
  const stockColor = (m) => m.quantity === 0 ? '#dc3545' : m.minQuantity && m.quantity < m.minQuantity ? '#ffc107' : '#28a745';
  const roleColor = (r) => ({ директор: '#ff6b00', зам_директора: '#e67e00', главный_инженер: '#8e44ad', прораб: '#007bff', кладовщик: '#28a745', бухгалтер: '#6c757d', мастер: '#e83e8c', заказчик: '#17a2b8' }[r] || '#333');
  const workedDays = (staffId) => daysInMonth.filter(d => timesheet[`${staffId}-${d}`]).length;
  const staffPieceworkTotal = (staffId) => piecework.filter(p => Number(p.staffId) === staffId).reduce((sum, p) => sum + p.total, 0);
  const calcSalary = (s) => s.payType === 'сдельно' ? staffPieceworkTotal(s.id) : Math.round((s.salary / 31) * workedDays(s.id));
  const projectMaterialCost = (n) => history.filter(h => h.project === n && h.type === 'расход').reduce((sum, h) => { const mat = materials.find(m => m.name === h.material); return sum + (mat ? mat.price * h.quantity : 0); }, 0);
  const projectLaborCost = (n) => staff.filter(s => s.project === n).reduce((sum, s) => sum + calcSalary(s), 0) + piecework.filter(p => p.project === n).reduce((sum, p) => sum + p.total, 0);
  const lowStockMaterials = materials.filter(m => m.minQuantity && m.quantity < m.minQuantity);
  const pendingJournal = workJournal.filter(j => j.status === 'На проверке').length;

  const runAI = (type) => {
    setAiLoading(true);
    setShowAiModal(true);
    setTimeout(() => {
      setAiLoading(false);
      setAiResult({
        title: type === 'kp' ? '🤖 Анализ КП' : type === 'smeta' ? '🤖 Анализ сметы' : type === 'invoice' ? '🤖 Распознавание накладной' : '🤖 Прогноз перерасхода',
        content: 'ИИ модуль готов к подключению! Получите API ключ на console.anthropic.com и мы активируем за 30 минут.'
      });
    }, 1500);
  };

  const saveProject = async () => {
    if (!newProject.name) { alert('Введите название'); return; }
    const data = { ...newProject, budget: Number(newProject.budget) };
    if (editingItem) await fetch(`${API}/projects/${editingItem.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    else await fetch(`${API}/projects`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    await loadAll();
    setNewProject({ name: '', client: '', status: 'Планирование', budget: '', deadline: '', progress: 0, tasks: [], pricelistId: null });
    setEditingItem(null); setShowForm(false);
  };
  const deleteProject = async (id) => { if (window.confirm('Удалить?')) { await fetch(`${API}/projects/${id}`, { method: 'DELETE' }); await loadAll(); } };
  const editProject = (p) => { setEditingItem(p); setNewProject({...p}); setShowForm(true); };
  const addTaskToProject = async (p) => {
    if (!newTask) return;
    await fetch(`${API}/projects/${p.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...p, tasks: [...(p.tasks || []), newTask] }) });
    await loadAll(); setNewTask('');
  };
  const removeTask = async (p, i) => {
    await fetch(`${API}/projects/${p.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...p, tasks: p.tasks.filter((_, idx) => idx !== i) }) });
    await loadAll();
  };

  const saveClient = async () => {
    if (!newClient.name) { alert('Введите имя'); return; }
    if (editingItem) await fetch(`${API}/clients/${editingItem.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newClient) });
    else await fetch(`${API}/clients`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newClient) });
    await loadAll();
    setNewClient({ name: '', phone: '', email: '', status: 'Активный', notes: '', deals: [] });
    setEditingItem(null); setShowForm(false);
  };
  const deleteClient = async (id) => { if (window.confirm('Удалить?')) { await fetch(`${API}/clients/${id}`, { method: 'DELETE' }); await loadAll(); } };
  const editClient = (c) => { setEditingItem(c); setNewClient({...c}); setShowForm(true); };

  const saveMaterial = async () => {
    if (!newMaterial.name) { alert('Введите название'); return; }
    const data = { ...newMaterial, quantity: Number(newMaterial.quantity), price: Number(newMaterial.price), minQuantity: Number(newMaterial.minQuantity) };
    if (editingItem) await fetch(`${API}/materials/${editingItem.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    else await fetch(`${API}/materials`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    await loadAll();
    setNewMaterial({ name: '', unit: 'шт', quantity: '', price: '', minQuantity: '', project: '' });
    setEditingItem(null); setShowForm(false);
  };
  const deleteMaterial = async (id) => { if (window.confirm('Удалить?')) { await fetch(`${API}/materials/${id}`, { method: 'DELETE' }); await loadAll(); } };

  const applyMovement = async () => {
    if (!movement.id || !movement.quantity) { alert('Заполните поля'); return; }
    const mat = materials.find(m => m.id === Number(movement.id));
    const qty = Number(movement.quantity);
    const newQty = movement.type === 'приход' ? mat.quantity + qty : Math.max(0, mat.quantity - qty);
    await fetch(`${API}/materials/${mat.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...mat, quantity: newQty }) });
    await fetch(`${API}/warehouse-history`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ material: mat.name, type: movement.type, quantity: qty, date: new Date().toISOString().split('T')[0], project: movement.project }) });
    if (movement.type === 'приход' && movement.invoicePhoto) {
      setExpenses(prev => [...prev, { id: Date.now(), project: movement.project, category: 'materials', description: `Накладная: ${mat.name}`, amount: mat.price * qty, date: new Date().toISOString().split('T')[0], invoicePhoto: movement.invoicePhoto, status: 'Ожидает подтверждения', addedBy: user.name }]);
    }
    await loadAll();
    setMovement({ id: '', type: 'приход', quantity: '', project: '', invoicePhoto: '' });
  };

  const saveStaff = async () => {
    if (!newStaff.name) { alert('Введите имя'); return; }
    const data = { ...newStaff, salary: Number(newStaff.salary) };
    if (editingItem) await fetch(`${API}/staff/${editingItem.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    else await fetch(`${API}/staff`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    await loadAll();
    setNewStaff({ name: '', role: '', phone: '', salary: '', project: '', payType: 'оклад' });
    setEditingItem(null); setShowForm(false);
  };
  const deleteStaff = async (id) => { if (window.confirm('Удалить?')) { await fetch(`${API}/staff/${id}`, { method: 'DELETE' }); await loadAll(); } };

  const addPiecework = async () => {
    if (!newPiecework.staffId || !newPiecework.description || !newPiecework.quantity || !newPiecework.pricePerUnit) { alert('Заполните поля'); return; }
    await fetch(`${API}/piecework`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newPiecework, total: Number(newPiecework.quantity) * Number(newPiecework.pricePerUnit), date: new Date().toISOString().split('T')[0], photoUrl: '' }) });
    await loadAll();
    setNewPiecework({ staffId: '', description: '', unit: 'м²', quantity: '', pricePerUnit: '', project: '', comment: '' });
  };

  const addMasterWorks = async () => {
    const project = projects.find(p => p.id === Number(masterProjectId));
    if (!project) return;
    const pl = pricelists.find(p => p.id === project.pricelistId);
    const coeff = pl ? pl.coefficient : 1.0;
    const now = new Date();
    const weekNumber = Math.ceil(now.getDate() / 7);
    let hasWork = false;
    for (const [itemId, workData] of Object.entries(selectedWorks)) {
      if (!workData.quantity || Number(workData.quantity) <= 0) continue;
      const item = pricelistItems.find(i => i.id === Number(itemId));
      if (!item) continue;
      hasWork = true;
      const pricePerUnit = item.price * coeff;
      const total = Number(workData.quantity) * pricePerUnit;
      await fetch(`${API}/piecework`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ staffId: String(user.id), description: item.name, unit: item.unit, quantity: Number(workData.quantity), pricePerUnit, total, project: project.name, date: now.toISOString().split('T')[0], comment: workData.comment || '', photoUrl: workData.photoUrl || '' }) });
      await fetch(`${API}/work-journal`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ masterId: user.id, masterName: user.name, project: project.name, description: item.name, unit: item.unit, quantity: Number(workData.quantity), pricePerUnit, total, date: now.toISOString().split('T')[0], comment: workData.comment || '', weekNumber, photoUrl: workData.photoUrl || '' }) });
    }
    if (!hasWork) { alert('Введите количество хотя бы для одной работы'); return; }
    await loadAll();
    setSelectedWorks({});
    setMasterProjectId('');
    setPricelistItems([]);
    alert('✅ Все работы отправлены на проверку!');
  };

  const confirmJournalEntry = async (entry) => {
    await fetch(`${API}/work-journal/${entry.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'Подтверждено', confirmedBy: user.name, confirmedAt: new Date().toISOString().split('T')[0] }) });
    await loadAll();
  };

  const rejectJournalEntry = async (entry, comment) => {
    await fetch(`${API}/work-journal/${entry.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'Отклонено', confirmedBy: user.name, confirmedAt: new Date().toISOString().split('T')[0], comment: comment || entry.comment }) });
    await loadAll();
    setRejectingEntry(null);
    setRejectComment('');
  };

  const saveUser = async () => {
    if (!newUser.name || !newUser.email || (!editingItem && !newUser.password)) { alert('Заполните поля'); return; }
    if (editingItem) await fetch(`${API}/users/${editingItem.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newUser) });
    else await fetch(`${API}/users`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newUser) });
    await loadAll();
    setNewUser({ name: '', email: '', password: '', role: 'прораб' });
    setEditingItem(null); setShowForm(false);
  };
  const deleteUser = async (id) => { if (id === user.id) { alert('Нельзя удалить себя!'); return; } if (window.confirm('Удалить?')) { await fetch(`${API}/users/${id}`, { method: 'DELETE' }); await loadAll(); } };
  const createInviteCode = async () => { await fetch(`${API}/invite-codes`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role: newInviteRole }) }); await loadAll(); };
  const deleteInviteCode = async (id) => { await fetch(`${API}/invite-codes/${id}`, { method: 'DELETE' }); await loadAll(); };

  const savePricelist = async () => {
    if (!newPricelist.name) { alert('Введите название'); return; }
    if (editingItem) await fetch(`${API}/pricelists/${editingItem.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newPricelist) });
    else await fetch(`${API}/pricelists`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newPricelist) });
    await loadAll();
    setNewPricelist({ name: '', description: '', coefficient: 1.0 });
    setEditingItem(null); setShowForm(false);
  };
  const deletePricelist = async (id) => { if (window.confirm('Удалить?')) { await fetch(`${API}/pricelists/${id}`, { method: 'DELETE' }); await loadAll(); } };
  const copyPricelist = async (pl) => { const name = prompt('Название копии:', `Копия — ${pl.name}`); if (!name) return; await fetch(`${API}/pricelists/${pl.id}/copy`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) }); await loadAll(); };

  const savePlItem = async () => {
    if (!newPlItem.name || !newPlItem.price) { alert('Заполните поля'); return; }
    const data = { ...newPlItem, price: Number(newPlItem.price), pricelistId: selectedPricelist.id };
    if (editingItem) await fetch(`${API}/pricelist-items/${editingItem.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    else await fetch(`${API}/pricelist-items`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    await loadPricelistItems(selectedPricelist.id);
    setNewPlItem({ name: '', unit: 'м²', price: '', category: '', specialization: '' });
    setEditingItem(null);
  };
  const deletePlItem = async (id) => { await fetch(`${API}/pricelist-items/${id}`, { method: 'DELETE' }); await loadPricelistItems(selectedPricelist.id); };

  const saveSupplier = async () => {
    if (!newSupplier.name) { alert('Введите название'); return; }
    if (editingItem) await fetch(`${API}/suppliers/${editingItem.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newSupplier) });
    else await fetch(`${API}/suppliers`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newSupplier) });
    await loadAll();
    setNewSupplier({ name: '', phone: '', email: '', specialization: '', rating: 5.0, notes: '', status: 'Активный' });
    setEditingItem(null); setShowForm(false);
  };
  const deleteSupplier = async (id) => { if (window.confirm('Удалить?')) { await fetch(`${API}/suppliers/${id}`, { method: 'DELETE' }); await loadAll(); } };

  const saveRequest = async () => {
    if (!newRequest.materialName || !newRequest.quantity) { alert('Заполните поля'); return; }
    await fetch(`${API}/supply-requests`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newRequest, quantity: Number(newRequest.quantity), createdBy: user.name, date: new Date().toISOString().split('T')[0] }) });
    await loadAll();
    setNewRequest({ materialName: '', quantity: '', unit: 'шт', project: '', notes: '' });
    setShowForm(false);
  };

  const cancelRequest = async (id) => {
    await fetch(`${API}/supply-requests/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'Отменена' }) });
    await loadAll();
  };

  const saveOffer = async (requestId) => {
    if (!newOffer.supplierId || !newOffer.pricePerUnit) { alert('Заполните поля'); return; }
    const req = supplyRequests.find(r => r.id === requestId);
    await fetch(`${API}/supplier-offers`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ requestId, supplierId: Number(newOffer.supplierId), pricePerUnit: Number(newOffer.pricePerUnit), totalPrice: Number(newOffer.pricePerUnit) * req.quantity, deliveryDays: Number(newOffer.deliveryDays) || 0, notes: newOffer.notes }) });
    await loadAll();
    setNewOffer({ supplierId: '', pricePerUnit: '', deliveryDays: '', notes: '' });
  };

  const approveOffer = async (offer) => {
    await fetch(`${API}/supplier-offers/${offer.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'Утверждено' }) });
    await fetch(`${API}/supply-requests/${offer.requestId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'Утверждено' }) });
    const req = supplyRequests.find(r => r.id === offer.requestId);
    const sup = suppliers.find(s => s.id === offer.supplierId);
    await fetch(`${API}/supply-history`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ supplierId: offer.supplierId, materialName: req?.materialName, quantity: req?.quantity, unit: req?.unit, pricePerUnit: offer.pricePerUnit, totalPrice: offer.totalPrice, project: req?.project, date: new Date().toISOString().split('T')[0], status: 'Ожидает поставки' }) });
    await loadAll();
    alert(`✅ Предложение от "${sup?.name}" утверждено!`);
  };

  const confirmDelivery = async (delivery) => {
    await fetch(`${API}/supply-history/${delivery.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'Доставлено', confirmedBy: user.name }) });
    const mat = materials.find(m => m.name === delivery.materialName);
    if (mat) {
      await fetch(`${API}/materials/${mat.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...mat, quantity: mat.quantity + delivery.quantity }) });
      await fetch(`${API}/warehouse-history`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ material: delivery.materialName, type: 'приход', quantity: delivery.quantity, date: new Date().toISOString().split('T')[0], project: delivery.project }) });
    }
    await loadAll();
  };

  const toggleDay = async (staffId, day) => {
    await fetch(`${API}/timesheet`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ staffId, day }) });
    setTimesheet(prev => ({ ...prev, [`${staffId}-${day}`]: !prev[`${staffId}-${day}`] }));
  };

  const createContract = async () => {
    if (!newContract.masterId || !newContract.contractNumber || !newContract.project) { alert('Заполните поля'); return; }
    await fetch(`${API}/contracts`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newContract) });
    await loadAll();
    setNewContract({ masterId: '', masterName: '', contractType: 'ГПХ', contractNumber: '', project: '', startDate: '', endDate: '' });
    setShowForm(false);
  };

  const createInterimAct = async () => {
    if (!newAct.masterId || !newAct.project || !newAct.periodStart || !newAct.periodEnd) { alert('Заполните все поля'); return; }
    const masterWorks = workJournal.filter(j => j.masterId === Number(newAct.masterId) && j.project === newAct.project && j.status === 'Подтверждено');
    const total = masterWorks.reduce((sum, w) => sum + w.total, 0);
    const contract = contracts.find(c => c.masterId === Number(newAct.masterId) && c.project === newAct.project);
    await fetch(`${API}/interim-acts`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newAct, masterId: Number(newAct.masterId), contractId: contract?.id, totalAmount: total }) });
    await loadAll();
    setNewAct({ masterId: '', masterName: '', project: '', periodStart: '', periodEnd: '' });
    setShowForm(false);
  };

  const printAct = (entry) => {
    const w = window.open('', '_blank');
    w.document.write(`<html><head><title>АОСР</title><style>body{font-family:Arial,sans-serif;padding:40px;font-size:13px}h2{text-align:center;text-transform:uppercase}table{width:100%;border-collapse:collapse;margin:15px 0}td,th{border:1px solid #333;padding:6px}th{background:#f5f5f5}.sign{margin-top:50px;display:flex;justify-content:space-between}.sign-block{width:22%;text-align:center}.sign-line{border-top:1px solid #333;margin-top:35px;padding-top:4px;font-size:11px}</style></head><body>
    <h2>АКТ ОСВИДЕТЕЛЬСТВОВАНИЯ СКРЫТЫХ РАБОТ № ${entry.id}</h2>
    <p style="text-align:center">от ${entry.date}</p>
    <table><tr><th>Объект</th><td>${entry.project}</td></tr><tr><th>Исполнитель</th><td>${entry.masterName}</td></tr></table>
    <p><b>К освидетельствованию предъявлены:</b></p>
    <table><tr><th>№</th><th>Наименование работ</th><th>Ед. изм.</th><th>Объём</th></tr>
    <tr><td>1</td><td>${entry.description}</td><td>${entry.unit}</td><td>${entry.quantity}</td></tr></table>
    <p>Работы выполнены в соответствии с проектной документацией и требованиями нормативных документов.</p>
    <p><b>Разрешается производство последующих работ.</b></p>
    <div class="sign">
    <div class="sign-block"><div class="sign-line">Мастер<br>${entry.masterName}</div></div>
    <div class="sign-block"><div class="sign-line">Прораб<br>${entry.confirmedBy || '___'}</div></div>
    <div class="sign-block"><div class="sign-line">Технадзор<br>___________</div></div>
    <div class="sign-block"><div class="sign-line">Заказчик<br>___________</div></div>
    </div></body></html>`);
    w.document.close(); w.print();
  };

  const printContract = (profile, contract) => {
    const w = window.open('', '_blank');
    w.document.write(`<html><head><title>Договор</title><style>body{font-family:Arial,sans-serif;padding:40px;font-size:13px;line-height:1.8}h2{text-align:center}.sign{margin-top:60px;display:flex;justify-content:space-between}.sign-block{width:45%}.sign-line{border-top:1px solid #333;margin-top:40px;padding-top:5px;font-size:12px}</style></head><body>
    <h2>ДОГОВОР ${contract.contractType} № ${contract.contractNumber}</h2>
    <p style="text-align:right">Дата: ${contract.startDate}</p>
    <p><b>Исполнитель:</b> ${profile.fullName}, ИНН: ${profile.inn}, ${profile.contractType}</p>
    <p><b>Банк:</b> ${profile.bankName}, счёт: ${profile.bankAccount}</p>
    <p><b>Объект:</b> ${contract.project} | <b>Период:</b> ${contract.startDate} — ${contract.endDate}</p>
    <br><p><b>1. ПРЕДМЕТ ДОГОВОРА</b></p>
    <p>1.1. Исполнитель выполняет строительные работы на объекте согласно прайс-листу.</p>
    <p>1.2. Специализация: ${profile.specialization}</p>
    <br><p><b>2. ОПЛАТА</b></p>
    <p>2.1. Оплата по факту подтверждённых прорабом работ на основании акта.</p>
    <br><p><b>3. ПЕРСОНАЛЬНЫЕ ДАННЫЕ</b></p>
    <p>3.1. Исполнитель даёт согласие на обработку персональных данных согласно ФЗ №152-ФЗ.</p>
    <div class="sign">
    <div class="sign-block"><p><b>ЗАКАЗЧИК:</b></p><div class="sign-line">Подпись ___________</div></div>
    <div class="sign-block"><p><b>ИСПОЛНИТЕЛЬ:</b></p><div class="sign-line">${profile.fullName}<br>Подпись ___________</div></div>
    </div></body></html>`);
    w.document.close(); w.print();
  };

  const printInterimAct = (act) => {
    const profile = masterProfiles.find(p => p.userId === act.masterId);
    const masterWorks = workJournal.filter(j => j.masterId === act.masterId && j.project === act.project && j.status === 'Подтверждено');
    const w = window.open('', '_blank');
    w.document.write(`<html><head><title>Акт</title><style>body{font-family:Arial,sans-serif;padding:40px;font-size:13px}h2{text-align:center}table{width:100%;border-collapse:collapse;margin:15px 0}td,th{border:1px solid #333;padding:7px}th{background:#f5f5f5}.sign{margin-top:50px;display:flex;justify-content:space-between}.sign-block{width:30%;text-align:center}.sign-line{border-top:1px solid #333;margin-top:35px;padding-top:4px;font-size:11px}</style></head><body>
    <h2>АКТ ВЫПОЛНЕННЫХ РАБОТ № ${act.id}</h2>
    <p style="text-align:center">Период: ${act.periodStart} — ${act.periodEnd} | Объект: ${act.project}</p>
    <p><b>Исполнитель:</b> ${act.masterName} ${profile ? `| ИНН: ${profile.inn} | ${profile.bankName} | ${profile.bankAccount}` : ''}</p>
    <table><tr><th>№</th><th>Работа</th><th>Ед.</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>
    ${masterWorks.map((w, i) => `<tr><td>${i+1}</td><td>${w.description}</td><td>${w.unit}</td><td>${w.quantity}</td><td>${w.pricePerUnit?.toLocaleString()}</td><td>${w.total?.toLocaleString()}</td></tr>`).join('')}
    <tr style="background:#f5f5f5"><td colspan="5"><b>ИТОГО:</b></td><td><b>${act.totalAmount?.toLocaleString()} руб.</b></td></tr></table>
    <div class="sign">
    <div class="sign-block"><div class="sign-line">Заказчик<br>___________</div></div>
    <div class="sign-block"><div class="sign-line">Прораб<br>___________</div></div>
    <div class="sign-block"><div class="sign-line">Исполнитель<br>${act.masterName}</div></div>
    </div></body></html>`);
    w.document.close(); w.print();
  };

  const printKS2 = (project) => {
    const projectWorks = workJournal.filter(j => j.project === project.name && j.status === 'Подтверждено');
    const w = window.open('', '_blank');
    w.document.write(`<html><head><title>КС-2</title><style>body{font-family:Arial,sans-serif;padding:40px;font-size:12px}h2{text-align:center}table{width:100%;border-collapse:collapse;margin:15px 0}td,th{border:1px solid #333;padding:6px}th{background:#f5f5f5}.sign{margin-top:50px;display:flex;justify-content:space-between}.sign-block{width:45%}.sign-line{border-top:1px solid #333;margin-top:35px;padding-top:4px;font-size:11px}</style></head><body>
    <h2>АКТ О ПРИЁМКЕ ВЫПОЛНЕННЫХ РАБОТ (КС-2)</h2>
    <p>Объект: ${project.name} | Заказчик: ${project.client} | Дата: ${new Date().toLocaleDateString('ru-RU')}</p>
    <table><tr><th>№</th><th>Наименование работ</th><th>Исполнитель</th><th>Ед.</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>
    ${projectWorks.map((w, i) => `<tr><td>${i+1}</td><td>${w.description}</td><td>${w.masterName}</td><td>${w.unit}</td><td>${w.quantity}</td><td>${w.pricePerUnit?.toLocaleString()}</td><td>${w.total?.toLocaleString()}</td></tr>`).join('')}
    <tr style="background:#f5f5f5"><td colspan="6"><b>ИТОГО:</b></td><td><b>${projectWorks.reduce((s,w) => s+w.total, 0).toLocaleString()} руб.</b></td></tr></table>
    <div class="sign">
    <div class="sign-block"><div class="sign-line">Заказчик<br>___________</div></div>
    <div class="sign-block"><div class="sign-line">Подрядчик<br>___________</div></div>
    </div></body></html>`);
    w.document.close(); w.print();
  };

  const navigateTo = (p) => {
    if (canAccess(p)) {
      setActivePage(p);
      setShowForm(false);
      setShowHistory(false);
      setExpandedProject(null);
      setExpandedClient(null);
      setEditingItem(null);
      setShowPiecework(false);
      setSelectedPricelist(null);
      setPricelistItems([]);
      setShowInvites(false);
      setShowOffers(null);
      setShowSupplyHistory(false);
    }
  };

  if (!user) {
    if (page === 'register') {
      return (
        <div style={{display:'flex',justifyContent:'center',alignItems:'center',height:'100vh',backgroundColor:'#f0f2f5'}}>
          <div style={{backgroundColor:'white',padding:'40px',borderRadius:'10px',boxShadow:'0 2px 10px rgba(0,0,0,0.1)',width:'380px'}}>
            <h2 style={{textAlign:'center',color:'#333'}}>🏗️ СтройКа</h2>
            <p style={{textAlign:'center',color:'#999',marginBottom:'30px',fontSize:'14px'}}>Регистрация по коду приглашения</p>
            <input placeholder="Ваше имя" value={regName} onChange={e=>setRegName(e.target.value)} style={{...inputStyle,fontSize:'16px'}}/>
            <input type="email" placeholder="Email" value={regEmail} onChange={e=>setRegEmail(e.target.value)} style={{...inputStyle,fontSize:'16px'}}/>
            <input type="password" placeholder="Пароль" value={regPassword} onChange={e=>setRegPassword(e.target.value)} style={{...inputStyle,fontSize:'16px'}}/>
            <input placeholder="Код приглашения" value={regCode} onChange={e=>setRegCode(e.target.value.toUpperCase())} style={{...inputStyle,fontSize:'16px',letterSpacing:'3px',fontWeight:'bold'}}/>
            {loginError&&<p style={{color:'#dc3545',fontSize:'14px'}}>{loginError}</p>}
            <button onClick={handleRegister} style={{...btnOrange,width:'100%',padding:'12px',fontSize:'16px'}}>Зарегистрироваться</button>
            <p style={{textAlign:'center',marginTop:'15px',color:'#666',fontSize:'14px'}}>Уже есть аккаунт? <span onClick={()=>{setPage('login');setLoginError('');}} style={{color:'#ff6b00',cursor:'pointer'}}>Войти</span></p>
          </div>
        </div>
      );
    }
    return (
      <div style={{display:'flex',justifyContent:'center',alignItems:'center',height:'100vh',backgroundColor:'#f0f2f5'}}>
        <div style={{backgroundColor:'white',padding:'40px',borderRadius:'10px',boxShadow:'0 2px 10px rgba(0,0,0,0.1)',width:'380px'}}>
          <h2 style={{textAlign:'center',color:'#333'}}>🏗️ СтройКа</h2>
          <p style={{textAlign:'center',color:'#999',marginBottom:'30px',fontSize:'14px'}}>Система управления строительством</p>
          <input type="email" placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)} style={{...inputStyle,fontSize:'16px'}}/>
          <input type="password" placeholder="Пароль" value={password} onChange={e=>setPassword(e.target.value)} onKeyDown={e=>e.key==='Enter'&&handleLogin()} style={{...inputStyle,fontSize:'16px'}}/>
          {loginError&&<p style={{color:'#dc3545',fontSize:'14px'}}>{loginError}</p>}
          <button onClick={handleLogin} style={{...btnOrange,width:'100%',padding:'12px',fontSize:'16px',marginBottom:'10px'}}>Войти</button>
          <button onClick={()=>{setPage('register');setLoginError('');}} style={{width:'100%',padding:'12px',fontSize:'16px',backgroundColor:'white',border:'2px solid #ff6b00',color:'#ff6b00',borderRadius:'6px',cursor:'pointer'}}>Зарегистрироваться по коду</button>
          <div style={{marginTop:'20px',padding:'15px',backgroundColor:'#f8f9fa',borderRadius:'8px',fontSize:'12px',color:'#666'}}>
            <b>Аккаунты:</b><br/>👑 admin@stroyka.ru / admin123<br/>💰 buh@stroyka.ru / buh123<br/>🔨 prorab@stroyka.ru / prorab123<br/>👷 master@stroyka.ru / master123
          </div>
        </div>
      </div>
    );
  }

  if (user.role === 'заказчик') {
    const myProjects = projects.filter(p => p.client === user.name);
    return (
      <div style={{display:'flex',height:'100vh',backgroundColor:'#f0f2f5'}}>
        <div style={{width:'220px',backgroundColor:'#1a1a2e',color:'white',padding:'20px 0',flexShrink:0,display:'flex',flexDirection:'column'}}>
          <h3 style={{textAlign:'center',color:'#ff6b00'}}>🏗️ СтройКа</h3>
          <div style={{textAlign:'center',marginBottom:'20px'}}>
            <span style={{backgroundColor:'#17a2b8',color:'white',padding:'2px 10px',borderRadius:'20px',fontSize:'12px'}}>заказчик</span>
            <p style={{color:'#aaa',fontSize:'13px',margin:'5px 0 0'}}>{user.name}</p>
          </div>
          <div style={{padding:'15px 25px',backgroundColor:'#ff6b00',borderLeft:'4px solid white'}}>🏠 Мои объекты</div>
          <div style={{marginTop:'auto'}}><div onClick={()=>setUser(null)} style={{padding:'15px 25px',cursor:'pointer',color:'#aaa'}}>🚪 Выйти</div></div>
        </div>
        <div style={{flex:1,padding:'30px',overflowY:'auto'}}>
          <h2 style={{color:'#333',marginBottom:'20px'}}>🏠 Мои объекты</h2>
          {myProjects.map(p=>{
            const works=workJournal.filter(j=>j.project===p.name&&j.status==='Подтверждено');
            const labCost=works.reduce((s,w)=>s+w.total,0);
            const pct=p.budget>0?Math.min(100,Math.round((labCost/p.budget)*100)):0;
            return (
              <div key={p.id} style={{backgroundColor:'white',padding:'25px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                  <h2 style={{margin:0}}>{p.name}</h2>
                  <span style={{backgroundColor:statusColor(p.status),color:'white',padding:'6px 15px',borderRadius:'20px'}}>{p.status}</span>
                </div>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'15px',marginBottom:'15px'}}>
                  <div style={{backgroundColor:'#f8f9fa',padding:'15px',borderRadius:'8px',textAlign:'center'}}>
                    <div style={{fontSize:'28px',fontWeight:'bold',color:'#ff6b00'}}>{p.progress}%</div>
                    <div style={{color:'#666',fontSize:'13px'}}>Прогресс</div>
                  </div>
                  <div style={{backgroundColor:'#f8f9fa',padding:'15px',borderRadius:'8px',textAlign:'center'}}>
                    <div style={{fontSize:'16px',fontWeight:'bold',color:'#28a745'}}>{labCost.toLocaleString()} руб.</div>
                    <div style={{color:'#666',fontSize:'13px'}}>Освоено</div>
                  </div>
                  <div style={{backgroundColor:'#f8f9fa',padding:'15px',borderRadius:'8px',textAlign:'center'}}>
                    <div style={{fontSize:'16px',fontWeight:'bold',color:'#007bff'}}>{p.budget.toLocaleString()} руб.</div>
                    <div style={{color:'#666',fontSize:'13px'}}>Бюджет</div>
                  </div>
                </div>
                <div style={{backgroundColor:'#f0f2f5',borderRadius:'10px',height:'10px',marginBottom:'15px'}}>
                  <div style={{backgroundColor:'#ff6b00',width:`${pct}%`,height:'10px',borderRadius:'10px'}}/>
                </div>
                <h4 style={{marginBottom:'10px'}}>✅ Выполненные работы</h4>
                {works.slice(0,5).map(w=>(
                  <div key={w.id} style={{padding:'8px 0',borderBottom:'1px solid #f5f5f5',fontSize:'14px'}}>
                    {w.description} — {w.quantity} {w.unit} | 👷 {w.masterName} | 📅 {w.date}
                  </div>
                ))}
                <button onClick={()=>printKS2(p)} style={{...btnBlue,marginTop:'15px',fontSize:'13px'}}>📄 КС-2</button>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (user.role === 'мастер') {
    if (showProfileForm) {
      return (
        <div style={{display:'flex',justifyContent:'center',alignItems:'center',minHeight:'100vh',backgroundColor:'#f0f2f5',padding:'20px'}}>
          <div style={{backgroundColor:'white',padding:'40px',borderRadius:'10px',boxShadow:'0 2px 10px rgba(0,0,0,0.1)',width:'500px',maxHeight:'90vh',overflowY:'auto'}}>
            <h2 style={{textAlign:'center',color:'#333'}}>👷 Заполните профиль</h2>
            <label style={{color:'#555',fontSize:'13px',fontWeight:'bold'}}>ФИО *</label>
            <input placeholder="Иванов Иван Иванович" value={profileData.fullName} onChange={e=>setProfileData({...profileData,fullName:e.target.value})} style={inputStyle}/>
            <label style={{color:'#555',fontSize:'13px',fontWeight:'bold'}}>Паспорт</label>
            <input placeholder="1234 567890" value={profileData.passport} onChange={e=>setProfileData({...profileData,passport:e.target.value})} style={inputStyle}/>
            <label style={{color:'#555',fontSize:'13px',fontWeight:'bold'}}>ИНН *</label>
            <input placeholder="123456789012" value={profileData.inn} onChange={e=>setProfileData({...profileData,inn:e.target.value})} style={inputStyle}/>
            <label style={{color:'#555',fontSize:'13px',fontWeight:'bold'}}>Тип договора</label>
            <select value={profileData.contractType} onChange={e=>setProfileData({...profileData,contractType:e.target.value})} style={inputStyle}>
              <option>ГПХ</option><option>ИП</option><option>Самозанятый</option>
            </select>
            <label style={{color:'#555',fontSize:'13px',fontWeight:'bold'}}>Номер счёта *</label>
            <input placeholder="40817810000000000000" value={profileData.bankAccount} onChange={e=>setProfileData({...profileData,bankAccount:e.target.value})} style={inputStyle}/>
            <label style={{color:'#555',fontSize:'13px',fontWeight:'bold'}}>Банк</label>
            <input placeholder="Сбербанк" value={profileData.bankName} onChange={e=>setProfileData({...profileData,bankName:e.target.value})} style={inputStyle}/>
            <label style={{color:'#555',fontSize:'13px',fontWeight:'bold'}}>Телефон</label>
            <input placeholder="+7 900 000-00-00" value={profileData.phone} onChange={e=>setProfileData({...profileData,phone:e.target.value})} style={inputStyle}/>
            <label style={{color:'#555',fontSize:'13px',fontWeight:'bold'}}>Специализация</label>
            <select value={profileData.specialization} onChange={e=>setProfileData({...profileData,specialization:e.target.value})} style={inputStyle}>
              <option value="">Выберите</option>
              <option>Каменщик</option><option>Электрик</option><option>Сантехник</option>
              <option>Отделочник</option><option>Кровельщик</option><option>Бетонщик</option>
              <option>Монтажник</option><option>Плотник</option><option>Сварщик</option>
            </select>
            <div style={{backgroundColor:'#f8f9fa',padding:'15px',borderRadius:'8px',marginBottom:'15px',border:'1px solid #dee2e6'}}>
              <label style={{display:'flex',alignItems:'flex-start',gap:'12px',cursor:'pointer'}}>
                <input type="checkbox" checked={consentChecked} onChange={e=>setConsentChecked(e.target.checked)} style={{marginTop:'3px',width:'18px',height:'18px',cursor:'pointer',flexShrink:0}}/>
                <span style={{fontSize:'13px',color:'#555',lineHeight:'1.6'}}>Я даю согласие на обработку персональных данных в соответствии с ФЗ №152-ФЗ. <span style={{color:'#dc3545'}}>*</span></span>
              </label>
            </div>
            <button onClick={saveProfile} style={{...btnOrange,width:'100%',padding:'12px',fontSize:'16px'}}>✅ Сохранить</button>
            <button onClick={()=>setShowProfileForm(false)} style={{width:'100%',padding:'10px',marginTop:'10px',backgroundColor:'white',border:'1px solid #ddd',borderRadius:'6px',cursor:'pointer',color:'#666'}}>Заполню позже</button>
          </div>
        </div>
      );
    }

    const myWorks = piecework.filter(p => Number(p.staffId) === user.id);
    const myTotal = myWorks.reduce((sum, p) => sum + p.total, 0);
    const categories = [...new Set(pricelistItems.map(i => i.category))];

    return (
      <div style={{display:'flex',height:'100vh',backgroundColor:'#f0f2f5'}}>
        {showPhotoModal&&(
          <div onClick={()=>setShowPhotoModal(null)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.9)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:2000,cursor:'pointer'}}>
            <img src={showPhotoModal} alt="фото" style={{maxWidth:'90%',maxHeight:'90%',borderRadius:'8px'}}/>
          </div>
        )}
        <div style={{width:'220px',backgroundColor:'#1a1a2e',color:'white',padding:'20px 0',flexShrink:0,display:'flex',flexDirection:'column'}}>
          <h3 style={{textAlign:'center',color:'#ff6b00'}}>🏗️ СтройКа</h3>
          <div style={{textAlign:'center',marginBottom:'20px'}}>
            <span style={{backgroundColor:'#e83e8c',color:'white',padding:'2px 10px',borderRadius:'20px',fontSize:'12px'}}>мастер</span>
            <p style={{color:'#aaa',fontSize:'13px',margin:'5px 0 0'}}>{user.name}</p>
            {masterProfile?.specialization&&<p style={{color:'#ff6b00',fontSize:'12px',margin:'2px 0'}}>{masterProfile.specialization}</p>}
          </div>
          <div style={{padding:'15px 25px',backgroundColor:'#ff6b00',borderLeft:'4px solid white'}}>🔨 Мои работы</div>
          <div onClick={()=>setShowProfileForm(true)} style={{padding:'15px 25px',cursor:'pointer',color:'#aaa'}}>👤 Мой профиль</div>
          <div style={{marginTop:'auto'}}><div onClick={()=>setUser(null)} style={{padding:'15px 25px',cursor:'pointer',color:'#aaa'}}>🚪 Выйти</div></div>
        </div>
        <div style={{flex:1,padding:'30px',overflowY:'auto'}}>
          {!masterProfile?.profileCompleted&&(
            <div style={{backgroundColor:'#fff3cd',border:'1px solid #ffc107',padding:'15px',borderRadius:'10px',marginBottom:'20px'}}>
              <b>⚠️ Профиль не заполнен!</b>
              <button onClick={()=>setShowProfileForm(true)} style={{...btnOrange,marginLeft:'15px',padding:'6px 15px',fontSize:'14px'}}>Заполнить</button>
            </div>
          )}
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
            <h2 style={{color:'#333'}}>🔨 Мои работы</h2>
            <div style={{backgroundColor:'#28a745',color:'white',padding:'10px 20px',borderRadius:'10px',fontWeight:'bold'}}>Всего: {myTotal.toLocaleString()} руб.</div>
          </div>
          <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
            <h3 style={{marginBottom:'15px'}}>➕ Добавить работы</h3>
            <select value={masterProjectId} onChange={async e=>{
              const pid=e.target.value;
              setMasterProjectId(pid);
              setSelectedWorks({});
              const proj=projects.find(p=>p.id===Number(pid));
              if(proj&&proj.pricelistId) await loadPricelistItems(proj.pricelistId);
              else setPricelistItems([]);
            }} style={inputStyle}>
              <option value="">Выберите объект</option>
              {projects.filter(p=>p.status==='В работе').map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            {pricelistItems.length>0&&(
              <>
                <p style={{color:'#666',fontSize:'13px',marginBottom:'10px'}}>✅ Отметьте выполненные работы:</p>
                {categories.map(cat=>(
                  <div key={cat} style={{marginBottom:'15px'}}>
                    <div style={{color:'#ff6b00',fontSize:'12px',fontWeight:'bold',marginBottom:'8px',textTransform:'uppercase',borderBottom:'2px solid #ff6b00',paddingBottom:'4px'}}>{cat}</div>
                    {pricelistItems.filter(i=>i.category===cat).map(item=>{
                      const proj=projects.find(p=>p.id===Number(masterProjectId));
                      const pl=proj&&pricelists.find(p=>p.id===proj.pricelistId);
                      const price=item.price*(pl?pl.coefficient:1.0);
                      const isSelected=selectedWorks[item.id]!==undefined;
                      return (
                        <div key={item.id} style={{padding:'10px',marginBottom:'8px',borderRadius:'8px',border:`2px solid ${isSelected?'#ff6b00':'#eee'}`,backgroundColor:isSelected?'#fff5f0':'white'}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:isSelected?'8px':'0'}}>
                            <label style={{display:'flex',alignItems:'center',gap:'10px',cursor:'pointer',flex:1}}>
                              <input type="checkbox" checked={isSelected} onChange={e=>{
                                if(e.target.checked) setSelectedWorks(prev=>({...prev,[item.id]:{quantity:'',comment:'',photoUrl:''}}));
                                else{const updated={...selectedWorks};delete updated[item.id];setSelectedWorks(updated);}
                              }} style={{width:'18px',height:'18px',cursor:'pointer'}}/>
                              <span style={{fontWeight:isSelected?'bold':'normal'}}>{item.name}</span>
                            </label>
                            <span style={{color:'#ff6b00',fontWeight:'bold',fontSize:'14px'}}>{price.toLocaleString()} руб./{item.unit}</span>
                          </div>
                          {isSelected&&(
                            <div style={{paddingLeft:'28px'}}>
                              <div style={{display:'flex',gap:'10px',alignItems:'center'}}>
                                <input placeholder={`Количество (${item.unit})`} type="number" value={selectedWorks[item.id]?.quantity||''} onChange={e=>setSelectedWorks(prev=>({...prev,[item.id]:{...prev[item.id],quantity:e.target.value}}))} style={{...inputStyle,marginBottom:0,flex:1}}/>
                                {selectedWorks[item.id]?.quantity&&(
                                  <span style={{color:'#28a745',fontWeight:'bold',whiteSpace:'nowrap'}}>= {(Number(selectedWorks[item.id].quantity)*price).toLocaleString()} руб.</span>
                                )}
                              </div>
                              <input placeholder="Комментарий" value={selectedWorks[item.id]?.comment||''} onChange={e=>setSelectedWorks(prev=>({...prev,[item.id]:{...prev[item.id],comment:e.target.value}}))} style={{...inputStyle,marginTop:'8px',marginBottom:'8px'}}/>
                              <label style={{color:'#555',fontSize:'12px',fontWeight:'bold'}}>📸 Фото работы</label>
                              <input type="file" accept="image/*" onChange={async e=>{
                                if(e.target.files[0]){
                                  const url=await uploadPhoto(e.target.files[0]);
                                  setSelectedWorks(prev=>({...prev,[item.id]:{...prev[item.id],photoUrl:url}}));
                                }
                              }} style={{...inputStyle,padding:'6px',marginTop:'4px'}}/>
                              {selectedWorks[item.id]?.photoUrl&&<p style={{color:'#28a745',fontSize:'12px'}}>✅ Фото загружено</p>}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ))}
                {Object.keys(selectedWorks).length>0&&(
                  <div style={{backgroundColor:'#f0fff0',padding:'15px',borderRadius:'8px',marginBottom:'15px'}}>
                    <b>Итого: {Object.entries(selectedWorks).reduce((sum,[itemId,data])=>{
                      const item=pricelistItems.find(i=>i.id===Number(itemId));
                      const proj=projects.find(p=>p.id===Number(masterProjectId));
                      const pl=proj&&pricelists.find(p=>p.id===proj.pricelistId);
                      const price=item?item.price*(pl?pl.coefficient:1.0):0;
                      return sum+(Number(data.quantity)*price||0);
                    },0).toLocaleString()} руб.</b>
                    <p style={{color:'#666',fontSize:'13px',margin:'4px 0 0'}}>Выбрано работ: {Object.keys(selectedWorks).length}</p>
                  </div>
                )}
                <button onClick={addMasterWorks} style={btnOrange}>✅ Отправить все работы на проверку</button>
              </>
            )}
            {masterProjectId&&pricelistItems.length===0&&<p style={{color:'#999'}}>К этому объекту не привязан прайс-лист</p>}
          </div>
          <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
            <h3 style={{marginBottom:'15px'}}>📋 История работ</h3>
            {myWorks.length===0&&<p style={{color:'#999'}}>Работ пока нет</p>}
            {myWorks.map(w=>{
              const je=workJournal.find(j=>j.masterId===user.id&&j.description===w.description&&j.date===w.date);
              return (
                <div key={w.id} style={{padding:'15px',borderBottom:'1px solid #eee'}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                    <div style={{flex:1}}>
                      <b>{w.description}</b>
                      <p style={{color:'#666',margin:'4px 0',fontSize:'14px'}}>{w.quantity} {w.unit} × {w.pricePerUnit?.toLocaleString()} руб. | 🏗️ {w.project} | 📅 {w.date}</p>
                      {w.comment&&<p style={{color:'#999',margin:'4px 0',fontSize:'13px'}}>💬 {w.comment}</p>}
                      {w.photoUrl&&<img src={`${API}${w.photoUrl}`} alt="фото" onClick={()=>setShowPhotoModal(`${API}${w.photoUrl}`)} style={{width:'80px',height:'60px',objectFit:'cover',borderRadius:'6px',cursor:'pointer',marginTop:'6px'}}/>}
                      {je&&(
                        <div style={{marginTop:'6px'}}>
                          <span style={{fontSize:'12px',padding:'2px 8px',borderRadius:'10px',backgroundColor:je.status==='Подтверждено'?'#28a745':je.status==='Отклонено'?'#dc3545':'#ffc107',color:'white'}}>
                            {je.status==='Подтверждено'?'✅ Подтверждено':je.status==='Отклонено'?'❌ Отклонено':'⏳ На проверке'}
                          </span>
                          {je.status==='Отклонено'&&je.comment&&<p style={{color:'#dc3545',fontSize:'12px',margin:'4px 0'}}>Причина: {je.comment}</p>}
                        </div>
                      )}
                    </div>
                    <b style={{color:'#28a745',whiteSpace:'nowrap',marginLeft:'10px'}}>{w.total?.toLocaleString()} руб.</b>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  const allMenuItems = [
    {id:'dashboard',icon:'📊',label:'Главная'},
    {id:'analytics',icon:'📈',label:'Аналитика'},
    {id:'projects',icon:'📋',label:'Проекты'},
    {id:'clients',icon:'👥',label:'Клиенты'},
    {id:'warehouse',icon:'🏗️',label:'Склад'},
    {id:'staff',icon:'👷',label:'Сотрудники'},
    {id:'suppliers',icon:'🚚',label:'Поставщики'},
    {id:'journal',icon:'📔',label:'Журнал работ'},
    {id:'checklists',icon:'✅',label:'Чек-листы'},
    {id:'accounting',icon:'💰',label:'Бухгалтерия'},
    {id:'pricelists',icon:'💲',label:'Прайс-листы'},
    {id:'users',icon:'🔐',label:'Пользователи'},
  ];
  const menuItems = allMenuItems.filter(item => canAccess(item.id));
  const filteredUsers = users.filter(u => u.name.toLowerCase().includes(searchUser.toLowerCase()) || u.email.toLowerCase().includes(searchUser.toLowerCase()));

  return (
    <div style={{display:'flex',height:'100vh',backgroundColor:'#f0f2f5'}}>
      {showPhotoModal&&(
        <div onClick={()=>setShowPhotoModal(null)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.9)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:2000,cursor:'pointer'}}>
          <img src={showPhotoModal} alt="фото" style={{maxWidth:'90%',maxHeight:'90%',borderRadius:'8px'}}/>
        </div>
      )}
      {showAiModal&&(
        <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500}}>
          <div style={{backgroundColor:'white',padding:'30px',borderRadius:'10px',width:'450px',maxWidth:'90%'}}>
            {aiLoading?(
              <div style={{textAlign:'center',padding:'30px'}}>
                <div style={{fontSize:'40px',marginBottom:'15px'}}>🤖</div>
                <h3>ИИ анализирует...</h3>
              </div>
            ):aiResult&&(
              <div>
                <h3 style={{marginBottom:'15px'}}>{aiResult.title}</h3>
                <div style={{backgroundColor:'#f8f9fa',padding:'15px',borderRadius:'8px',marginBottom:'15px'}}>
                  <p style={{color:'#666',margin:0}}>{aiResult.content}</p>
                </div>
                <div style={{backgroundColor:'#fff3cd',padding:'12px',borderRadius:'8px',marginBottom:'15px',fontSize:'13px'}}>
                  <b>⚡ Для активации:</b><br/>1. Получите API ключ на console.anthropic.com<br/>2. Сообщите нам — подключим за 30 минут!
                </div>
                <button onClick={()=>{setShowAiModal(false);setAiResult(null);}} style={btnOrange}>Закрыть</button>
              </div>
            )}
          </div>
        </div>
      )}
      {rejectingEntry&&(
        <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500}}>
          <div style={{backgroundColor:'white',padding:'30px',borderRadius:'10px',width:'400px'}}>
            <h3 style={{marginBottom:'15px'}}>❌ Причина отклонения</h3>
            <p style={{color:'#666',marginBottom:'10px',fontSize:'14px'}}>{rejectingEntry.description} — {rejectingEntry.masterName}</p>
            <textarea placeholder="Укажите причину..." value={rejectComment} onChange={e=>setRejectComment(e.target.value)} style={{...inputStyle,height:'100px',resize:'vertical'}}/>
            <div style={{display:'flex',gap:'10px'}}>
              <button onClick={()=>rejectJournalEntry(rejectingEntry,rejectComment)} style={btnRed}>❌ Отклонить</button>
              <button onClick={()=>{setRejectingEntry(null);setRejectComment('');}} style={btnGray}>Отмена</button>
            </div>
          </div>
        </div>
      )}
      <div style={{width:'220px',backgroundColor:'#1a1a2e',color:'white',padding:'20px 0',flexShrink:0,display:'flex',flexDirection:'column',overflowY:'auto'}}>
        <h3 style={{textAlign:'center',color:'#ff6b00',marginBottom:'5px'}}>🏗️ СтройКа</h3>
        <div style={{textAlign:'center',marginBottom:'20px'}}>
          <span style={{backgroundColor:roleColor(user.role),color:'white',padding:'2px 10px',borderRadius:'20px',fontSize:'11px'}}>{ROLE_LABELS[user.role]||user.role}</span>
          <p style={{color:'#aaa',fontSize:'13px',margin:'5px 0 0'}}>{user.name}</p>
        </div>
        {menuItems.map(item=>(
          <div key={item.id} onClick={()=>navigateTo(item.id)}
            style={{padding:'15px 25px',cursor:'pointer',backgroundColor:activePage===item.id?'#ff6b00':'transparent',borderLeft:activePage===item.id?'4px solid white':'4px solid transparent'}}>
            {item.icon} {item.label}
            {item.id==='warehouse'&&lowStockMaterials.length>0&&<span style={{marginLeft:'8px',backgroundColor:'#dc3545',color:'white',borderRadius:'50%',padding:'1px 6px',fontSize:'12px'}}>{lowStockMaterials.length}</span>}
            {item.id==='journal'&&pendingJournal>0&&<span style={{marginLeft:'8px',backgroundColor:'#ffc107',color:'white',borderRadius:'50%',padding:'1px 6px',fontSize:'12px'}}>{pendingJournal}</span>}
          </div>
        ))}
        <div style={{marginTop:'auto'}}>
          <div onClick={()=>setUser(null)} style={{padding:'15px 25px',cursor:'pointer',color:'#aaa'}}>🚪 Выйти</div>
        </div>
      </div>
      <div style={{flex:1,padding:'30px',overflowY:'auto'}}>

        {activePage==='dashboard'&&(
          <div>
            <h2 style={{color:'#333',marginBottom:'20px'}}>📊 Главная</h2>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(160px, 1fr))',gap:'20px',marginBottom:'30px'}}>
              {[
                {label:'Проектов',value:projects.length,icon:'📋',color:'#ff6b00',page:'projects'},
                {label:'Клиентов',value:clients.length,icon:'👥',color:'#007bff',page:'clients'},
                {label:'Материалов',value:materials.length,icon:'🏗️',color:'#28a745',page:'warehouse'},
                {label:'Сотрудников',value:staff.length,icon:'👷',color:'#6c757d',page:'staff'},
                {label:'Поставщиков',value:suppliers.length,icon:'🚚',color:'#8e44ad',page:'suppliers'},
                {label:'Мастеров',value:masterProfiles.length,icon:'🔨',color:'#e83e8c',page:'accounting'},
              ].filter(card=>canAccess(card.page)).map(card=>(
                <div key={card.label} onClick={()=>navigateTo(card.page)}
                  style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)',borderTop:`4px solid ${card.color}`,cursor:'pointer',transition:'box-shadow 0.2s'}}>
                  <div style={{fontSize:'25px',marginBottom:'8px'}}>{card.icon}</div>
                  <div style={{fontSize:'28px',fontWeight:'bold',color:card.color}}>{card.value}</div>
                  <div style={{color:'#666',fontSize:'14px'}}>{card.label}</div>
                  <div style={{color:card.color,fontSize:'12px',marginTop:'4px'}}>→ Перейти</div>
                </div>
              ))}
            </div>
            {isFinanceRole()&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)',marginBottom:'20px'}}>
                <h3 style={{marginBottom:'15px'}}>💰 Финансовая сводка</h3>
                {projects.map(p=>{
                  const matCost=projectMaterialCost(p.name);
                  const labCost=projectLaborCost(p.name);
                  const remaining=p.budget-matCost-labCost;
                  const pct=p.budget>0?Math.min(100,Math.round(((matCost+labCost)/p.budget)*100)):0;
                  return (
                    <div key={p.id} style={{marginBottom:'15px',paddingBottom:'15px',borderBottom:'1px solid #eee'}}>
                      <div style={{display:'flex',justifyContent:'space-between',marginBottom:'5px'}}>
                        <b>{p.name}</b>
                        <span style={{color:remaining>=0?'#28a745':'#dc3545',fontWeight:'bold'}}>{remaining>=0?`✅ ${remaining.toLocaleString()}`:`⚠️ -${Math.abs(remaining).toLocaleString()}`} руб.</span>
                      </div>
                      <div style={{display:'flex',gap:'15px',fontSize:'13px',color:'#666',marginBottom:'6px'}}>
                        <span>📦 {matCost.toLocaleString()}</span><span>👷 {labCost.toLocaleString()}</span><span>💰 {p.budget.toLocaleString()}</span>
                      </div>
                      <div style={{backgroundColor:'#f0f2f5',borderRadius:'10px',height:'8px'}}>
                        <div style={{backgroundColor:pct>90?'#dc3545':'#ff6b00',width:`${pct}%`,height:'8px',borderRadius:'10px'}}/>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)',marginBottom:'20px'}}>
              <h3 style={{marginBottom:'15px'}}>📋 Прогресс проектов</h3>
              {projects.filter(p=>p.status==='В работе').map(p=>(
                <div key={p.id} style={{marginBottom:'15px',cursor:'pointer'}} onClick={()=>navigateTo('projects')}>
                  <div style={{display:'flex',justifyContent:'space-between',marginBottom:'5px'}}><span>{p.name}</span><span style={{color:'#ff6b00',fontWeight:'bold'}}>{p.progress}%</span></div>
                  <div style={{backgroundColor:'#f0f2f5',borderRadius:'10px',height:'10px'}}>
                    <div style={{backgroundColor:'#ff6b00',width:`${p.progress}%`,height:'10px',borderRadius:'10px'}}/>
                  </div>
                </div>
              ))}
            </div>
            {isFinanceRole()&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                <h3 style={{marginBottom:'15px'}}>📊 Статьи затрат</h3>
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(140px, 1fr))',gap:'10px'}}>
                  {EXPENSE_CATEGORIES.map(cat=>{
                    const total=expenses.filter(e=>e.category===cat.id).reduce((sum,e)=>sum+Number(e.amount),0);
                    return (
                      <div key={cat.id} style={{backgroundColor:'#f8f9fa',padding:'12px',borderRadius:'8px',borderLeft:`4px solid ${cat.color}`}}>
                        <div style={{fontSize:'13px',color:'#666'}}>{cat.label}</div>
                        <div style={{fontSize:'16px',fontWeight:'bold',color:cat.color}}>{total.toLocaleString()} руб.</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {activePage==='analytics'&&(
          <div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <h2 style={{color:'#333'}}>📈 Аналитика</h2>
              <button onClick={()=>runAI('forecast')} style={{...btnBlue,fontSize:'13px'}}>🤖 Прогноз перерасхода</button>
            </div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'20px',marginBottom:'20px'}}>
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                <h3 style={{marginBottom:'15px'}}>💰 План / Факт</h3>
                {projects.map(p=>{
                  const fact=projectMaterialCost(p.name)+projectLaborCost(p.name);
                  const pct=p.budget>0?Math.min(100,Math.round((fact/p.budget)*100)):0;
                  return (
                    <div key={p.id} style={{marginBottom:'15px',paddingBottom:'15px',borderBottom:'1px solid #eee'}}>
                      <div style={{display:'flex',justifyContent:'space-between',marginBottom:'5px'}}>
                        <b>{p.name}</b><span style={{color:pct>90?'#dc3545':'#28a745',fontWeight:'bold'}}>{pct}%</span>
                      </div>
                      <div style={{display:'flex',gap:'10px',fontSize:'13px',color:'#666',marginBottom:'6px'}}>
                        <span>📋 {p.budget.toLocaleString()}</span><span>✅ {fact.toLocaleString()}</span>
                      </div>
                      <div style={{backgroundColor:'#f0f2f5',borderRadius:'6px',height:'8px'}}>
                        <div style={{backgroundColor:pct>90?'#dc3545':pct>70?'#ffc107':'#28a745',width:`${pct}%`,height:'8px',borderRadius:'6px'}}/>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                <h3 style={{marginBottom:'15px'}}>👷 Топ мастеров</h3>
                {[...masterProfiles].sort((a,b)=>{
                  const aT=workJournal.filter(j=>j.masterId===a.userId&&j.status==='Подтверждено').reduce((s,w)=>s+w.total,0);
                  const bT=workJournal.filter(j=>j.masterId===b.userId&&j.status==='Подтверждено').reduce((s,w)=>s+w.total,0);
                  return bT-aT;
                }).map((mp,idx)=>{
                  const works=workJournal.filter(j=>j.masterId===mp.userId&&j.status==='Подтверждено');
                  const total=works.reduce((s,w)=>s+w.total,0);
                  return (
                    <div key={mp.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'10px 0',borderBottom:'1px solid #eee'}}>
                      <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                        <span>{idx===0?'🥇':idx===1?'🥈':idx===2?'🥉':`${idx+1}.`}</span>
                        <div><b>{mp.fullName}</b><p style={{color:'#666',fontSize:'13px',margin:'2px 0'}}>{mp.specialization} | {works.length} работ</p></div>
                      </div>
                      <b style={{color:'#28a745'}}>{total.toLocaleString()} руб.</b>
                    </div>
                  );
                })}
              </div>
            </div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'20px',marginBottom:'20px'}}>
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                <h3 style={{marginBottom:'15px'}}>📊 Статьи затрат</h3>
                {EXPENSE_CATEGORIES.map(cat=>{
                  const total=expenses.filter(e=>e.category===cat.id).reduce((sum,e)=>sum+Number(e.amount),0);
                  return (
                    <div key={cat.id} style={{display:'flex',justifyContent:'space-between',padding:'8px 0',borderBottom:'1px solid #eee'}}>
                      <span>{cat.label}</span><b style={{color:cat.color}}>{total.toLocaleString()} руб.</b>
                    </div>
                  );
                })}
              </div>
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                <h3 style={{marginBottom:'15px'}}>🚚 Рейтинг поставщиков</h3>
                {[...suppliers].sort((a,b)=>b.rating-a.rating).map(s=>(
                  <div key={s.id} style={{display:'flex',justifyContent:'space-between',padding:'8px 0',borderBottom:'1px solid #eee'}}>
                    <div><b>{s.name}</b><p style={{color:'#666',fontSize:'13px',margin:'2px 0'}}>{s.specialization}</p></div>
                    <div style={{textAlign:'right'}}>
                      <div style={{color:'#ff6b00',fontWeight:'bold'}}>⭐ {s.rating}</div>
                      <div style={{color:'#666',fontSize:'12px'}}>{supplyHistory.filter(h=>h.supplierId===s.id).length} поставок</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)',marginBottom:'20px'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <h3 style={{margin:0}}>📄 Анализ сметы (ИИ)</h3>
                <button onClick={()=>runAI('smeta')} style={{...btnBlue,fontSize:'13px'}}>🤖 Анализ ИИ</button>
              </div>
              <input type="file" accept=".pdf,.xlsx,.xls,.csv" onChange={e=>setSmetaFile(e.target.files[0])} style={{...inputStyle,padding:'8px'}}/>
              {smetaFile&&<p style={{color:'#28a745',fontSize:'13px'}}>📄 {smetaFile.name}</p>}
            </div>
            <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
              <h3 style={{marginBottom:'15px'}}>📊 Сводная таблица КС-2</h3>
              <table style={{width:'100%',borderCollapse:'collapse',fontSize:'13px'}}>
                <thead>
                  <tr style={{backgroundColor:'#f5f5f5'}}>
                    <th style={{padding:'10px',border:'1px solid #ddd',textAlign:'left'}}>Объект</th>
                    <th style={{padding:'10px',border:'1px solid #ddd'}}>Статус</th>
                    <th style={{padding:'10px',border:'1px solid #ddd'}}>Бюджет</th>
                    <th style={{padding:'10px',border:'1px solid #ddd'}}>Факт</th>
                    <th style={{padding:'10px',border:'1px solid #ddd'}}>Остаток</th>
                    <th style={{padding:'10px',border:'1px solid #ddd'}}>КС-2</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map(p=>{
                    const total=projectMaterialCost(p.name)+projectLaborCost(p.name);
                    const rem=p.budget-total;
                    return (
                      <tr key={p.id}>
                        <td style={{padding:'8px 10px',border:'1px solid #ddd'}}><b>{p.name}</b></td>
                        <td style={{padding:'8px 10px',border:'1px solid #ddd',textAlign:'center'}}><span style={{backgroundColor:statusColor(p.status),color:'white',padding:'2px 8px',borderRadius:'10px',fontSize:'12px'}}>{p.status}</span></td>
                        <td style={{padding:'8px 10px',border:'1px solid #ddd',textAlign:'right'}}>{p.budget.toLocaleString()}</td>
                        <td style={{padding:'8px 10px',border:'1px solid #ddd',textAlign:'right',fontWeight:'bold'}}>{total.toLocaleString()}</td>
                        <td style={{padding:'8px 10px',border:'1px solid #ddd',textAlign:'right',color:rem>=0?'#28a745':'#dc3545',fontWeight:'bold'}}>{rem.toLocaleString()}</td>
                        <td style={{padding:'8px 10px',border:'1px solid #ddd',textAlign:'center'}}><button onClick={()=>printKS2(p)} style={{...btnBlue,padding:'4px 10px',fontSize:'12px'}}>📄</button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activePage==='checklists'&&(
          <div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <h2 style={{color:'#333'}}>✅ Чек-листы</h2>
              <button onClick={()=>setShowForm(!showForm)} style={btnOrange}>+ Новый</button>
            </div>
            {showForm&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <input placeholder="Название" value={newChecklist.title} onChange={e=>setNewChecklist({...newChecklist,title:e.target.value})} style={inputStyle}/>
                <select value={newChecklist.project} onChange={e=>setNewChecklist({...newChecklist,project:e.target.value})} style={inputStyle}>
                  <option value="">Выберите объект</option>
                  {projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
                </select>
                <div style={{display:'flex',gap:'10px',marginBottom:'10px'}}>
                  <input placeholder="Добавить пункт" value={newChecklistItem} onChange={e=>setNewChecklistItem(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&newChecklistItem){setNewChecklist({...newChecklist,items:[...newChecklist.items,{text:newChecklistItem,checked:false}]});setNewChecklistItem('');}}} style={{...inputStyle,marginBottom:0,flex:1}}/>
                  <button onClick={()=>{if(newChecklistItem){setNewChecklist({...newChecklist,items:[...newChecklist.items,{text:newChecklistItem,checked:false}]});setNewChecklistItem('');}}} style={btnOrange}>+</button>
                </div>
                {newChecklist.items.map((item,i)=>(
                  <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'6px 10px',backgroundColor:'#f8f9fa',borderRadius:'6px',marginBottom:'5px'}}>
                    <span>• {item.text}</span>
                    <button onClick={()=>setNewChecklist({...newChecklist,items:newChecklist.items.filter((_,idx)=>idx!==i)})} style={{...btnRed,padding:'2px 8px',fontSize:'12px'}}>✕</button>
                  </div>
                ))}
                <button onClick={()=>{
                  if(!newChecklist.title){alert('Введите название');return;}
                  setChecklists([...checklists,{...newChecklist,id:Date.now(),createdBy:user.name,date:new Date().toISOString().split('T')[0]}]);
                  setNewChecklist({project:'',title:'',items:[]});
                  setShowForm(false);
                }} style={btnOrange}>Создать</button>
              </div>
            )}
            {checklists.length===0&&<p style={{color:'#999',textAlign:'center',padding:'40px'}}>Чек-листов пока нет</p>}
            {checklists.map(cl=>{
              const done=cl.items.filter(i=>i.checked).length;
              const total=cl.items.length;
              const pct=total>0?Math.round((done/total)*100):0;
              return (
                <div key={cl.id} style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'15px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px'}}>
                    <div>
                      <h3 style={{margin:0}}>{cl.title}</h3>
                      <p style={{color:'#666',margin:'4px 0',fontSize:'14px'}}>🏗️ {cl.project} | 👤 {cl.createdBy} | 📅 {cl.date}</p>
                    </div>
                    <span style={{backgroundColor:pct===100?'#28a745':'#ffc107',color:'white',padding:'4px 12px',borderRadius:'20px',fontSize:'13px'}}>{done}/{total}</span>
                  </div>
                  <div style={{backgroundColor:'#f0f2f5',borderRadius:'6px',height:'6px',marginBottom:'12px'}}>
                    <div style={{backgroundColor:pct===100?'#28a745':'#ff6b00',width:`${pct}%`,height:'6px',borderRadius:'6px'}}/>
                  </div>
                  {cl.items.map((item,i)=>(
                    <div key={i} onClick={()=>{
                      const updated=checklists.map(c=>c.id===cl.id?{...c,items:c.items.map((it,idx)=>idx===i?{...it,checked:!it.checked}:it)}:c);
                      setChecklists(updated);
                    }} style={{display:'flex',alignItems:'center',gap:'10px',padding:'8px',borderRadius:'6px',cursor:'pointer',backgroundColor:item.checked?'#f0fff0':'white',marginBottom:'4px',border:'1px solid #f0f0f0'}}>
                      <span style={{fontSize:'18px'}}>{item.checked?'✅':'⬜'}</span>
                      <span style={{color:item.checked?'#28a745':'#333',textDecoration:item.checked?'line-through':'none'}}>{item.text}</span>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}

        {activePage==='journal'&&(
          <div>
            <h2 style={{color:'#333',marginBottom:'20px'}}>📔 Журнал выполненных работ</h2>
            {pendingJournal>0&&<div style={{backgroundColor:'#fff3cd',border:'1px solid #ffc107',padding:'15px',borderRadius:'10px',marginBottom:'20px'}}><b>⏳ Ожидают: {pendingJournal}</b></div>}
            <div style={{display:'flex',gap:'10px',marginBottom:'20px',flexWrap:'wrap'}}>
              {['Все','На проверке','Подтверждено','Отклонено'].map(filter=>(
                <button key={filter} onClick={()=>setJournalFilter(filter==='Все'?'':filter)}
                  style={{padding:'8px 16px',borderRadius:'20px',border:'none',cursor:'pointer',backgroundColor:journalFilter===(filter==='Все'?'':filter)?'#ff6b00':'#f0f2f5',color:journalFilter===(filter==='Все'?'':filter)?'white':'#333'}}>
                  {filter}
                </button>
              ))}
            </div>
            {workJournal.filter(j=>!journalFilter||j.status===journalFilter).map(entry=>(
              <div key={entry.id} style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'15px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)',borderLeft:`4px solid ${entry.status==='Подтверждено'?'#28a745':entry.status==='Отклонено'?'#dc3545':'#ffc107'}`}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                  <div style={{flex:1}}>
                    <h3 style={{margin:0}}>{entry.description}</h3>
                    <p style={{color:'#e83e8c',margin:'4px 0',fontWeight:'bold',fontSize:'14px'}}>👷 {entry.masterName}</p>
                    <p style={{color:'#666',margin:'4px 0',fontSize:'14px'}}>🏗️ {entry.project} | {entry.quantity} {entry.unit} × {entry.pricePerUnit?.toLocaleString()} руб. | 📅 {entry.date}</p>
                    {entry.comment&&<p style={{color:entry.status==='Отклонено'?'#dc3545':'#999',margin:'4px 0',fontSize:'13px'}}>💬 {entry.comment}</p>}
                    {entry.confirmedBy&&<p style={{color:'#666',margin:'4px 0',fontSize:'13px'}}>✍️ {entry.confirmedBy} | {entry.confirmedAt}</p>}
                    {entry.photoUrl&&(
                      <img src={`${API}${entry.photoUrl}`} alt="фото" onClick={()=>setShowPhotoModal(`${API}${entry.photoUrl}`)}
                        style={{width:'100px',height:'75px',objectFit:'cover',borderRadius:'6px',cursor:'pointer',marginTop:'8px',border:'2px solid #eee'}}/>
                    )}
                  </div>
                  <div style={{display:'flex',flexDirection:'column',gap:'8px',alignItems:'flex-end',marginLeft:'15px'}}>
                    <b style={{color:'#28a745',fontSize:'16px'}}>{entry.total?.toLocaleString()} руб.</b>
                    <span style={{backgroundColor:entry.status==='Подтверждено'?'#28a745':entry.status==='Отклонено'?'#dc3545':'#ffc107',color:'white',padding:'4px 12px',borderRadius:'20px',fontSize:'13px'}}>{entry.status}</span>
                    {entry.status==='На проверке'&&(
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={()=>confirmJournalEntry(entry)} style={{...btnGreen,padding:'6px 12px',fontSize:'13px'}}>✅</button>
                        <button onClick={()=>setRejectingEntry(entry)} style={{...btnRed,padding:'6px 12px',fontSize:'13px'}}>❌</button>
                      </div>
                    )}
                    {entry.status==='Подтверждено'&&<button onClick={()=>printAct(entry)} style={{...btnBlue,padding:'6px 12px',fontSize:'13px'}}>🖨️ АОСР</button>}
                  </div>
                </div>
              </div>
            ))}
            {workJournal.filter(j=>!journalFilter||j.status===journalFilter).length===0&&<p style={{color:'#999',textAlign:'center',padding:'40px'}}>Записей нет</p>}
          </div>
        )}

        {activePage==='projects'&&(
          <div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <h2 style={{color:'#333'}}>📋 Проекты</h2>
              <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewProject({name:'',client:'',status:'Планирование',budget:'',deadline:'',progress:0,tasks:[],pricelistId:null});}} style={btnOrange}>+ Новый</button>
            </div>
            {showForm&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <input placeholder="Название" value={newProject.name} onChange={e=>setNewProject({...newProject,name:e.target.value})} style={inputStyle}/>
                <input placeholder="Клиент" value={newProject.client} onChange={e=>setNewProject({...newProject,client:e.target.value})} style={inputStyle}/>
                <input placeholder="Бюджет (руб)" type="number" value={newProject.budget} onChange={e=>setNewProject({...newProject,budget:e.target.value})} style={inputStyle}/>
                <input type="date" value={newProject.deadline} onChange={e=>setNewProject({...newProject,deadline:e.target.value})} style={inputStyle}/>
                <select value={newProject.status} onChange={e=>setNewProject({...newProject,status:e.target.value})} style={inputStyle}>
                  <option>Планирование</option><option>В работе</option><option>Завершён</option>
                </select>
                <select value={newProject.pricelistId||''} onChange={e=>setNewProject({...newProject,pricelistId:e.target.value?Number(e.target.value):null})} style={inputStyle}>
                  <option value="">Без прайс-листа</option>
                  {pricelists.map(pl=><option key={pl.id} value={pl.id}>{pl.name}</option>)}
                </select>
                <label style={{color:'#666',fontSize:'14px'}}>Прогресс: {newProject.progress}%</label>
                <input type="range" min="0" max="100" value={newProject.progress} onChange={e=>setNewProject({...newProject,progress:Number(e.target.value)})} style={{width:'100%',marginBottom:'10px'}}/>
                <button onClick={saveProject} style={btnOrange}>Сохранить</button>
              </div>
            )}
            {projects.map(p=>{
              const matCost=projectMaterialCost(p.name);
              const labCost=projectLaborCost(p.name);
              const remaining=p.budget-matCost-labCost;
              const pl=pricelists.find(pl=>pl.id===p.pricelistId);
              return (
                <div key={p.id} style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'15px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                    <h3 style={{margin:0,cursor:'pointer'}} onClick={()=>setExpandedProject(expandedProject===p.id?null:p.id)}>{p.name}</h3>
                    <div style={{display:'flex',gap:'8px',alignItems:'center'}}>
                      <span style={{backgroundColor:statusColor(p.status),color:'white',padding:'4px 12px',borderRadius:'20px',fontSize:'13px'}}>{p.status}</span>
                      <button onClick={()=>printKS2(p)} style={{...btnBlue,padding:'4px 10px',fontSize:'12px'}}>📄 КС-2</button>
                      <button onClick={()=>editProject(p)} style={btnGray}>✏️</button>
                      <button onClick={()=>deleteProject(p.id)} style={btnRed}>🗑️</button>
                    </div>
                  </div>
                  <p style={{color:'#666',margin:'8px 0',fontSize:'14px'}}>👤 {p.client} &nbsp;&nbsp; 📅 {p.deadline}</p>
                  {pl&&<p style={{color:'#007bff',margin:'4px 0',fontSize:'14px'}}>📋 {pl.name} (коэф. {pl.coefficient})</p>}
                  {isFinanceRole()&&(
                    <div style={{display:'flex',gap:'15px',fontSize:'14px',marginBottom:'8px'}}>
                      <span>💰 {p.budget.toLocaleString()}</span>
                      <span>📦 {matCost.toLocaleString()}</span>
                      <span>👷 {labCost.toLocaleString()}</span>
                      <span style={{color:remaining>=0?'#28a745':'#dc3545',fontWeight:'bold'}}>{remaining>=0?`✅ ${remaining.toLocaleString()}`:`⚠️ -${Math.abs(remaining).toLocaleString()}`} руб.</span>
                    </div>
                  )}
                  <div style={{backgroundColor:'#f0f2f5',borderRadius:'10px',height:'8px'}}>
                    <div style={{backgroundColor:'#ff6b00',width:`${p.progress}%`,height:'8px',borderRadius:'10px'}}/>
                  </div>
                  {expandedProject===p.id&&(
                    <div style={{marginTop:'15px',borderTop:'1px solid #eee',paddingTop:'15px'}}>
                      <h4 style={{marginBottom:'10px'}}>✅ Задачи</h4>
                      {(p.tasks||[]).map((task,i)=>(
                        <div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'6px 0',borderBottom:'1px solid #f5f5f5'}}>
                          <span>• {task}</span>
                          <button onClick={()=>removeTask(p,i)} style={{...btnRed,padding:'2px 8px',fontSize:'12px'}}>✕</button>
                        </div>
                      ))}
                      <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                        <input placeholder="Новая задача" value={newTask} onChange={e=>setNewTask(e.target.value)} onKeyDown={e=>e.key==='Enter'&&addTaskToProject(p)} style={{...inputStyle,marginBottom:0,flex:1}}/>
                        <button onClick={()=>addTaskToProject(p)} style={btnOrange}>+</button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {activePage==='clients'&&(
          <div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <h2 style={{color:'#333'}}>👥 Клиенты</h2>
              <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewClient({name:'',phone:'',email:'',status:'Активный',notes:'',deals:[]});}} style={btnOrange}>+ Новый</button>
            </div>
            {showForm&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <input placeholder="Имя / Компания" value={newClient.name} onChange={e=>setNewClient({...newClient,name:e.target.value})} style={inputStyle}/>
                <input placeholder="Телефон" value={newClient.phone} onChange={e=>setNewClient({...newClient,phone:e.target.value})} style={inputStyle}/>
                <input placeholder="Email" value={newClient.email} onChange={e=>setNewClient({...newClient,email:e.target.value})} style={inputStyle}/>
                <textarea placeholder="Заметки" value={newClient.notes} onChange={e=>setNewClient({...newClient,notes:e.target.value})} style={{...inputStyle,height:'80px',resize:'vertical'}}/>
                <select value={newClient.status} onChange={e=>setNewClient({...newClient,status:e.target.value})} style={inputStyle}>
                  <option>Активный</option><option>Завершён</option>
                </select>
                <button onClick={saveClient} style={btnOrange}>Сохранить</button>
              </div>
            )}
            {clients.map(c=>(
              <div key={c.id} style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'15px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <h3 style={{margin:0,cursor:'pointer'}} onClick={()=>setExpandedClient(expandedClient===c.id?null:c.id)}>{c.name}</h3>
                  <div style={{display:'flex',gap:'8px',alignItems:'center'}}>
                    <span style={{backgroundColor:statusColor(c.status),color:'white',padding:'4px 12px',borderRadius:'20px',fontSize:'13px'}}>{c.status}</span>
                    <button onClick={()=>editClient(c)} style={btnGray}>✏️</button>
                    <button onClick={()=>deleteClient(c.id)} style={btnRed}>🗑️</button>
                  </div>
                </div>
                <p style={{color:'#666',margin:'8px 0',fontSize:'14px'}}>📞 {c.phone} &nbsp;&nbsp; ✉️ {c.email}</p>
                {expandedClient===c.id&&c.notes&&<p style={{color:'#666',marginTop:'10px'}}>📝 {c.notes}</p>}
              </div>
            ))}
          </div>
        )}

        {activePage==='warehouse'&&(
          <div>
            {lowStockMaterials.length>0&&<div style={{backgroundColor:'#fff3cd',border:'1px solid #ffc107',padding:'15px',borderRadius:'10px',marginBottom:'20px'}}><b>⚠️ Заканчиваются:</b> {lowStockMaterials.map(m=>m.name).join(', ')}</div>}
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <h2 style={{color:'#333'}}>🏗️ Склад</h2>
              <div style={{display:'flex',gap:'10px'}}>
                <button onClick={()=>setShowHistory(!showHistory)} style={{...btnGray,padding:'10px 20px'}}>📊 История</button>
                <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewMaterial({name:'',unit:'шт',quantity:'',price:'',minQuantity:'',project:''});}} style={btnOrange}>+ Материал</button>
              </div>
            </div>
            {showHistory&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <h3 style={{marginBottom:'15px'}}>📊 История</h3>
                {history.map(h=>(
                  <div key={h.id} style={{display:'flex',justifyContent:'space-between',padding:'8px 0',borderBottom:'1px solid #eee',fontSize:'14px'}}>
                    <span>{h.date} — {h.material} ({h.project})</span>
                    <span style={{color:h.type==='приход'?'#28a745':'#dc3545',fontWeight:'bold'}}>{h.type==='приход'?'+':'-'}{h.quantity}</span>
                  </div>
                ))}
              </div>
            )}
            {showForm&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <h3 style={{marginBottom:'15px'}}>{editingItem?'Редактировать':'Новый материал'}</h3>
                <input placeholder="Название" value={newMaterial.name} onChange={e=>setNewMaterial({...newMaterial,name:e.target.value})} style={inputStyle}/>
                <input placeholder="Количество" type="number" value={newMaterial.quantity} onChange={e=>setNewMaterial({...newMaterial,quantity:e.target.value})} style={inputStyle}/>
                <input placeholder="Цена за единицу" type="number" value={newMaterial.price} onChange={e=>setNewMaterial({...newMaterial,price:e.target.value})} style={inputStyle}/>
                <input placeholder="Мин. остаток" type="number" value={newMaterial.minQuantity} onChange={e=>setNewMaterial({...newMaterial,minQuantity:e.target.value})} style={inputStyle}/>
                <select value={newMaterial.project} onChange={e=>setNewMaterial({...newMaterial,project:e.target.value})} style={inputStyle}>
                  <option value="">Выберите проект</option>
                  {projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
                </select>
                <select value={newMaterial.unit} onChange={e=>setNewMaterial({...newMaterial,unit:e.target.value})} style={inputStyle}>
                  <option>шт</option><option>мешок</option><option>м</option><option>м²</option><option>м³</option><option>кг</option><option>т</option>
                </select>
                <button onClick={saveMaterial} style={btnOrange}>Сохранить</button>
              </div>
            )}
            <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
              <h3 style={{marginBottom:'15px'}}>📦 Приход / Расход</h3>
              <select value={movement.id} onChange={e=>setMovement({...movement,id:e.target.value})} style={inputStyle}>
                <option value="">Выберите материал</option>
                {materials.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
              <select value={movement.type} onChange={e=>setMovement({...movement,type:e.target.value})} style={inputStyle}>
                <option value="приход">📥 Приход</option><option value="расход">📤 Расход</option>
              </select>
              <input placeholder="Количество" type="number" value={movement.quantity} onChange={e=>setMovement({...movement,quantity:e.target.value})} style={inputStyle}/>
              <select value={movement.project} onChange={e=>setMovement({...movement,project:e.target.value})} style={inputStyle}>
                <option value="">Выберите проект</option>
                {projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
              </select>
              {movement.type==='приход'&&(
                <div style={{marginBottom:'10px'}}>
                  <label style={{color:'#555',fontSize:'13px',fontWeight:'bold',display:'block',marginBottom:'5px'}}>📸 Фото накладной → бухгалтеру</label>
                  <input type="file" accept="image/*" onChange={async e=>{
                    if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);setMovement(prev=>({...prev,invoicePhoto:url}));}
                  }} style={{...inputStyle,padding:'8px'}}/>
                  {uploadingPhoto&&<p style={{color:'#ff6b00',fontSize:'13px'}}>⏳ Загрузка...</p>}
                  {movement.invoicePhoto&&(
                    <div style={{marginTop:'8px'}}>
                      <img src={`${API}${movement.invoicePhoto}`} alt="накладная" onClick={()=>setShowPhotoModal(`${API}${movement.invoicePhoto}`)} style={{width:'120px',height:'90px',objectFit:'cover',borderRadius:'6px',cursor:'pointer'}}/>
                      <p style={{color:'#28a745',fontSize:'13px'}}>✅ Фото загружено → бухгалтеру</p>
                      <button onClick={()=>runAI('invoice')} style={{...btnBlue,fontSize:'12px',padding:'4px 10px',marginTop:'4px'}}>🤖 Распознать ИИ</button>
                    </div>
                  )}
                </div>
              )}
              <button onClick={applyMovement} style={{...btnOrange,backgroundColor:'#28a745'}}>Применить</button>
            </div>
            <div style={{backgroundColor:'#f8f9fa',padding:'12px',borderRadius:'8px',marginBottom:'15px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
              <b>📦 Итого на складе:</b>
              <b style={{color:'#ff6b00',fontSize:'16px'}}>{materials.reduce((sum,m)=>sum+(m.price*m.quantity),0).toLocaleString()} руб.</b>
            </div>
            {materials.map(m=>(
              <div key={m.id} style={{backgroundColor:'white',padding:'15px',borderRadius:'10px',marginBottom:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <h3 style={{margin:0}}>{m.name}</h3>
                  <div style={{display:'flex',gap:'8px',alignItems:'center'}}>
                    <span style={{backgroundColor:stockColor(m),color:'white',padding:'4px 12px',borderRadius:'20px',fontSize:'13px'}}>{m.quantity} {m.unit}</span>
                    <button onClick={()=>{setEditingItem(m);setNewMaterial({...m,quantity:String(m.quantity),price:String(m.price)});setShowForm(true);}} style={btnGray}>✏️</button>
                    <button onClick={()=>deleteMaterial(m.id)} style={btnRed}>🗑️</button>
                  </div>
                </div>
                <div style={{display:'flex',gap:'20px',marginTop:'6px',fontSize:'14px',color:'#666'}}>
                  <span>💰 {m.price.toLocaleString()} руб./{m.unit}</span>
                  <span style={{color:'#ff6b00',fontWeight:'bold'}}>Итого: {(m.price*m.quantity).toLocaleString()} руб.</span>
                  {m.project&&<span>🏗️ {m.project}</span>}
                </div>
                {m.minQuantity>0&&m.quantity<m.minQuantity&&<p style={{color:'#ffc107',margin:'4px 0',fontSize:'13px'}}>⚠️ Ниже минимума</p>}
              </div>
            ))}
          </div>
        )}

        {activePage==='suppliers'&&(
          <div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <h2 style={{color:'#333'}}>🚚 Поставщики</h2>
              <div style={{display:'flex',gap:'10px'}}>
                <button onClick={()=>setShowSupplyHistory(!showSupplyHistory)} style={{...btnGray,padding:'10px 20px'}}>📦 История</button>
                <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);}} style={btnOrange}>+ Поставщик</button>
              </div>
            </div>
            {showSupplyHistory&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <h3 style={{marginBottom:'15px'}}>📦 История поставок</h3>
                {supplyHistory.map(d=>{
                  const sup=suppliers.find(s=>s.id===d.supplierId);
                  return (
                    <div key={d.id} style={{padding:'12px',borderBottom:'1px solid #eee'}}>
                      <div style={{display:'flex',justifyContent:'space-between'}}>
                        <div>
                          <b>{d.materialName}</b> — {d.quantity} {d.unit}
                          <p style={{color:'#666',margin:'2px 0',fontSize:'13px'}}>🚚 {sup?.name} | 🏗️ {d.project} | 💰 {d.totalPrice?.toLocaleString()} руб.</p>
                        </div>
                        <div style={{display:'flex',flexDirection:'column',gap:'5px',alignItems:'flex-end'}}>
                          <span style={{backgroundColor:d.status==='Доставлено'?'#28a745':'#ffc107',color:'white',padding:'2px 10px',borderRadius:'15px',fontSize:'12px'}}>{d.status}</span>
                          {d.status==='Ожидает поставки'&&(user.role==='прораб'||user.role==='кладовщик'||user.role==='директор')&&(
                            <button onClick={()=>confirmDelivery(d)} style={{...btnGreen,fontSize:'12px',padding:'4px 10px'}}>✅ Принять</button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <h3 style={{margin:0}}>📋 Заявки</h3>
                <button onClick={()=>{setShowForm(true);setEditingItem(null);setNewRequest({materialName:'',quantity:'',unit:'шт',project:'',notes:''});}} style={{...btnBlue,padding:'8px 16px'}}>+ Заявка</button>
              </div>
              {showForm&&!editingItem&&(
                <div style={{backgroundColor:'#f8f9fa',padding:'15px',borderRadius:'8px',marginBottom:'15px'}}>
                  <input placeholder="Материал" value={newRequest.materialName} onChange={e=>setNewRequest({...newRequest,materialName:e.target.value})} style={inputStyle}/>
                  <div style={{display:'flex',gap:'10px'}}>
                    <input placeholder="Количество" type="number" value={newRequest.quantity} onChange={e=>setNewRequest({...newRequest,quantity:e.target.value})} style={{...inputStyle,flex:1}}/>
                    <select value={newRequest.unit} onChange={e=>setNewRequest({...newRequest,unit:e.target.value})} style={{...inputStyle,flex:1}}>
                      <option>шт</option><option>мешок</option><option>м</option><option>м²</option><option>м³</option><option>кг</option><option>т</option>
                    </select>
                  </div>
                  <select value={newRequest.project} onChange={e=>setNewRequest({...newRequest,project:e.target.value})} style={inputStyle}>
                    <option value="">Выберите проект</option>
                    {projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
                  </select>
                  <button onClick={saveRequest} style={btnOrange}>Создать</button>
                </div>
              )}
              {supplyRequests.map(req=>{
                const reqOffers=supplierOffers.filter(o=>o.requestId===req.id);
                const bestOffer=reqOffers.reduce((best,o)=>!best||o.totalPrice<best.totalPrice?o:best,null);
                return (
                  <div key={req.id} style={{padding:'12px',borderBottom:'1px solid #eee',backgroundColor:req.status==='Утверждено'?'#f0fff0':req.status==='Отменена'?'#fff5f5':'white',borderRadius:'6px',marginBottom:'5px'}}>
                    <div style={{display:'flex',justifyContent:'space-between'}}>
                      <div>
                        <b>{req.materialName}</b> — {req.quantity} {req.unit} | 🏗️ {req.project}
                        <p style={{color:'#666',margin:'2px 0',fontSize:'13px'}}>👤 {req.createdBy} | 📅 {req.date}</p>
                      </div>
                      <div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap',justifyContent:'flex-end'}}>
                        <span style={{backgroundColor:req.status==='Утверждено'?'#28a745':req.status==='Отменена'?'#dc3545':'#007bff',color:'white',padding:'2px 10px',borderRadius:'15px',fontSize:'12px'}}>{req.status}</span>
                        {req.status!=='Отменена'&&req.status!=='Утверждено'&&<button onClick={()=>setShowOffers(showOffers===req.id?null:req.id)} style={{...btnGray,fontSize:'12px',padding:'4px 10px'}}>📊 ({reqOffers.length})</button>}
                        {req.status==='Новая'&&<button onClick={()=>cancelRequest(req.id)} style={{...btnRed,fontSize:'12px',padding:'4px 8px'}}>✕</button>}
                      </div>
                    </div>
                    {showOffers===req.id&&(
                      <div style={{marginTop:'10px',backgroundColor:'#f8f9fa',padding:'12px',borderRadius:'8px'}}>
                        {reqOffers.map(offer=>{
                          const sup=suppliers.find(s=>s.id===offer.supplierId);
                          const isBest=bestOffer&&offer.id===bestOffer.id;
                          return (
                            <div key={offer.id} style={{padding:'8px',marginBottom:'6px',borderRadius:'6px',backgroundColor:isBest?'#e8f5e9':'white',border:`1px solid ${isBest?'#28a745':'#eee'}`}}>
                              <div style={{display:'flex',justifyContent:'space-between'}}>
                                <div><b>{sup?.name}</b> {isBest&&<span style={{color:'#28a745',fontSize:'11px'}}>⭐ Лучшая</span>}
                                  <p style={{color:'#666',margin:'2px 0',fontSize:'12px'}}>💰 {offer.pricePerUnit?.toLocaleString()} руб/ед. | {offer.totalPrice?.toLocaleString()} руб. | {offer.deliveryDays} дн.</p>
                                </div>
                                <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                                  {offer.status==='Ожидает'&&(user.role==='директор'||user.role==='зам_директора')&&<button onClick={()=>approveOffer(offer)} style={{...btnGreen,fontSize:'12px',padding:'4px 10px'}}>✅</button>}
                                  <span style={{backgroundColor:offer.status==='Утверждено'?'#28a745':'#6c757d',color:'white',padding:'2px 8px',borderRadius:'10px',fontSize:'11px'}}>{offer.status}</span>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                        <div style={{marginTop:'8px',padding:'8px',backgroundColor:'white',borderRadius:'6px'}}>
                          <select value={newOffer.supplierId} onChange={e=>setNewOffer({...newOffer,supplierId:e.target.value})} style={{...inputStyle,marginBottom:'6px'}}>
                            <option value="">Поставщик</option>
                            {suppliers.filter(s=>s.status==='Активный').map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
                          </select>
                          <div style={{display:'flex',gap:'8px'}}>
                            <input placeholder="Цена/ед." type="number" value={newOffer.pricePerUnit} onChange={e=>setNewOffer({...newOffer,pricePerUnit:e.target.value})} style={{...inputStyle,flex:1,marginBottom:'6px'}}/>
                            <input placeholder="Дней" type="number" value={newOffer.deliveryDays} onChange={e=>setNewOffer({...newOffer,deliveryDays:e.target.value})} style={{...inputStyle,flex:1,marginBottom:'6px'}}/>
                          </div>
                          <div style={{display:'flex',gap:'8px'}}>
                            <button onClick={()=>saveOffer(req.id)} style={{...btnBlue,padding:'6px 14px',fontSize:'13px'}}>Добавить</button>
                            <button onClick={()=>runAI('kp')} style={{...btnBlue,padding:'6px 14px',fontSize:'13px',backgroundColor:'#8e44ad'}}>🤖 ИИ анализ КП</button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            {!showForm&&(
              <>
                <h3 style={{color:'#333',marginBottom:'15px'}}>🏢 База поставщиков</h3>
                {suppliers.map(s=>(
                  <div key={s.id} style={{backgroundColor:'white',padding:'15px',borderRadius:'10px',marginBottom:'10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                      <div><h3 style={{margin:0}}>{s.name}</h3><p style={{color:'#ff6b00',margin:'2px 0',fontSize:'13px'}}>{s.specialization}</p></div>
                      <div style={{display:'flex',gap:'8px',alignItems:'center'}}>
                        <span>⭐ {s.rating}</span>
                        <button onClick={()=>{setEditingItem(s);setNewSupplier({...s});setShowForm(true);}} style={btnGray}>✏️</button>
                        <button onClick={()=>deleteSupplier(s.id)} style={btnRed}>🗑️</button>
                      </div>
                    </div>
                    <p style={{color:'#666',margin:'4px 0',fontSize:'13px'}}>📞 {s.phone} | ✉️ {s.email}</p>
                  </div>
                ))}
              </>
            )}
            {showForm&&editingItem&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <h3 style={{marginBottom:'15px'}}>Редактировать поставщика</h3>
                <input placeholder="Название" value={newSupplier.name} onChange={e=>setNewSupplier({...newSupplier,name:e.target.value})} style={inputStyle}/>
                <input placeholder="Телефон" value={newSupplier.phone} onChange={e=>setNewSupplier({...newSupplier,phone:e.target.value})} style={inputStyle}/>
                <input placeholder="Email" value={newSupplier.email} onChange={e=>setNewSupplier({...newSupplier,email:e.target.value})} style={inputStyle}/>
                <input placeholder="Специализация" value={newSupplier.specialization} onChange={e=>setNewSupplier({...newSupplier,specialization:e.target.value})} style={inputStyle}/>
                <label style={{color:'#666',fontSize:'13px'}}>Рейтинг: {newSupplier.rating}</label>
                <input type="range" min="1" max="5" step="0.1" value={newSupplier.rating} onChange={e=>setNewSupplier({...newSupplier,rating:Number(e.target.value)})} style={{width:'100%',marginBottom:'10px'}}/>
                <button onClick={saveSupplier} style={btnOrange}>Сохранить</button>
              </div>
            )}
          </div>
        )}

        {activePage==='staff'&&(
          <div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <h2 style={{color:'#333'}}>👷 Сотрудники</h2>
              <div style={{display:'flex',gap:'10px'}}>
                <button onClick={()=>setShowPiecework(!showPiecework)} style={{...btnGray,padding:'10px 20px'}}>🔨 Сдельные</button>
                <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewStaff({name:'',role:'',phone:'',salary:'',project:'',payType:'оклад'});}} style={btnOrange}>+ Сотрудник</button>
              </div>
            </div>
            {showPiecework&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <h3 style={{marginBottom:'15px'}}>🔨 Сдельная зарплата</h3>
                <select value={newPiecework.staffId} onChange={e=>setNewPiecework({...newPiecework,staffId:e.target.value})} style={inputStyle}>
                  <option value="">Выберите сотрудника</option>
                  {staff.map(s=><option key={s.id} value={s.id}>{s.name} — {s.role}</option>)}
                </select>
                <input placeholder="Вид работы" value={newPiecework.description} onChange={e=>setNewPiecework({...newPiecework,description:e.target.value})} style={inputStyle}/>
                <input placeholder="Количество" type="number" value={newPiecework.quantity} onChange={e=>setNewPiecework({...newPiecework,quantity:e.target.value})} style={inputStyle}/>
                <input placeholder="Цена за единицу" type="number" value={newPiecework.pricePerUnit} onChange={e=>setNewPiecework({...newPiecework,pricePerUnit:e.target.value})} style={inputStyle}/>
                <select value={newPiecework.project} onChange={e=>setNewPiecework({...newPiecework,project:e.target.value})} style={inputStyle}>
                  <option value="">Выберите проект</option>
                  {projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
                </select>
                {newPiecework.quantity&&newPiecework.pricePerUnit&&<div style={{backgroundColor:'#f0f2f5',padding:'10px',borderRadius:'6px',marginBottom:'10px'}}><b>Итого: {(Number(newPiecework.quantity)*Number(newPiecework.pricePerUnit)).toLocaleString()} руб.</b></div>}
                <button onClick={addPiecework} style={btnOrange}>Начислить</button>
              </div>
            )}
            {showForm&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <h3 style={{marginBottom:'15px'}}>{editingItem?'Редактировать':'Новый сотрудник'}</h3>
                <input placeholder="Имя" value={newStaff.name} onChange={e=>setNewStaff({...newStaff,name:e.target.value})} style={inputStyle}/>
                <input placeholder="Должность" value={newStaff.role} onChange={e=>setNewStaff({...newStaff,role:e.target.value})} style={inputStyle}/>
                <input placeholder="Телефон" value={newStaff.phone} onChange={e=>setNewStaff({...newStaff,phone:e.target.value})} style={inputStyle}/>
                <select value={newStaff.payType} onChange={e=>setNewStaff({...newStaff,payType:e.target.value})} style={inputStyle}>
                  <option value="оклад">💼 Оклад</option><option value="сдельно">🔨 Сдельно</option>
                </select>
                {newStaff.payType==='оклад'&&<input placeholder="Оклад (руб/мес)" type="number" value={newStaff.salary} onChange={e=>setNewStaff({...newStaff,salary:e.target.value})} style={inputStyle}/>}
                <select value={newStaff.project} onChange={e=>setNewStaff({...newStaff,project:e.target.value})} style={inputStyle}>
                  <option value="">Выберите проект</option>
                  {projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
                </select>
                <button onClick={saveStaff} style={btnOrange}>Сохранить</button>
              </div>
            )}
            {staff.map(s=>(
              <div key={s.id} style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'15px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <div><h3 style={{margin:0}}>{s.name}</h3><p style={{color:'#ff6b00',margin:'4px 0',fontWeight:'bold'}}>{s.role}</p></div>
                  <div style={{display:'flex',gap:'8px'}}>
                    {s.payType==='оклад'&&<button onClick={async()=>{setSelectedStaff(s);await loadTimesheet(s.id);setShowTimesheet(true);}} style={btnOrange}>📅 Табель</button>}
                    <button onClick={()=>{setEditingItem(s);setNewStaff({...s,salary:String(s.salary)});setShowForm(true);}} style={btnGray}>✏️</button>
                    <button onClick={()=>deleteStaff(s.id)} style={btnRed}>🗑️</button>
                  </div>
                </div>
                <p style={{color:'#666',margin:'8px 0',fontSize:'14px'}}>📞 {s.phone} &nbsp;&nbsp; 🏗️ {s.project}</p>
                <p style={{color:'#28a745',margin:'4px 0',fontWeight:'bold',fontSize:'14px'}}>
                  {s.payType==='оклад'?`✅ Отработано: ${workedDays(s.id)} дн. | К выплате: ${calcSalary(s).toLocaleString()} руб.`:`✅ Начислено: ${staffPieceworkTotal(s.id).toLocaleString()} руб.`}
                </p>
              </div>
            ))}
            {showTimesheet&&selectedStaff&&(
              <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1000}}>
                <div style={{backgroundColor:'white',padding:'30px',borderRadius:'10px',width:'600px',maxWidth:'90%'}}>
                  <h3 style={{marginBottom:'15px'}}>📅 Табель — {selectedStaff.name}</h3>
                  <div style={{display:'flex',flexWrap:'wrap',gap:'8px',marginBottom:'20px'}}>
                    {daysInMonth.map(day=>{
                      const worked=timesheet[`${selectedStaff.id}-${day}`];
                      return <div key={day} onClick={()=>toggleDay(selectedStaff.id,day)} style={{width:'40px',height:'40px',display:'flex',alignItems:'center',justifyContent:'center',borderRadius:'6px',cursor:'pointer',backgroundColor:worked?'#28a745':'#f0f2f5',color:worked?'white':'#333',fontWeight:'bold'}}>{day}</div>;
                    })}
                  </div>
                  <p style={{marginBottom:'15px'}}><b>Отработано: {workedDays(selectedStaff.id)} дней | К выплате: {calcSalary(selectedStaff).toLocaleString()} руб.</b></p>
                  <button onClick={()=>setShowTimesheet(false)} style={btnOrange}>Закрыть</button>
                </div>
              </div>
            )}
          </div>
        )}

        {activePage==='accounting'&&(
          <div>
            <h2 style={{color:'#333',marginBottom:'20px'}}>💰 Бухгалтерия</h2>
            <div style={{display:'flex',gap:'10px',marginBottom:'20px',flexWrap:'wrap'}}>
              {['contracts','acts','masters','invoices'].map(tab=>(
                <button key={tab} onClick={()=>setAccountingTab(tab)}
                  style={{padding:'10px 20px',borderRadius:'8px',border:'none',cursor:'pointer',backgroundColor:accountingTab===tab?'#ff6b00':'#f0f2f5',color:accountingTab===tab?'white':'#333',fontWeight:'bold'}}>
                  {tab==='contracts'?'📄 Договоры':tab==='acts'?'📋 Акты':tab==='masters'?'👷 Мастера':'📸 Накладные'}
                </button>
              ))}
            </div>
            {accountingTab==='invoices'&&(
              <div>
                <h3 style={{marginBottom:'15px'}}>📸 Накладные от склада</h3>
                {expenses.filter(e=>e.invoicePhoto).length===0&&<p style={{color:'#999'}}>Накладных пока нет</p>}
                {expenses.filter(e=>e.invoicePhoto).map(exp=>(
                  <div key={exp.id} style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'15px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                    <div style={{display:'flex',gap:'20px',alignItems:'flex-start'}}>
                      <img src={`${API}${exp.invoicePhoto}`} alt="накладная" onClick={()=>setShowPhotoModal(`${API}${exp.invoicePhoto}`)} style={{width:'120px',height:'90px',objectFit:'cover',borderRadius:'8px',cursor:'pointer',border:'2px solid #eee'}}/>
                      <div style={{flex:1}}>
                        <h3 style={{margin:0}}>{exp.description}</h3>
                        <p style={{color:'#666',margin:'4px 0',fontSize:'14px'}}>🏗️ {exp.project} | 📅 {exp.date} | 👤 {exp.addedBy}</p>
                        {exp.amount>0&&<p style={{color:'#28a745',fontWeight:'bold',fontSize:'16px',margin:'4px 0'}}>{Number(exp.amount).toLocaleString()} руб.</p>}
                        <span style={{backgroundColor:exp.status==='Подтверждено'?'#28a745':'#ffc107',color:'white',padding:'2px 10px',borderRadius:'15px',fontSize:'12px'}}>{exp.status}</span>
                      </div>
                      {exp.status!=='Подтверждено'&&(
                        <div style={{display:'flex',flexDirection:'column',gap:'8px',minWidth:'180px'}}>
                          <input placeholder="Сумма накладной" type="number" style={inputStyle} defaultValue={exp.amount} onBlur={e=>setExpenses(prev=>prev.map(ex=>ex.id===exp.id?{...ex,amount:e.target.value}:ex))}/>
                          <select style={inputStyle} value={exp.category} onChange={e=>setExpenses(prev=>prev.map(ex=>ex.id===exp.id?{...ex,category:e.target.value}:ex))}>
                            {EXPENSE_CATEGORIES.map(cat=><option key={cat.id} value={cat.id}>{cat.label}</option>)}
                          </select>
                          <button onClick={()=>setExpenses(prev=>prev.map(ex=>ex.id===exp.id?{...ex,status:'Подтверждено'}:ex))} style={btnGreen}>✅ Подтвердить</button>
                          <button onClick={()=>runAI('invoice')} style={{...btnBlue,fontSize:'12px',padding:'6px 10px'}}>🤖 Распознать ИИ</button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {accountingTab==='masters'&&(
              <div>
                <h3 style={{marginBottom:'15px'}}>👷 Профили мастеров</h3>
                {masterProfiles.map(mp=>{
                  const confirmedWorks=workJournal.filter(j=>j.masterId===mp.userId&&j.status==='Подтверждено');
                  const totalEarned=confirmedWorks.reduce((sum,w)=>sum+w.total,0);
                  return (
                    <div key={mp.id} style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'15px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                        <div>
                          <h3 style={{margin:0}}>{mp.fullName}</h3>
                          <p style={{color:'#ff6b00',margin:'4px 0',fontSize:'14px'}}>{mp.specialization} | {mp.contractType}</p>
                          <p style={{color:'#666',margin:'4px 0',fontSize:'14px'}}>ИНН: {mp.inn} | 🏦 {mp.bankName} | {mp.bankAccount}</p>
                        </div>
                        <div style={{textAlign:'right'}}>
                          <p style={{color:'#28a745',fontWeight:'bold',fontSize:'18px',margin:0}}>{totalEarned.toLocaleString()} руб.</p>
                          <p style={{color:'#666',fontSize:'13px',margin:'4px 0'}}>Работ: {confirmedWorks.length}</p>
                        </div>
                      </div>
                      <div style={{marginTop:'10px',borderTop:'1px solid #eee',paddingTop:'10px'}}>
                        {confirmedWorks.slice(0,3).map(w=>(
                          <div key={w.id} style={{display:'flex',justifyContent:'space-between',fontSize:'13px',padding:'4px 0',color:'#666'}}>
                            <span>📅 {w.date} — {w.description} ({w.quantity} {w.unit})</span>
                            <span style={{color:'#28a745',fontWeight:'bold'}}>{w.total?.toLocaleString()} руб.</span>
                          </div>
                        ))}
                        {confirmedWorks.length>3&&<p style={{color:'#999',fontSize:'12px',margin:'4px 0'}}>...ещё {confirmedWorks.length-3} работ</p>}
                        <button onClick={()=>{
                          const w=window.open('','_blank');
                          w.document.write(`<html><head><title>Акт мастера</title><style>body{font-family:Arial,sans-serif;padding:40px;font-size:13px}h2{text-align:center}table{width:100%;border-collapse:collapse;margin:15px 0}td,th{border:1px solid #333;padding:7px}th{background:#f5f5f5}.sign{margin-top:50px;display:flex;justify-content:space-between}.sign-block{width:45%;text-align:center}.sign-line{border-top:1px solid #333;margin-top:35px;padding-top:4px;font-size:11px}</style></head><body>
                          <h2>АКТ ВЫПОЛНЕННЫХ РАБОТ</h2>
                          <p><b>Мастер:</b> ${mp.fullName} | ИНН: ${mp.inn}</p>
                          <p><b>Банк:</b> ${mp.bankName} | Счёт: ${mp.bankAccount}</p>
                          <table><tr><th>№</th><th>Дата</th><th>Работа</th><th>Объект</th><th>Ед.</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>
                          ${confirmedWorks.map((w,i)=>`<tr><td>${i+1}</td><td>${w.date}</td><td>${w.description}</td><td>${w.project}</td><td>${w.unit}</td><td>${w.quantity}</td><td>${w.pricePerUnit?.toLocaleString()}</td><td>${w.total?.toLocaleString()}</td></tr>`).join('')}
                          <tr style="background:#f5f5f5"><td colspan="7"><b>ИТОГО:</b></td><td><b>${totalEarned.toLocaleString()} руб.</b></td></tr></table>
                          <div class="sign">
                          <div class="sign-block"><div class="sign-line">Заказчик<br>___________</div></div>
                          <div class="sign-block"><div class="sign-line">Исполнитель<br>${mp.fullName}</div></div>
                          </div></body></html>`);
                          w.document.close();w.print();
                        }} style={{...btnBlue,fontSize:'12px',padding:'6px 12px',marginTop:'8px'}}>🖨️ Печать акта</button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {accountingTab==='contracts'&&(
              <div>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                  <h3 style={{margin:0}}>📄 Договоры</h3>
                  <button onClick={()=>setShowForm(!showForm)} style={btnOrange}>+ Новый</button>
                </div>
                {showForm&&(
                  <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                    <select value={newContract.masterId} onChange={e=>{const mp=masterProfiles.find(p=>p.userId===Number(e.target.value));setNewContract({...newContract,masterId:e.target.value,masterName:mp?.fullName||'',contractType:mp?.contractType||'ГПХ'});}} style={inputStyle}>
                      <option value="">Выберите мастера</option>
                      {masterProfiles.map(mp=><option key={mp.id} value={mp.userId}>{mp.fullName}</option>)}
                    </select>
                    <input placeholder="Номер договора" value={newContract.contractNumber} onChange={e=>setNewContract({...newContract,contractNumber:e.target.value})} style={inputStyle}/>
                    <select value={newContract.project} onChange={e=>setNewContract({...newContract,project:e.target.value})} style={inputStyle}>
                      <option value="">Выберите объект</option>
                      {projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
                    </select>
                    <div style={{display:'flex',gap:'10px'}}>
                      <input type="date" value={newContract.startDate} onChange={e=>setNewContract({...newContract,startDate:e.target.value})} style={{...inputStyle,flex:1}}/>
                      <input type="date" value={newContract.endDate} onChange={e=>setNewContract({...newContract,endDate:e.target.value})} style={{...inputStyle,flex:1}}/>
                    </div>
                    <button onClick={createContract} style={btnOrange}>Создать</button>
                  </div>
                )}
                {contracts.map(ct=>{
                  const mp=masterProfiles.find(p=>p.userId===ct.masterId);
                  return (
                    <div key={ct.id} style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'15px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                      <div style={{display:'flex',justifyContent:'space-between'}}>
                        <div>
                          <h3 style={{margin:0}}>Договор № {ct.contractNumber}</h3>
                          <p style={{color:'#ff6b00',margin:'4px 0',fontWeight:'bold'}}>{ct.masterName} | {ct.contractType}</p>
                          <p style={{color:'#666',margin:'4px 0',fontSize:'14px'}}>🏗️ {ct.project} | 📅 {ct.startDate} — {ct.endDate}</p>
                        </div>
                        <div style={{display:'flex',flexDirection:'column',gap:'8px',alignItems:'flex-end'}}>
                          <span style={{backgroundColor:'#28a745',color:'white',padding:'4px 12px',borderRadius:'20px',fontSize:'13px'}}>{ct.status}</span>
                          {mp&&<button onClick={()=>printContract(mp,ct)} style={{...btnBlue,fontSize:'13px'}}>🖨️ Печать</button>}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {accountingTab==='acts'&&(
              <div>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                  <h3 style={{margin:0}}>📋 Промежуточные акты</h3>
                  <button onClick={()=>setShowForm(!showForm)} style={btnOrange}>+ Новый</button>
                </div>
                {showForm&&(
                  <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                    <select value={newAct.masterId} onChange={e=>{const mp=masterProfiles.find(p=>p.userId===Number(e.target.value));setNewAct({...newAct,masterId:e.target.value,masterName:mp?.fullName||''});}} style={inputStyle}>
                      <option value="">Выберите мастера</option>
                      {masterProfiles.map(mp=><option key={mp.id} value={mp.userId}>{mp.fullName}</option>)}
                    </select>
                    <select value={newAct.project} onChange={e=>setNewAct({...newAct,project:e.target.value})} style={inputStyle}>
                      <option value="">Выберите объект</option>
                      {projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
                    </select>
                    {newAct.masterId&&newAct.project&&(()=>{
                      const works=workJournal.filter(j=>j.masterId===Number(newAct.masterId)&&j.project===newAct.project&&j.status==='Подтверждено');
                      const total=works.reduce((sum,w)=>sum+w.total,0);
                      return <div style={{backgroundColor:'#f0fff0',padding:'10px',borderRadius:'6px',marginBottom:'10px',fontSize:'14px'}}><b>Работ: {works.length} | Сумма: {total.toLocaleString()} руб.</b></div>;
                    })()}
                    <div style={{display:'flex',gap:'10px'}}>
                      <input type="date" value={newAct.periodStart} onChange={e=>setNewAct({...newAct,periodStart:e.target.value})} style={{...inputStyle,flex:1}}/>
                      <input type="date" value={newAct.periodEnd} onChange={e=>setNewAct({...newAct,periodEnd:e.target.value})} style={{...inputStyle,flex:1}}/>
                    </div>
                    <button onClick={createInterimAct} style={btnOrange}>Создать</button>
                  </div>
                )}
                {interimActs.map(act=>(
                  <div key={act.id} style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'15px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                    <div style={{display:'flex',justifyContent:'space-between'}}>
                      <div>
                        <h3 style={{margin:0}}>Акт № {act.id}</h3>
                        <p style={{color:'#ff6b00',margin:'4px 0',fontWeight:'bold'}}>{act.masterName}</p>
                        <p style={{color:'#666',margin:'4px 0',fontSize:'14px'}}>🏗️ {act.project} | 📅 {act.periodStart} — {act.periodEnd}</p>
                      </div>
                      <div style={{display:'flex',flexDirection:'column',gap:'8px',alignItems:'flex-end'}}>
                        <b style={{color:'#28a745',fontSize:'18px'}}>{act.totalAmount?.toLocaleString()} руб.</b>
                        <span style={{backgroundColor:act.status==='Оплачен'?'#28a745':'#ffc107',color:'white',padding:'4px 12px',borderRadius:'20px',fontSize:'13px'}}>{act.status}</span>
                        <button onClick={()=>printInterimAct(act)} style={{...btnBlue,fontSize:'13px'}}>🖨️ Печать</button>
                        {act.status==='Новый'&&<button onClick={async()=>{await fetch(`${API}/interim-acts/${act.id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Оплачен',paidAt:new Date().toISOString().split('T')[0]})});await loadAll();}} style={{...btnGreen,fontSize:'13px'}}>💰 Оплачено</button>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activePage==='pricelists'&&(
          <div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <h2 style={{color:'#333'}}>💲 Прайс-листы</h2>
              <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewPricelist({name:'',description:'',coefficient:1.0});}} style={btnOrange}>+ Новый</button>
            </div>
            {showForm&&!selectedPricelist&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <input placeholder="Название" value={newPricelist.name} onChange={e=>setNewPricelist({...newPricelist,name:e.target.value})} style={inputStyle}/>
                <textarea placeholder="Описание" value={newPricelist.description} onChange={e=>setNewPricelist({...newPricelist,description:e.target.value})} style={{...inputStyle,height:'60px',resize:'vertical'}}/>
                <label style={{color:'#666',fontSize:'14px'}}>Коэффициент: {newPricelist.coefficient}</label>
                <input type="range" min="0.5" max="3" step="0.1" value={newPricelist.coefficient} onChange={e=>setNewPricelist({...newPricelist,coefficient:Number(e.target.value)})} style={{width:'100%',marginBottom:'10px'}}/>
                <button onClick={savePricelist} style={btnOrange}>Сохранить</button>
              </div>
            )}
            {selectedPricelist?(
              <div>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
                  <h3>{selectedPricelist.name} (коэф. {selectedPricelist.coefficient})</h3>
                  <button onClick={()=>{setSelectedPricelist(null);setPricelistItems([]);setEditingItem(null);}} style={btnGray}>← Назад</button>
                </div>
                <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                  <h4 style={{marginBottom:'15px'}}>➕ {editingItem?'Редактировать':'Добавить'}</h4>
                  <input placeholder="Название работы" value={newPlItem.name} onChange={e=>setNewPlItem({...newPlItem,name:e.target.value})} style={inputStyle}/>
                  <input placeholder="Категория (Каменные работы, Отделка...)" value={newPlItem.category} onChange={e=>setNewPlItem({...newPlItem,category:e.target.value})} style={inputStyle}/>
                  <input placeholder="Специализация" value={newPlItem.specialization} onChange={e=>setNewPlItem({...newPlItem,specialization:e.target.value})} style={inputStyle}/>
                  <input placeholder="Цена (руб)" type="number" value={newPlItem.price} onChange={e=>setNewPlItem({...newPlItem,price:e.target.value})} style={inputStyle}/>
                  <select value={newPlItem.unit} onChange={e=>setNewPlItem({...newPlItem,unit:e.target.value})} style={inputStyle}>
                    <option>м²</option><option>м³</option><option>м</option><option>шт</option><option>т</option><option>кг</option><option>точка</option><option>комплект</option>
                  </select>
                  <button onClick={savePlItem} style={btnOrange}>Сохранить</button>
                </div>
                {[...new Set(pricelistItems.map(i=>i.category))].map(cat=>(
                  <div key={cat} style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'15px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                    <h4 style={{color:'#ff6b00',marginBottom:'10px',borderBottom:'2px solid #ff6b00',paddingBottom:'6px'}}>{cat||'Без категории'}</h4>
                    {pricelistItems.filter(i=>i.category===cat).map(item=>(
                      <div key={item.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0',borderBottom:'1px solid #f5f5f5'}}>
                        <div style={{flex:1,marginRight:'10px'}}>
                          <b style={{fontSize:'14px'}}>{item.name}</b>
                          <span style={{color:'#666',fontSize:'13px'}}> — {item.unit}</span>
                          {item.specialization&&<span style={{marginLeft:'8px',backgroundColor:'#e9ecef',padding:'2px 8px',borderRadius:'10px',fontSize:'12px'}}>{item.specialization}</span>}
                        </div>
                        <div style={{display:'flex',gap:'8px',alignItems:'center',flexShrink:0}}>
                          <b style={{color:'#28a745',fontSize:'13px'}}>{item.price.toLocaleString()} руб.</b>
                          <b style={{color:'#007bff',fontSize:'13px'}}>→ {(item.price*selectedPricelist.coefficient).toLocaleString()}</b>
                          <button onClick={()=>{setEditingItem(item);setNewPlItem({name:item.name,unit:item.unit,price:String(item.price),category:item.category,specialization:item.specialization||''});}} style={btnGray}>✏️</button>
                          <button onClick={()=>deletePlItem(item.id)} style={btnRed}>🗑️</button>
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ):(
              pricelists.map(pl=>(
                <div key={pl.id} style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'15px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                    <div>
                      <h3 style={{margin:0}}>{pl.name}</h3>
                      {pl.description&&<p style={{color:'#666',margin:'4px 0',fontSize:'14px'}}>{pl.description}</p>}
                      <p style={{color:'#007bff',margin:'4px 0',fontSize:'14px'}}>Коэффициент: {pl.coefficient}</p>
                    </div>
                    <div style={{display:'flex',gap:'8px'}}>
                      <button onClick={async()=>{setSelectedPricelist(pl);await loadPricelistItems(pl.id);}} style={{...btnOrange,padding:'6px 12px'}}>📋 Открыть</button>
                      <button onClick={()=>copyPricelist(pl)} style={{...btnGray,padding:'6px 12px'}}>📄 Копия</button>
                      <button onClick={()=>{setEditingItem(pl);setNewPricelist({name:pl.name,description:pl.description,coefficient:pl.coefficient});setShowForm(true);}} style={btnGray}>✏️</button>
                      <button onClick={()=>deletePricelist(pl.id)} style={btnRed}>🗑️</button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activePage==='users'&&user.role==='директор'&&(
          <div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <h2 style={{color:'#333'}}>🔐 Пользователи</h2>
              <div style={{display:'flex',gap:'10px'}}>
                <button onClick={()=>setShowInvites(!showInvites)} style={{...btnGray,padding:'10px 20px'}}>🔑 Коды</button>
                <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewUser({name:'',email:'',password:'',role:'прораб'});}} style={btnOrange}>+ Пользователь</button>
              </div>
            </div>
            {showInvites&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <h3 style={{marginBottom:'15px'}}>🔑 Коды приглашений</h3>
                <div style={{display:'flex',gap:'10px',marginBottom:'15px'}}>
                  <select value={newInviteRole} onChange={e=>setNewInviteRole(e.target.value)} style={{...inputStyle,marginBottom:0,flex:1}}>
                    {Object.entries(ROLE_LABELS).map(([key,label])=><option key={key} value={key}>{label}</option>)}
                  </select>
                  <button onClick={createInviteCode} style={btnOrange}>Создать</button>
                </div>
                {inviteCodes.map(ic=>(
                  <div key={ic.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'10px',backgroundColor:ic.used?'#f8f9fa':'#f0fff0',borderRadius:'8px',marginBottom:'8px',border:`1px solid ${ic.used?'#dee2e6':'#28a745'}`}}>
                    <div>
                      <span style={{fontFamily:'monospace',fontSize:'18px',fontWeight:'bold',letterSpacing:'3px',color:ic.used?'#999':'#28a745'}}>{ic.code}</span>
                      <span style={{marginLeft:'15px',color:'#666',fontSize:'13px'}}>{ROLE_LABELS[ic.role]} | {ic.used?'✅ Использован':'⏳ Активен'}</span>
                    </div>
                    <button onClick={()=>deleteInviteCode(ic.id)} style={{...btnRed,padding:'4px 10px'}}>🗑️</button>
                  </div>
                ))}
              </div>
            )}
            {showForm&&(
              <div style={{backgroundColor:'white',padding:'20px',borderRadius:'10px',marginBottom:'20px',boxShadow:'0 2px 8px rgba(0,0,0,0.1)'}}>
                <input placeholder="Имя" value={newUser.name} onChange={e=>setNewUser({...newUser,name:e.target.value})} style={inputStyle}/>
                <input placeholder="Email" value={newUser.email} onChange={e=>setNewUser({...newUser,email:e.target.value})} style={inputStyle}/>
                <input placeholder={editingItem?"Пароль (пусто = без изменений)":"Пароль"} type="password" value={newUser.password} onChange={e=>setNewUser({...newUser,password:e.target.value})} style={inputStyle}/>
                <select value={newUser.role} onChange={e=>setNewUser({...newUser,role:e.target.value})} style={inputStyle}>
                  {Object.entries(ROLE_LABELS).map(([key,label])=><option key={key} value={key}>{label}</option>)}
                </select>
                <button onClick={saveUser} style={btnOrange}>Сохранить</button>
              </div>
            )}
            <input placeholder="🔍 Поиск..." value={searchUser} onChange={e=>setSearchUser(e.target.value)} style={{...inputStyle,marginBottom:'20px'}}/>
            {ROLE_GROUPS.map(group=>{
              const groupUsers=filteredUsers.filter(u=>group.roles.includes(u.role));
              if(groupUsers.length===0) return null;
              return (
                <div key={group.key} style={{marginBottom:'15px'}}>
                  <div onClick={()=>setExpandedGroup(expandedGroup===group.key?null:group.key)}
                    style={{backgroundColor:'#1a1a2e',color:'white',padding:'15px 20px',borderRadius:expandedGroup===group.key?'10px 10px 0 0':'10px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                    <span style={{fontWeight:'bold'}}>{group.label}</span>
                    <span style={{backgroundColor:'#ff6b00',color:'white',padding:'2px 10px',borderRadius:'20px',fontSize:'13px'}}>{groupUsers.length} чел.</span>
                  </div>
                  {expandedGroup===group.key&&(
                    <div style={{backgroundColor:'white',borderRadius:'0 0 10px 10px',boxShadow:'0 2px 8px rgba(0,0,0,0.08)'}}>
                      {groupUsers.map(u=>(
                        <div key={u.id} style={{padding:'15px 20px',borderBottom:'1px solid #f5f5f5',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                          <div><b>{u.name}</b><p style={{color:'#666',margin:'4px 0',fontSize:'14px'}}>✉️ {u.email}</p></div>
                          <div style={{display:'flex',gap:'8px',alignItems:'center'}}>
                            <span style={{backgroundColor:roleColor(u.role),color:'white',padding:'4px 12px',borderRadius:'20px',fontSize:'12px'}}>{ROLE_LABELS[u.role]}</span>
                            <button onClick={()=>{setEditingItem(u);setNewUser({...u,password:''});setShowForm(true);}} style={btnGray}>✏️</button>
                            <button onClick={()=>deleteUser(u.id)} style={btnRed}>🗑️</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

      </div>
    </div>
  );
}

export default App;