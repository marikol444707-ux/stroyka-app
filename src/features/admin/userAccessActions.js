import { createUserForm } from '../personnel/personnelInitialForms';

export const createUserAccessActions = ({
  API,
  editingItem,
  newInviteRole,
  newUser,
  refreshData,
  setEditingItem,
  setGeneratedInviteLink,
  setNewUser,
  setShowForm,
  supplierInviteForm,
  suppliers,
  user,
}) => {
  const saveUser = async () => {
    const cleanUser = {
      ...newUser,
      name: (newUser.name || '').trim(),
      email: (newUser.email || '').trim().toLowerCase(),
      password: (newUser.password || '').trim(),
    };
    if (!cleanUser.name || !cleanUser.email) return;
    if (!editingItem && !cleanUser.password) {
      alert('Укажите пароль');
      return;
    }
    if (editingItem) {
      const res = await fetch(API + '/users/' + editingItem.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(cleanUser)});
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        alert(e.detail || 'Не удалось сохранить пользователя');
        return;
      }
    } else {
      const res = await fetch(API + '/users', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(cleanUser)});
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        alert(e.detail || 'Не удалось создать пользователя');
        return;
      }
      if (cleanUser.role === 'поставщик') {
        const existing = suppliers.find(s => s.name === cleanUser.name || s.email === cleanUser.email);
        if (!existing) {
          await fetch(API + '/suppliers', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: cleanUser.name, email: cleanUser.email, phone: '', specialization: '', category: 'Прочее', rating: 5.0, status: 'Активный'})});
        }
      }
    }
    await refreshData();
    setNewUser(createUserForm());
    setEditingItem(null);
    setShowForm(false);
  };

  const toggleUserActive = async (u, nextActive) => {
    if (!nextActive && u.id === user.id) {
      alert('Нельзя отключить себя!');
      return;
    }
    const label = nextActive ? 'Включить доступ пользователю?' : 'Отключить доступ пользователю? История останется в системе.';
    if (!window.confirm(label)) return;
    if (nextActive) {
      await fetch(API + '/users/' + u.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
        name: u.name,
        email: u.email,
        password: '',
        role: u.role,
        projectId: u.projectId || '',
        projectName: u.projectName || u.project_name || '',
        assignedProjects: u.assignedProjects || u.assigned_projects || [],
        assignedPackages: u.assignedPackages || u.assigned_packages || [],
        active: true,
      })});
    } else {
      await fetch(API + '/users/' + u.id, {method: 'DELETE'});
    }
    await refreshData();
  };

  const deleteUser = async (u) => {
    await toggleUserActive(u, false);
  };

  const resetUserTwoFactor = async (u) => {
    if (!u?.id) return;
    const label = `Сбросить 2FA для ${u.name || u.email}? При следующем входе пользователь настроит код заново.`;
    if (!window.confirm(label)) return;
    const res = await fetch(API + '/users/' + u.id + '/2fa-reset', {method: 'POST'});
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      alert(data.detail || data.error || 'Не удалось сбросить 2FA');
      return;
    }
    await refreshData();
    alert('2FA сброшена');
  };

  const createInvite = async () => {
    await fetch(API + '/invite-codes', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({role: newInviteRole})});
    await refreshData();
  };

  const createSupplierInvite = async () => {
    const body = {
      role: 'поставщик',
      presetName: supplierInviteForm.presetName || '',
      presetCategory: supplierInviteForm.presetCategory || '',
      supplierId: supplierInviteForm.supplierId,
      expiresInDays: supplierInviteForm.expiresInDays || 14,
      createdBy: user?.name || '',
    };
    const r = await fetch(API + '/invite-codes', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const data = await r.json();
    if (data.code) {
      const link = window.location.origin + '/?invite=' + data.code;
      setGeneratedInviteLink({code: data.code, link, presetName: body.presetName, expiresAt: data.expires_at});
      await refreshData();
    } else {
      alert('Не удалось создать ссылку');
    }
  };

  const deleteInvite = async (id) => {
    await fetch(API + '/invite-codes/' + id, {method: 'DELETE'});
    await refreshData();
  };

  return {
    saveUser,
    toggleUserActive,
    deleteUser,
    resetUserTwoFactor,
    createInvite,
    createSupplierInvite,
    deleteInvite,
  };
};
