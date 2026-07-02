import { emptyStaffForm } from '../../utils/staffUtils';

export const createPersonnelActions = ({
  API,
  ROLE_LABELS,
  contracts,
  editingItem,
  expandedStaffId,
  findUserForStaff,
  masterRatings,
  newAct,
  newContract,
  newPiecework,
  newStaff,
  newStaffDoc,
  notify,
  readApiResult,
  refreshData,
  resolveContractPerformer,
  setEditingItem,
  setExpandedStaffId,
  setNewAct,
  setNewContract,
  setNewPiecework,
  setNewStaff,
  setNewStaffDoc,
  setMasterRatings,
  setSalaryPayments,
  setShowForm,
  setShowStaffDocForm,
  setStaffProfile,
  setStaffProfileLoading,
  setTimesheet,
  staffAccessRoles,
  staffPackageRequiredRoles,
  staffProjectRequiredRoles,
  upsertStaffAccess,
  user,
  users,
  workJournal,
}) => {
  const openStaffProfile = async (s) => {
    if (expandedStaffId === s.id) {
      setExpandedStaffId(null);
      setStaffProfile(null);
      return;
    }
    setExpandedStaffId(s.id);
    setStaffProfileLoading(true);
    try {
      const data = await fetch(API + '/staff/' + s.id + '/profile').then(r => r.json());
      setStaffProfile(data);
    } catch (e) {
      setStaffProfile(null);
    }
    setStaffProfileLoading(false);
  };

  const addStaffDoc = async (staffId) => {
    if (!newStaffDoc.title) return alert('Укажите название документа');
    await fetch(API + '/staff/' + staffId + '/documents', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...newStaffDoc, createdBy: user?.name || ''}),
    });
    const data = await fetch(API + '/staff/' + staffId + '/profile').then(r => r.json());
    setStaffProfile(data);
    setNewStaffDoc({docType: 'другое', title: '', fileUrl: '', signedAt: '', expiresAt: '', notes: ''});
    setShowStaffDocForm(false);
  };

  const paySalary = async (row, monthStr) => {
    const net = Math.round(Number(row.net || 0));
    if (net <= 0) {
      alert('Нечего выплачивать (сумма на руки 0)');
      return;
    }
    if (!window.confirm('Записать выплату ' + net.toLocaleString('ru-RU') + ' ₽ → ' + row.name + ' за ' + monthStr + '?')) return;
    await fetch(API + '/salary-payments', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        staffId: row.id,
        staffName: row.name,
        month: monthStr,
        amount: net,
        paidBy: user.name,
        paidDate: new Date().toISOString().split('T')[0],
      }),
    });
    const sp = await fetch(API + '/salary-payments').then(r => r.json());
    setSalaryPayments(Array.isArray(sp) ? sp : []);
    alert('💰 Выплата зафиксирована');
  };

  const ratemaster = (masterId, rating) => {
    const updated = {...masterRatings, [masterId]: rating};
    setMasterRatings(updated);
    localStorage.setItem('masterRatings', JSON.stringify(updated));
  };

  const saveStaff = async () => {
    if (!newStaff.name && !newStaff.lastName && !newStaff.firstName) {
      alert('Заполните хотя бы фамилию и имя');
      return;
    }
    const fullName = newStaff.name || [newStaff.lastName, newStaff.firstName, newStaff.middleName].filter(Boolean).join(' ');
    const accessEmail = (newStaff.email || '').trim().toLowerCase();
    const accessPassword = (newStaff.password || '').trim();
    const hasEmail = !!accessEmail;
    const hasPassword = !!accessPassword;
    const hasRole = !!newStaff.systemRole;
    const existingAccess = accessEmail
      ? (users || []).find(u => String(u.email || '').trim().toLowerCase() === accessEmail)
      : findUserForStaff(editingItem || newStaff);
    if ((hasEmail || hasPassword || hasRole) && !(hasEmail && hasRole && (hasPassword || existingAccess?.id))) {
      alert('Для нового доступа нужны системная роль + email + пароль. Для уже созданного доступа пароль можно оставить пустым.');
      return;
    }
    if (hasRole && !staffAccessRoles.includes(newStaff.systemRole)) {
      alert('Недопустимая системная роль: ' + newStaff.systemRole);
      return;
    }
    if (hasRole && staffProjectRequiredRoles.includes(newStaff.systemRole)) {
      const assignedProjects = Array.isArray(newStaff.assignedProjects) ? newStaff.assignedProjects.filter(Boolean) : [];
      if (!newStaff.project && assignedProjects.length === 0) {
        alert('Для роли ' + (ROLE_LABELS[newStaff.systemRole] || newStaff.systemRole) + ' нужно назначить объект.');
        return;
      }
    }
    if (hasRole && staffPackageRequiredRoles.includes(newStaff.systemRole)) {
      const assignedPackages = Array.isArray(newStaff.assignedPackages) ? newStaff.assignedPackages.filter(Boolean) : [];
      if (assignedPackages.length === 0) {
        alert('Для мастера, субподрядчика или бригадира нужно выбрать пакет работ/сметы. Так он увидит только свои работы.');
        return;
      }
    }
    const data = {...newStaff, name: fullName, salary: Number(newStaff.salary) || 0, role: newStaff.role || newStaff.systemRole || ''};
    const response = editingItem
      ? await readApiResult(await fetch(API + '/staff/' + editingItem.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)}))
      : await readApiResult(await fetch(API + '/staff', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)}));
    if (response?.access?.action === 'password_updated') alert('Сотрудник сохранён. Пароль и доступ обновлены: ' + response.access.email);
    else if (response?.access?.action === 'updated') alert('Сотрудник сохранён. Доступ обновлён: ' + response.access.email);
    else if (response?.access?.action === 'created') alert('Сотрудник сохранён. Доступ выдан: ' + response.access.email);
    await refreshData();
    setNewStaff(emptyStaffForm());
    setEditingItem(null);
    setShowForm(false);
  };

  const resetStaffAccessPassword = async (accessUser, staffRow) => {
    const password = prompt('Новый пароль для ' + (accessUser.email || staffRow.name) + ':');
    if (!password) return;
    const cleanPassword = password.trim();
    try {
      await upsertStaffAccess({
        staffRow,
        fullName: accessUser.name || staffRow.name,
        email: accessUser.email,
        password: cleanPassword,
        role: accessUser.role || 'мастер',
        projectName: accessUser.projectName || accessUser.project_name || staffRow.project || '',
        assignedProjects: accessUser.assignedProjects || accessUser.assigned_projects || [],
        assignedPackages: accessUser.assignedPackages || accessUser.assigned_packages || [],
      });
      await refreshData();
      alert('Пароль обновлён: ' + (accessUser.email || staffRow.name));
    } catch (e) {
      alert('Не удалось обновить пароль: ' + (e.message || e));
    }
  };

  const createStaffAccessFromPrompt = async (staffRow) => {
    const email = (prompt('Email для входа:') || '').trim().toLowerCase();
    if (!email) return;
    const password = (prompt('Пароль:') || '').trim();
    if (!password) return;
    const role = (prompt('Системная роль (директор/зам_директора/бухгалтер/прораб/мастер/субподрядчик/кладовщик/снабженец):', 'мастер') || '').trim();
    if (!role) return;
    if (!staffAccessRoles.includes(role)) {
      alert('Недопустимая роль. Используйте одну из: ' + staffAccessRoles.join(', '));
      return;
    }
    const assignedProjects = Array.isArray(staffRow.assignedProjects) ? staffRow.assignedProjects : [];
    const assignedPackages = Array.isArray(staffRow.assignedPackages) ? staffRow.assignedPackages : [];
    if (['прораб', 'главный_инженер', 'технадзор', 'стройконтроль', 'мастер', 'субподрядчик', 'бригадир'].includes(role) && !staffRow.project && assignedProjects.length === 0) {
      alert('Сначала откройте сотрудника через карандаш и назначьте объект. Без объекта доступ не выдаётся.');
      return;
    }
    if (['мастер', 'субподрядчик', 'бригадир'].includes(role) && assignedPackages.length === 0) {
      alert('Сначала откройте сотрудника через карандаш и выберите разделы сметы/виды работ. Без разделов мастер или субподрядчик увидит лишнее.');
      return;
    }
    try {
      const result = await upsertStaffAccess({staffRow, fullName: staffRow.name, email, password, role, projectName: staffRow.project || '', assignedProjects, assignedPackages});
      await refreshData();
      alert(result.updatedExisting ? 'Доступ обновлён: ' + email : 'Доступ выдан: ' + email);
    } catch (e) {
      alert('Не удалось выдать доступ: ' + (e.message || e));
    }
  };

  const deleteStaff = async (id) => {
    if (window.confirm('Отключить сотрудника? Запись останется в истории, доступ в систему будет выключен.')) {
      await fetch(API + '/staff/' + id, {method: 'DELETE'});
      await refreshData();
    }
  };

  const addPiecework = async () => {
    if (!newPiecework.staffId || !newPiecework.description || !newPiecework.quantity || !newPiecework.pricePerUnit) return;
    await fetch(API + '/piecework', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...newPiecework, total: Number(newPiecework.quantity) * Number(newPiecework.pricePerUnit), date: new Date().toISOString().split('T')[0]}),
    });
    await refreshData();
    setNewPiecework({staffId: '', description: '', unit: 'м2', quantity: '', pricePerUnit: '', project: ''});
  };

  const deletePiecework = async (id) => {
    if (window.confirm('Удалить?')) {
      await fetch(API + '/piecework/' + id, {method: 'DELETE'});
      await refreshData();
    }
  };

  const deleteContract = async (id) => {
    if (window.confirm('Удалить?')) {
      await fetch(API + '/contracts/' + id, {method: 'DELETE'});
      await refreshData();
    }
  };

  const deleteInterimAct = async (id) => {
    if (window.confirm('Удалить?')) {
      await fetch(API + '/interim-acts/' + id, {method: 'DELETE'});
      await refreshData();
    }
  };

  const toggleDay = async (staffId, day) => {
    await fetch(API + '/timesheet', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({staffId, day}),
    });
    setTimesheet(prev => ({...prev, [staffId + '-' + day]: !prev[staffId + '-' + day]}));
  };

  const createContract = async () => {
    if (!newContract.masterId || !newContract.contractNumber || !newContract.project) return;
    const performer = resolveContractPerformer(newContract);
    const payload = {
      ...newContract,
      masterId: Number(newContract.masterId),
      masterName: performer.fullName || newContract.masterName,
      contractType: newContract.contractType || performer.contractType || 'ГПХ',
    };
    await fetch(API + '/contracts', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    await refreshData();
    setNewContract({masterId: '', masterName: '', contractType: 'ГПХ', contractNumber: '', project: '', startDate: '', endDate: ''});
    setShowForm(false);
  };

  const createInterimAct = async () => {
    if (!newAct.masterId || !newAct.project || !newAct.periodStart || !newAct.periodEnd) return;
    const inActPeriod = (d) => {
      if (!d) return false;
      const day = String(d).split('T')[0];
      return day >= newAct.periodStart && day <= newAct.periodEnd;
    };
    const selectedPackage = String(newAct.workPackage || '').trim();
    const mw = workJournal.filter(j => j.masterId === Number(newAct.masterId) && j.project === newAct.project && j.status === 'Подтверждено' && inActPeriod(j.confirmedAt || j.date) && String(j.roomName || j.room_name || '').trim() && Number(j.executionTotal || 0) > 0 && (!selectedPackage || String(j.workPackage || j.work_package || 'Основная').trim() === selectedPackage));
    const contract = contracts.find(c => c.masterId === Number(newAct.masterId) && c.project === newAct.project);
    const groups = selectedPackage
      ? [[selectedPackage, mw]]
      : Object.entries(mw.reduce((acc, work) => {
        const pkg = String(work.workPackage || work.work_package || 'Основная').trim() || 'Основная';
        if (!acc[pkg]) acc[pkg] = [];
        acc[pkg].push(work);
        return acc;
      }, {}));
    if (!groups.length) {
      alert('Нет подтверждённых работ для акта за выбранный период');
      return;
    }
    let createdCount = 0;
    for (const [packageName, works] of groups) {
      const total = works.reduce((s, w) => s + Number(w.executionTotal || 0), 0);
      const workJournalIds = works.map(w => w.id).filter(Boolean);
      if (!workJournalIds.length || total <= 0) continue;
      const res = await fetch(API + '/interim-acts', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({...newAct, workPackage: packageName, masterId: Number(newAct.masterId), contractId: contract ? contract.id : null, totalAmount: total, paidAmount: 0, workJournalIds}),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.detail || data.error) {
        alert('Не удалось создать акт по разделу ' + packageName + ': ' + (data.detail || data.error || res.status));
        return;
      }
      createdCount += 1;
    }
    if (!createdCount) {
      alert('Нет работ с суммой для акта');
      return;
    }
    notify('Акт создан: ' + newAct.masterName + (createdCount > 1 ? ' · разделов ' + createdCount : ''), 'act');
    await refreshData();
    setNewAct({masterId: '', masterName: '', project: '', workPackage: '', periodStart: '', periodEnd: ''});
    setShowForm(false);
  };

  return {
    addPiecework,
    addStaffDoc,
    createContract,
    createInterimAct,
    createStaffAccessFromPrompt,
    deleteContract,
    deleteInterimAct,
    deletePiecework,
    deleteStaff,
    openStaffProfile,
    paySalary,
    ratemaster,
    resetStaffAccessPassword,
    saveStaff,
    toggleDay,
  };
};
