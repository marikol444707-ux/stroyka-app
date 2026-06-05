import React from 'react';
import { Check, ChevronDown, ChevronUp, Copy, Edit2, Plus, RefreshCw, Trash2, X } from 'lucide-react';

const emptyUser = {
  name: '',
  email: '',
  password: '',
  role: 'прораб',
  projectId: '',
  projectName: '',
  active: true,
};

function UsersPage({
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
    setNewUser({...emptyUser});
  };

  const editUser = (u) => {
    setEditingItem(u);
    setNewUser({
      name: u.name,
      email: u.email,
      password: '',
      role: u.role,
      projectId: u.projectId || '',
      projectName: u.projectName || '',
      active: u.active !== false,
    });
    setShowForm(true);
  };

  const generatePassword = () => {
    const password = generateTempPassword();
    setNewUser({...newUser, password});
    navigator.clipboard?.writeText(password).catch(() => {});
  };

  const updateProject = (projectId) => {
    const project = projects.find(p => p.id === Number(projectId));
    setNewUser({...newUser, projectId, projectName: project ? project.name : ''});
  };

  return (
    <div>
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
          <select value={newUser.role} onChange={e=>setNewUser({...newUser,role:e.target.value})} style={{...inp,marginBottom:0}}>{Object.keys(ROLES).map(r=><option key={r} value={r}>{ROLE_LABELS[r]||r}</option>)}</select>
          {['заказчик','технадзор'].includes(newUser.role)&&(<select value={newUser.projectId} onChange={e=>updateProject(e.target.value)} style={{...inp,marginBottom:0}}><option value=''>Привязать к проекту *</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>)}
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
                <div><b style={{fontSize:'13px',color:C.text}}>{u.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{u.email+' · '+(ROLE_LABELS[u.role]||u.role)}{u.projectName?' · '+u.projectName:''}</p>{u.active===false&&<span style={{...badge(C.danger,C.dangerLight,C.dangerBorder),fontSize:'10px'}}>Доступ отключён</span>}</div>
              </div>
              <div style={{display:'flex',gap:'6px'}}>
                <button onClick={()=>editUser(u)} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><Edit2 size={11}/></button>
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
