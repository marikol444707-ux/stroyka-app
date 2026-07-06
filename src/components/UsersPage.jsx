import React from 'react';
import { Check, ChevronDown, ChevronUp, Copy, Edit2, Plus, RefreshCw, Trash2, X } from 'lucide-react';
import { createUserForm } from '../features/personnel/personnelInitialForms';

function UsersPage({
  API,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnGr,
  btnR,
  badge,
  users,
  user,
  projects,
  estimatesList = [],
  ROLES,
  ROLE_LABELS,
  ROLE_GROUPS,
  roleColor,
  searchUser,
  setSearchUser,
  showForm,
  setShowForm,
  editingItem,
  setEditingItem,
  newUser,
  setNewUser,
  saveUser,
  generateTempPassword,
  toggleUserActive,
  deleteUser,
  resetUserTwoFactor,
  showInvites,
  setShowInvites,
  newInviteRole,
  setNewInviteRole,
  createInvite,
  inviteCodes,
  deleteInvite,
  expandedGroup,
  setExpandedGroup,
}) {
  const openNewUser = () => {
    setShowForm(!showForm);
    setEditingItem(null);
    setNewUser(createUserForm());
  };
  const [messengerAccounts, setMessengerAccounts] = React.useState([]);
  const [messengerLoading, setMessengerLoading] = React.useState(false);
  const [maxBindingUser, setMaxBindingUser] = React.useState(null);
  const [maxBindingForm, setMaxBindingForm] = React.useState({externalUserId:'',chatId:'',displayName:'',enabled:true});
  const loadMessengerAccounts = React.useCallback(async () => {
    if (!API) return;
    setMessengerLoading(true);
    try {
      const res = await fetch(API + '/messenger-accounts');
      const data = await res.json().catch(() => ({}));
      setMessengerAccounts(Array.isArray(data.items) ? data.items : []);
    } catch (_error) {
      setMessengerAccounts([]);
    } finally {
      setMessengerLoading(false);
    }
  }, [API]);
  React.useEffect(() => {
    loadMessengerAccounts();
  }, [loadMessengerAccounts]);
  const maxAccountByUserId = React.useMemo(() => {
    const map = new Map();
    (messengerAccounts || []).filter(item => item.provider === 'max' && item.userId).forEach(item => {
      if (!map.has(Number(item.userId))) map.set(Number(item.userId), item);
    });
    return map;
  }, [messengerAccounts]);
  const openMaxBinding = (u) => {
    const existing = maxAccountByUserId.get(Number(u.id)) || null;
    setMaxBindingUser(u);
    setMaxBindingForm({
      externalUserId: existing?.externalUserId || '',
      chatId: existing?.chatId || existing?.externalUserId || '',
      displayName: existing?.displayName || u.name || '',
      enabled: existing ? existing.enabled !== false : true,
    });
  };
  const saveMaxBinding = async (enabledOverride = null) => {
    if (!maxBindingUser?.id) return;
    const enabled = enabledOverride === null ? maxBindingForm.enabled !== false : Boolean(enabledOverride);
    const externalUserId = String(maxBindingForm.externalUserId || '').trim();
    const chatId = String(maxBindingForm.chatId || '').trim();
    if (!externalUserId && !chatId) {
      alert('Укажите MAX userId или chatId');
      return;
    }
    const res = await fetch(API + '/messenger-accounts', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        provider:'max',
        userId:maxBindingUser.id,
        externalUserId,
        chatId,
        displayName:maxBindingForm.displayName || maxBindingUser.name || '',
        enabled,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      alert(data.detail || data.error || 'Не удалось сохранить MAX-связку');
      return;
    }
    await loadMessengerAccounts();
    setMaxBindingUser(null);
  };

  const editUser = (u) => {
    setEditingItem(u);
    setNewUser(createUserForm({
      name: u.name,
      email: u.email,
      password: '',
      role: u.role,
      projectId: u.projectId || '',
      projectName: u.projectName || '',
      assignedProjects: Array.isArray(u.assignedProjects) ? u.assignedProjects : [],
      assignedPackages: Array.isArray(u.assignedPackages) ? u.assignedPackages : [],
      active: u.active !== false,
    }));
    setShowForm(true);
  };

  const generatePassword = () => {
    const password = generateTempPassword();
    setNewUser({...newUser, password});
    navigator.clipboard?.writeText(password).catch(() => {});
  };

  const updateProject = (projectId) => {
    const project = projects.find(p => p.id === Number(projectId));
    const projectName = project ? project.name : '';
    const assignedProjects = projectName ? [projectName] : [];
    setNewUser({...newUser, projectId, projectName, assignedProjects, assignedPackages: []});
  };
  const projectScopedRoles = ['прораб','главный_инженер','технадзор','стройконтроль','мастер','субподрядчик','бригадир'];
  const packageScopedRoles = ['прораб','мастер','субподрядчик','бригадир'];
  const projectPackageOptions = Array.from(new Set(
    (estimatesList || [])
      .filter(e => (e.projectName || e.project_name || e.project || '') === (newUser.projectName || ''))
      .map(e => (e.workPackage || e.work_package || 'Основная').trim() || 'Основная')
      .filter(Boolean)
  )).sort((a, b) => a.localeCompare(b, 'ru'));
  const toggleAssignedPackage = (pkg) => {
    const current = Array.isArray(newUser.assignedPackages) ? newUser.assignedPackages : [];
    const next = current.includes(pkg) ? current.filter(x => x !== pkg) : [...current, pkg];
    setNewUser({...newUser, assignedPackages: next});
  };
  const handleRoleChange = (role) => {
    const keepProject = projectScopedRoles.includes(role);
    const keepPackages = packageScopedRoles.includes(role);
    setNewUser({
      ...newUser,
      role,
      projectId: keepProject ? newUser.projectId : '',
      projectName: keepProject ? newUser.projectName : '',
      assignedProjects: keepProject ? (newUser.assignedProjects || []) : [],
      assignedPackages: keepPackages ? (newUser.assignedPackages || []) : [],
    });
  };

  return (
    <div>
      {maxBindingUser&&(
        <div style={{position:'fixed',inset:0,zIndex:1800,background:'rgba(0,0,0,.55)',display:'flex',alignItems:'center',justifyContent:'center',padding:'18px'}}>
          <div style={{...card,width:'100%',maxWidth:'520px',padding:'20px',boxShadow:'0 18px 60px rgba(0,0,0,.35)'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px',marginBottom:'14px'}}>
              <div>
                <h3 style={{color:C.text,margin:'0 0 4px',fontWeight:'800'}}>Привязка MAX</h3>
                <p style={{color:C.textSec,margin:0,fontSize:'12px'}}>{maxBindingUser.name} · {ROLE_LABELS[maxBindingUser.role] || maxBindingUser.role}</p>
              </div>
              <button onClick={()=>setMaxBindingUser(null)} style={{...btnG,padding:'6px 8px'}}><X size={14}/></button>
            </div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
              <input placeholder="MAX userId" value={maxBindingForm.externalUserId} onChange={e=>setMaxBindingForm({...maxBindingForm,externalUserId:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input placeholder="MAX chatId" value={maxBindingForm.chatId} onChange={e=>setMaxBindingForm({...maxBindingForm,chatId:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input placeholder="Имя в MAX" value={maxBindingForm.displayName} onChange={e=>setMaxBindingForm({...maxBindingForm,displayName:e.target.value})} style={{...inp,marginBottom:0}}/>
              <select value={maxBindingForm.enabled?'on':'off'} onChange={e=>setMaxBindingForm({...maxBindingForm,enabled:e.target.value==='on'})} style={{...inp,marginBottom:0}}>
                <option value="on">Связка активна</option>
                <option value="off">Связка отключена</option>
              </select>
            </div>
            <div style={{marginTop:'12px',padding:'10px',border:'1.5px solid '+C.border,borderRadius:'10px',backgroundColor:C.bg}}>
              <b style={{display:'block',color:C.text,fontSize:'12px',marginBottom:'4px'}}>Mini-app URL для бота</b>
              <code style={{display:'block',color:C.accent,fontSize:'12px',wordBreak:'break-all'}}>{window.location.origin + '/max-app'}</code>
            </div>
            <div style={{display:'flex',gap:'10px',marginTop:'15px',flexWrap:'wrap'}}>
              <button onClick={()=>saveMaxBinding()} style={btnO}><Check size={14}/>Сохранить</button>
              <button onClick={()=>saveMaxBinding(false)} style={btnG}><X size={14}/>Отключить</button>
              <button onClick={()=>setMaxBindingUser(null)} style={btnG}>Отмена</button>
            </div>
          </div>
        </div>
      )}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px',flexWrap:'wrap',gap:'10px'}}>
        <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
          <button onClick={openNewUser} style={btnO}><Plus size={14}/>Новый пользователь</button>
          <button onClick={()=>setShowInvites(!showInvites)} style={btnG}><Plus size={14}/>Коды приглашений</button>
        </div>
        <input placeholder="Поиск..." value={searchUser} onChange={e=>setSearchUser(e.target.value)} style={{...inp,marginBottom:0,width:'220px'}}/>
      </div>

      {showForm&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
        <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{editingItem?'Редактировать':'Новый пользователь'}</h3>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
          <input placeholder="Имя *" value={newUser.name} onChange={e=>setNewUser({...newUser,name:e.target.value})} style={{...inp,marginBottom:0}}/>
          <input type="email" placeholder="Email *" value={newUser.email} onChange={e=>setNewUser({...newUser,email:e.target.value})} style={{...inp,marginBottom:0}}/>
          <div style={{display:'flex',gap:'6px'}}>
            <input type="text" placeholder={editingItem?'Новый пароль (если меняем)':'Пароль *'} value={newUser.password} onChange={e=>setNewUser({...newUser,password:e.target.value})} style={{...inp,marginBottom:0,flex:1}}/>
            <button onClick={generatePassword} title="Сгенерировать и скопировать пароль" style={{...btnG,padding:'6px 10px',margin:0}}><RefreshCw size={13}/></button>
          </div>
          <select value={newUser.role} onChange={e=>handleRoleChange(e.target.value)} style={{...inp,marginBottom:0}}>{Object.keys(ROLES).map(r=><option key={r} value={r}>{ROLE_LABELS[r]||r}</option>)}</select>
          {projectScopedRoles.includes(newUser.role)&&(<select value={newUser.projectId} onChange={e=>updateProject(e.target.value)} style={{...inp,marginBottom:0}}><option value=''>Привязать к проекту *</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>)}
          {packageScopedRoles.includes(newUser.role)&&newUser.projectName&&(
            <div style={{gridColumn:'span 2',border:'1.5px solid '+C.border,borderRadius:'10px',padding:'10px',backgroundColor:C.bg}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',marginBottom:'8px'}}>
                <b style={{color:C.text,fontSize:'12px'}}>Пакеты работ по объекту</b>
                <span style={{color:C.textSec,fontSize:'11px'}}>{(newUser.assignedPackages||[]).length || (newUser.role==='прораб' ? 'все для прораба' : 0)} выбрано</span>
              </div>
              <div style={{display:'flex',flexWrap:'wrap',gap:'8px'}}>
                {projectPackageOptions.map(pkg => (
                  <label key={pkg} style={{display:'inline-flex',alignItems:'center',gap:'6px',border:'1.5px solid '+((newUser.assignedPackages||[]).includes(pkg)?C.accent:C.border),borderRadius:'999px',padding:'6px 10px',color:C.text,fontSize:'12px',cursor:'pointer'}}>
                    <input type='checkbox' checked={(newUser.assignedPackages||[]).includes(pkg)} onChange={()=>toggleAssignedPackage(pkg)} style={{width:'14px',height:'14px'}}/>
                    {pkg}
                  </label>
                ))}
                {projectPackageOptions.length===0&&<span style={{color:C.textSec,fontSize:'12px'}}>По объекту пока нет активных смет с пакетами работ.</span>}
              </div>
              <p style={{margin:'8px 0 0',color:C.textSec,fontSize:'11px'}}>
                Мастер, субподрядчик и бригадир видят только выбранные пакеты. Прораб без выбора получает все активные пакеты объекта автоматически.
              </p>
            </div>
          )}
          {editingItem&&(<select value={newUser.active===false?'off':'on'} onChange={e=>setNewUser({...newUser,active:e.target.value==='on'})} style={{...inp,marginBottom:0}}><option value='on'>Аккаунт активен</option><option value='off'>Аккаунт отключён</option></select>)}
        </div>
        <div style={{display:'flex',gap:'10px',marginTop:'15px'}}><button onClick={saveUser} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Создать'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
      </div>)}

      {showInvites&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
        <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>Коды приглашений</h3>
        <div style={{display:'flex',gap:'10px',marginBottom:'15px',alignItems:'center'}}>
          <select value={newInviteRole} onChange={e=>setNewInviteRole(e.target.value)} style={{...inp,marginBottom:0,width:'200px'}}>{Object.keys(ROLES).map(r=><option key={r} value={r}>{ROLE_LABELS[r]||r}</option>)}</select>
          <button onClick={createInvite} style={btnO}><Plus size={14}/>Создать код</button>
        </div>
        {inviteCodes.filter(c=>!c.used).map(c=>(<div key={c.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'8px',border:'1.5px solid '+C.border}}>
          <div><b style={{fontSize:'14px',letterSpacing:'2px',color:C.accent}}>{c.code}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{ROLE_LABELS[c.role]||c.role}</p></div>
          <div style={{display:'flex',gap:'6px'}}>
            <button onClick={()=>navigator.clipboard.writeText(c.code)} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><Copy size={11}/>Скопировать</button>
            <button onClick={()=>deleteInvite(c.id)} style={{...btnR,padding:'5px 8px'}}><Trash2 size={11}/></button>
          </div>
        </div>))}
      </div>)}

      {ROLE_GROUPS.map(group=>{
        const groupUsers = users.filter(u=>group.roles.includes(u.role)&&u.name.toLowerCase().includes(searchUser.toLowerCase()));
        if(groupUsers.length===0) return null;
        const isOpen = expandedGroup === group.key;
        return(<div key={group.key} style={{...card,marginBottom:'10px'}}>
          <div style={{padding:'14px 18px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={()=>setExpandedGroup(isOpen?null:group.key)}>
            <div style={{display:'flex',alignItems:'center',gap:'10px'}}><div style={{width:'10px',height:'10px',borderRadius:'50%',backgroundColor:group.color}}/><b style={{color:C.text,fontSize:'14px'}}>{group.label}</b><span style={{...badge(group.color,C.bgWhite,C.border)}}>{groupUsers.length}</span></div>
            {isOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}
          </div>
          {isOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'10px 18px'}}>
            {groupUsers.map(u=>(<div key={u.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'10px 0',borderBottom:'1px solid '+C.border,opacity:u.active===false?0.58:1}}>
              <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                <div style={{width:'36px',height:'36px',borderRadius:'10px',backgroundColor:roleColor(u.role),display:'flex',alignItems:'center',justifyContent:'center',color:'white',fontWeight:'700',fontSize:'14px'}}>{u.name.charAt(0)}</div>
                <div>
                  <b style={{fontSize:'13px',color:C.text}}>{u.name}</b>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{u.email+' · '+(ROLE_LABELS[u.role]||u.role)}{u.projectName?' · '+u.projectName:''}</p>
                  <div style={{display:'flex',gap:'5px',flexWrap:'wrap'}}>
                    {(() => {
                      const maxAccount = maxAccountByUserId.get(Number(u.id));
                      if (maxAccount) {
                        return <span style={{...badge(maxAccount.enabled===false?C.warning:C.success,maxAccount.enabled===false?C.warningLight:C.successLight,maxAccount.enabled===false?C.warningBorder:C.successBorder),fontSize:'10px'}}>MAX {maxAccount.enabled===false?'отключён':'связан'}</span>;
                      }
                      return <span style={{...badge(C.textMuted,C.bg,C.border),fontSize:'10px'}}>MAX не связан</span>;
                    })()}
                    {u.active===false&&<span style={{...badge(C.danger,C.dangerLight,C.dangerBorder),fontSize:'10px'}}>Доступ отключён</span>}
                    {u.twoFactorRequired&&<span style={{...badge(u.twoFactorEnabled?C.success:C.warning,u.twoFactorEnabled?C.successLight:C.warningLight,u.twoFactorEnabled?C.successBorder:C.warningBorder),fontSize:'10px'}}>{u.twoFactorEnabled?'2FA включена':'Нужна 2FA'}</span>}
                  </div>
                </div>
              </div>
              <div style={{display:'flex',gap:'6px'}}>
                <button onClick={()=>openMaxBinding(u)} title={messengerLoading?'Связки загружаются':'Привязать MAX'} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>MAX</button>
                <button onClick={()=>editUser(u)} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><Edit2 size={11}/></button>
                {u.twoFactorEnabled&&<button onClick={()=>resetUserTwoFactor?.(u)} title="Сбросить 2FA" style={{...btnG,padding:'5px 8px',fontSize:'11px'}}>2FA</button>}
                {u.active===false?<button onClick={()=>toggleUserActive(u,true)} style={{...btnGr,padding:'5px 8px',fontSize:'11px'}}><Check size={11}/></button>:u.id!==user.id&&<button onClick={()=>deleteUser(u)} style={{...btnR,padding:'5px 8px',fontSize:'11px'}}><X size={11}/></button>}
              </div>
            </div>))}
          </div>)}
        </div>);
      })}
    </div>
  );
}

export default UsersPage;
