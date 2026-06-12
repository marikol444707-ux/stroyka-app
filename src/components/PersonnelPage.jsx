import React from 'react';
import { Check, CheckCircle, ChevronDown, ChevronUp, Edit2, Eye, FileText, Plus, Search, Trash2, X } from 'lucide-react';

export default function PersonnelPage({
  C,
  ROLE_GROUPS,
  ROLE_LABELS,
  PD_CONSENT_TEXT,
  UNITS,
  API,
  addPiecework,
  addStaffDoc,
  buildContractContent,
  buildPositionInstructionContent,
  btnB,
  btnG,
  btnO,
  btnR,
  calcSalary,
  card,
  contracts,
  createStaffAccessFromPrompt,
  daysInMonth,
  deletePiecework,
  deleteStaff,
  editingItem,
  expandedMaster,
  expandedMasterProject,
  expandedPieceworkProject,
  expandedStaffId,
  fileSrc,
  findUserForStaff,
  fmtMeasure,
  inp,
  interimActs,
  listSearch,
  masterProfiles,
  masterRatings,
  matchSearch,
  newPiecework,
  newStaff,
  newStaffDoc,
  openStaffProfile,
  pdConsents,
  personnelTab,
  piecework,
  projects,
  ratemaster,
  resetStaffAccessPassword,
  roleColor,
  saveStaff,
  setEditingItem,
  setExpandedMaster,
  setExpandedMasterProject,
  setExpandedPieceworkProject,
  setListSearch,
  setNewPiecework,
  setNewStaff,
  setNewStaffDoc,
  setPersonnelTab,
  setShowForm,
  setShowPhotoModal,
  setShowPiecework,
  setShowStaffDocForm,
  setStaffProfile,
  setStaffExpandedSections,
  showForm,
  showPiecework,
  showPreview,
  showStaffDocForm,
  staff,
  staffExpandedSections,
  staffProfile,
  staffProfileLoading,
  tbl,
  tblC,
  tblH,
  timesheet,
  toggleDay,
  uploadPhoto,
  users,
  workJournal,
  workedDays,
}) {
  return (
    <div>
      <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
        {['staff','timesheet','piecework'].map(tab=>(
          <button key={tab} onClick={()=>{setPersonnelTab(tab);setShowForm(false);}} style={{...personnelTab===tab?btnO:btnG,fontSize:'12px',padding:'7px 14px'}}>
            {{staff:'👥 Сотрудники',timesheet:'📅 Табель',piecework:'💵 Сдельные'}[tab]}
          </button>
        ))}
      </div>

      {personnelTab==='masters'&&(
        <div>
          <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>Мастера и субподрядчики</h3>
          {ROLE_GROUPS.filter(g=>['рабочие','субподрядчики'].includes(g.key)).map(group=>{
            const groupUsers=users.filter(u=>group.roles.includes(u.role));
            if(groupUsers.length===0) return null;
            return (
              <div key={group.key} style={{marginBottom:'20px'}}>
                <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'10px',padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}>
                  <div style={{width:'10px',height:'10px',borderRadius:'50%',backgroundColor:group.color}}/>
                  <b style={{color:C.text,fontSize:'13px'}}>{group.label}</b>
                  <span style={{color:C.textSec,fontSize:'12px'}}>{'('+groupUsers.length+')'}</span>
                </div>
                {groupUsers.map(u=>{
                  const profile=masterProfiles.find(p=>p.userId===u.id);
                  const consent=pdConsents.find(c=>c.userId===u.id);
                  const contract=contracts.find(c=>c.masterId===u.id);
                  const myActs=interimActs.filter(a=>a.masterId===u.id);
                  const totalEarned=myActs.reduce((s,a)=>s+(a.totalAmount||0),0);
                  const totalPaid=myActs.reduce((s,a)=>s+(a.paidAmount||0),0);
                  const rating=masterRatings[u.id]||0;
                  const isOpen=expandedMaster===u.id;
                  return (
                    <div key={u.id} style={{...card,marginBottom:'10px',marginLeft:'12px'}}>
                      <div style={{padding:'14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={()=>setExpandedMaster(isOpen?null:u.id)}>
                        <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
                          <div style={{width:'42px',height:'42px',borderRadius:'12px',backgroundColor:roleColor(u.role),display:'flex',alignItems:'center',justifyContent:'center',fontSize:'16px',color:'white',fontWeight:'800',flexShrink:0}}>{u.name.charAt(0)}</div>
                          <div>
                            <b style={{color:C.text,fontSize:'14px'}}>{u.name}</b>
                            <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{ROLE_LABELS[u.role]+(profile?' · '+profile.contractType+(profile.specialization?' · '+profile.specialization:''):'')}</p>
                            <div style={{display:'flex',gap:'4px',marginTop:'3px'}}>
                              {[1,2,3,4,5].map(s=>(
                                <span key={s} style={{color:s<=rating?'#f59e0b':'#d1d5db',fontSize:'16px',cursor:'pointer'}} onClick={e=>{e.stopPropagation();ratemaster(u.id,s);}}>
                                  {s<=rating?'★':'☆'}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                        <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                          <div style={{textAlign:'right'}}>
                            <p style={{color:C.success,margin:0,fontSize:'13px',fontWeight:'600'}}>{totalEarned.toLocaleString()+' ₽'}</p>
                            {totalEarned-totalPaid>0&&<p style={{color:C.danger,margin:'2px 0 0',fontSize:'11px'}}>{'Долг: '+(totalEarned-totalPaid).toLocaleString()+' ₽'}</p>}
                          </div>
                          {isOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}
                        </div>
                      </div>
                      {isOpen&&(
                        <div style={{borderTop:'1.5px solid '+C.border,padding:'14px'}}>
                          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'15px'}}>
                            <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}>
                              <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Профиль</p>
                              {profile?(
                                <div>
                                  <p style={{margin:'2px 0',fontSize:'12px',color:C.text}}>{'ФИО: '+profile.fullName}</p>
                                  <p style={{margin:'2px 0',fontSize:'12px',color:C.text}}>{'ИНН: '+profile.inn}</p>
                                  <p style={{margin:'2px 0',fontSize:'12px',color:C.text}}>{'Банк: '+profile.bankName}</p>
                                  <p style={{margin:'2px 0',fontSize:'12px',color:C.text}}>{'Р/с: '+profile.bankAccount}</p>
                                </div>
                              ):<p style={{color:C.textMuted,fontSize:'12px'}}>Не заполнен</p>}
                            </div>
                            <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}>
                              <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Документы</p>
                              <div style={{display:'flex',flexDirection:'column',gap:'6px'}}>
                                {consent?(
                                  <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                                    <CheckCircle size={14} color={C.success}/>
                                    <span style={{fontSize:'12px',color:C.success}}>ПД подписано</span>
                                    {consent.scanUrl&&<img src={fileSrc(consent.scanUrl)} alt="" onClick={()=>setShowPhotoModal(fileSrc(consent.scanUrl))} style={{width:'28px',height:'28px',borderRadius:'4px',objectFit:'cover',cursor:'pointer'}}/>}
                                  </div>
                                ):<span style={{fontSize:'12px',color:C.warning}}>⚠️ ПД не подписано</span>}
                                {contract?(
                                  <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                                    <CheckCircle size={14} color={C.success}/>
                                    <span style={{fontSize:'12px',color:C.success}}>{'Договор № '+contract.contractNumber}</span>
                                  </div>
                                ):<span style={{fontSize:'12px',color:C.warning}}>⚠️ Договора нет</span>}
                              </div>
                            </div>
                          </div>
                          <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginBottom:'15px'}}>
                            {profile&&contract&&<button onClick={()=>showPreview(buildContractContent(profile,contract),'Договор')} style={btnB}><Eye size={13}/>Договор</button>}
                            {profile&&<button onClick={()=>showPreview(PD_CONSENT_TEXT(profile),'Согласие на ПД')} style={btnG}><FileText size={13}/>Согласие ПД</button>}
                            {profile&&<button onClick={()=>showPreview(buildPositionInstructionContent(u.role,profile.fullName),'Должностная инструкция')} style={btnG}><FileText size={13}/>Должн. инструкция</button>}
                          </div>
                          <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>Работы по проектам:</b>
                          {[...new Set(workJournal.filter(j=>j.masterId===u.id).map(j=>j.project))].map(projectName=>{
                            const pWorks=workJournal.filter(j=>j.masterId===u.id&&j.project===projectName);
                            const pTotal=pWorks.reduce((s,w)=>s+(w.total||0),0);
                            const isProjectOpen=expandedMasterProject===u.id+'-'+projectName;
                            return (
                              <div key={projectName} style={{marginBottom:'8px',borderRadius:'8px',border:'1.5px solid '+C.border,overflow:'hidden'}}>
                                <div style={{padding:'10px 12px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center',backgroundColor:C.bg}} onClick={()=>setExpandedMasterProject(isProjectOpen?null:u.id+'-'+projectName)}>
                                  <b style={{fontSize:'12px',color:C.text}}>{projectName}</b>
                                  <div style={{display:'flex',gap:'8px',alignItems:'center'}}>
                                    <span style={{fontSize:'12px',color:C.success,fontWeight:'600'}}>{pTotal.toLocaleString()+' ₽'}</span>
                                    {isProjectOpen?<ChevronUp size={14}/>:<ChevronDown size={14}/>}
                                  </div>
                                </div>
                                {isProjectOpen&&(
                                  <div style={{padding:'8px 12px'}}>
                                    {pWorks.map(w=>(
                                      <div key={w.id} style={{padding:'6px 0',borderBottom:'1px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                                        <div>
                                          <span style={{fontSize:'12px',color:C.text}}>{w.description}</span>
                                          <p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{fmtMeasure(w.quantity,w.unit)+' · '+w.date}</p>
                                        </div>
                                        <b style={{fontSize:'12px',color:C.success}}>{(w.total||0).toLocaleString()+' ₽'}</b>
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
                  );
                })}
              </div>
            );
          })}
        </div>
      )}

      {personnelTab==='staff'&&(
        <div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
            <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Сотрудники компании</b>
            <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewStaff({name:'',role:'',phone:'',salary:'',project:'',payType:'оклад'});}} style={btnO}><Plus size={14}/>Добавить</button>
          </div>
          {showForm&&(
            <div style={{...card,padding:'20px',marginBottom:'16px'}}>
              <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>👤 Основное</b>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'10px',marginBottom:'10px'}}>
                <input placeholder='Фамилия *' value={newStaff.lastName} onChange={e=>setNewStaff({...newStaff,lastName:e.target.value,name:[e.target.value,newStaff.firstName,newStaff.middleName].filter(Boolean).join(' ')})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Имя *' value={newStaff.firstName} onChange={e=>setNewStaff({...newStaff,firstName:e.target.value,name:[newStaff.lastName,e.target.value,newStaff.middleName].filter(Boolean).join(' ')})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Отчество' value={newStaff.middleName} onChange={e=>setNewStaff({...newStaff,middleName:e.target.value,name:[newStaff.lastName,newStaff.firstName,e.target.value].filter(Boolean).join(' ')})} style={{...inp,marginBottom:0}}/>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'10px'}}>
                <input placeholder='Должность (напр. штукатур)' value={newStaff.role} onChange={e=>setNewStaff({...newStaff,role:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Специализация' value={newStaff.specialization} onChange={e=>setNewStaff({...newStaff,specialization:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Телефон' value={newStaff.phone} onChange={e=>setNewStaff({...newStaff,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newStaff.project} onChange={e=>setNewStaff({...newStaff,project:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>Объект</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
                <select value={newStaff.payType} onChange={e=>setNewStaff({...newStaff,payType:e.target.value})} style={{...inp,marginBottom:0}}><option value='оклад'>Оклад</option><option value='сдельно'>Сдельно</option><option value='почасово'>Почасово</option></select>
                {newStaff.payType!=='сдельно'&&<input placeholder={newStaff.payType==='почасово'?'Ставка ₽/ч':'Оклад (₽)'} type='number' step='any' inputMode='decimal' value={newStaff.salary} onChange={e=>setNewStaff({...newStaff,salary:e.target.value})} style={{...inp,marginBottom:0}}/>}
                <select value={newStaff.status} onChange={e=>setNewStaff({...newStaff,status:e.target.value})} style={{...inp,marginBottom:0}}><option>Активен</option><option>Отпуск</option><option>Больничный</option><option>Уволен</option></select>
                <select value={newStaff.employmentType} onChange={e=>setNewStaff({...newStaff,employmentType:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>Тип занятости</option><option>Трудовой договор</option><option>ГПХ</option><option>Самозанятый</option><option>ИП</option><option>ООО</option></select>
              </div>

              <div onClick={()=>setStaffExpandedSections(s=>({...s,access:!s.access}))} style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',cursor:'pointer',marginBottom:'6px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <b style={{fontSize:'12px',color:C.text}}>🔐 Доступ в систему</b>
                <span style={{fontSize:'14px',color:C.textSec}}>{staffExpandedSections.access?'▾':'▸'}</span>
              </div>
              {staffExpandedSections.access&&(
                <div style={{padding:'10px',marginBottom:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}>
                  <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 8px'}}>Чтобы сотрудник мог входить в приложение — заполните все три поля. Если email уже есть, пароль, роль и объекты будут обновлены.</p>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                    <select value={newStaff.systemRole} onChange={e=>setNewStaff({...newStaff,systemRole:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>Системная роль</option>{Object.keys(ROLE_LABELS).filter(r=>r!=='заказчик'&&r!=='поставщик').map(r=><option key={r} value={r}>{ROLE_LABELS[r]}</option>)}</select>
                    <input type='email' placeholder='Email для входа' value={newStaff.email} onChange={e=>setNewStaff({...newStaff,email:e.target.value,emailWork:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='text' placeholder='Пароль' value={newStaff.password} onChange={e=>setNewStaff({...newStaff,password:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                  </div>
                  {['прораб','технадзор','стройконтроль'].includes(newStaff.systemRole)&&(()=>{const ap=newStaff.assignedProjects||[];return(
                    <div style={{marginTop:'10px',padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1px solid '+C.border}}>
                      <b style={{fontSize:'11px',color:C.text,display:'block',marginBottom:'6px'}}>📍 Назначить объекты (приказ директора)</b>
                      <p style={{color:C.textMuted,fontSize:'10px',margin:'0 0 8px'}}>Прораб увидит только эти объекты. Если ничего не выбрано — все.</p>
                      <div style={{maxHeight:'140px',overflowY:'auto',display:'flex',flexDirection:'column',gap:'4px'}}>
                        {projects.filter(p=>p.status!=='Завершён').map(pr=>(
                          <label key={pr.id} style={{display:'flex',alignItems:'center',gap:'6px',cursor:'pointer',padding:'4px 6px',borderRadius:'6px',backgroundColor:ap.includes(pr.name)?C.successLight:'transparent'}}>
                            <input type='checkbox' checked={ap.includes(pr.name)} onChange={()=>{const next=ap.includes(pr.name)?ap.filter(n=>n!==pr.name):[...ap,pr.name];setNewStaff({...newStaff,assignedProjects:next});}}/>
                            <span style={{fontSize:'12px',color:C.text}}>{pr.name}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  );})()}
                </div>
              )}

              <div onClick={()=>setStaffExpandedSections(s=>({...s,docs:!s.docs}))} style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',cursor:'pointer',marginBottom:'6px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <b style={{fontSize:'12px',color:C.text}}>📄 Документы</b>
                <span style={{fontSize:'14px',color:C.textSec}}>{staffExpandedSections.docs?'▾':'▸'}</span>
              </div>
              {staffExpandedSections.docs&&(
                <div style={{padding:'10px',marginBottom:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                    <input placeholder='Паспорт серия' value={newStaff.passportSeries} onChange={e=>setNewStaff({...newStaff,passportSeries:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Паспорт номер' value={newStaff.passportNumber} onChange={e=>setNewStaff({...newStaff,passportNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Кем выдан' value={newStaff.passportIssuedBy} onChange={e=>setNewStaff({...newStaff,passportIssuedBy:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                    <input type='date' placeholder='Дата выдачи' value={newStaff.passportIssuedDate} onChange={e=>setNewStaff({...newStaff,passportIssuedDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='date' placeholder='Дата рождения' value={newStaff.birthDate} onChange={e=>setNewStaff({...newStaff,birthDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='ИНН' value={newStaff.inn} onChange={e=>setNewStaff({...newStaff,inn:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='СНИЛС' value={newStaff.snils} onChange={e=>setNewStaff({...newStaff,snils:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Гражданство' value={newStaff.citizenship} onChange={e=>setNewStaff({...newStaff,citizenship:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Адрес проживания' value={newStaff.address} onChange={e=>setNewStaff({...newStaff,address:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                  </div>
                </div>
              )}

              <div onClick={()=>setStaffExpandedSections(s=>({...s,finance:!s.finance}))} style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',cursor:'pointer',marginBottom:'6px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <b style={{fontSize:'12px',color:C.text}}>💰 Финансы (для выплат)</b>
                <span style={{fontSize:'14px',color:C.textSec}}>{staffExpandedSections.finance?'▾':'▸'}</span>
              </div>
              {staffExpandedSections.finance&&(
                <div style={{padding:'10px',marginBottom:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                    <input placeholder='Расчётный счёт' value={newStaff.bankAccount} onChange={e=>setNewStaff({...newStaff,bankAccount:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Банк' value={newStaff.bankName} onChange={e=>setNewStaff({...newStaff,bankName:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='БИК' value={newStaff.bankBik} onChange={e=>setNewStaff({...newStaff,bankBik:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Кор/счёт' value={newStaff.bankCorr} onChange={e=>setNewStaff({...newStaff,bankCorr:e.target.value})} style={{...inp,marginBottom:0}}/>
                    {(newStaff.employmentType==='ИП'||newStaff.employmentType==='ООО')&&<input placeholder='ОГРНИП / ОГРН' value={newStaff.ogrnip} onChange={e=>setNewStaff({...newStaff,ogrnip:e.target.value})} style={{...inp,marginBottom:0}}/>}
                    <input placeholder='Номер карты' value={newStaff.cardNumber} onChange={e=>setNewStaff({...newStaff,cardNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                  </div>
                </div>
              )}

              <div onClick={()=>setStaffExpandedSections(s=>({...s,extra:!s.extra}))} style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',cursor:'pointer',marginBottom:'6px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <b style={{fontSize:'12px',color:C.text}}>📝 Дополнительно</b>
                <span style={{fontSize:'14px',color:C.textSec}}>{staffExpandedSections.extra?'▾':'▸'}</span>
              </div>
              {staffExpandedSections.extra&&(
                <div style={{padding:'10px',marginBottom:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                    <input placeholder='Email личный' value={newStaff.emailPersonal} onChange={e=>setNewStaff({...newStaff,emailPersonal:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Доп. телефон (родственник)' value={newStaff.phoneExtra} onChange={e=>setNewStaff({...newStaff,phoneExtra:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='date' placeholder='Дата приёма' value={newStaff.hiredDate} onChange={e=>setNewStaff({...newStaff,hiredDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='date' placeholder='Дата увольнения' value={newStaff.firedDate} onChange={e=>setNewStaff({...newStaff,firedDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Бригада/Подразделение' value={newStaff.brigade} onChange={e=>setNewStaff({...newStaff,brigade:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Категория/разряд' value={newStaff.category} onChange={e=>setNewStaff({...newStaff,category:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <textarea placeholder='Заметки' value={newStaff.notes} onChange={e=>setNewStaff({...newStaff,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2',minHeight:'60px',fontFamily:'inherit'}}/>
                  </div>
                </div>
              )}

              <div style={{display:'flex',gap:'8px',marginTop:'14px'}}>
                <button onClick={saveStaff} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button>
                <button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button>
              </div>
            </div>
          )}
          <div style={{position:'relative',marginBottom:'12px'}}>
            <Search size={14} style={{position:'absolute',left:'10px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
            <input placeholder='🔍 Поиск сотрудника (ФИО, должность, объект)' value={listSearch} onChange={e=>setListSearch(e.target.value)} style={{...inp,marginBottom:0,paddingLeft:'32px'}}/>
          </div>
          <table style={tbl}>
            <thead>
              <tr>
                <th style={tblH}></th>
                <th style={tblH}>ФИО</th>
                <th style={tblH}>Должность</th>
                <th style={tblH}>Объект</th>
                <th style={tblH}>Тип оплаты</th>
                <th style={tblH}>Зарплата</th>
                <th style={tblH}>Доступ</th>
                <th style={tblH}></th>
              </tr>
            </thead>
            <tbody>
              {staff.filter(s=>matchSearch(listSearch,s.name,s.role,s.project,s.specialization)).map(s=>{
                const hasAccess=findUserForStaff(s);
                const isExp=expandedStaffId===s.id;
                return (
                  <React.Fragment key={s.id}>
                    <tr style={{cursor:'pointer',backgroundColor:isExp?C.bg:'transparent'}} onClick={()=>openStaffProfile(s)}>
                      <td style={{...tblC,width:'24px',textAlign:'center'}}>{isExp?<ChevronUp size={14}/>:<ChevronDown size={14}/>}</td>
                      <td style={tblC}><b style={{fontSize:'13px'}}>{s.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{s.phone}</p></td>
                      <td style={tblC}>{s.role}{s.specialization?' · '+s.specialization:''}</td>
                      <td style={tblC}>{s.project||'—'}</td>
                      <td style={tblC}>{s.payType==='сдельно'?'Сдельно':'Оклад: '+(s.salary||0).toLocaleString()+' ₽'}</td>
                      <td style={{...tblC,fontWeight:'600',color:C.success}}>{calcSalary(s).toLocaleString()+' ₽'}</td>
                      <td style={tblC} onClick={e=>e.stopPropagation()}>
                        {hasAccess
                          ? <div style={{display:'flex',alignItems:'center',gap:'6px',flexWrap:'wrap'}}><span style={{padding:'2px 8px',borderRadius:'10px',backgroundColor:C.successLight,color:C.success,fontSize:'11px',fontWeight:'600'}}>✅ {hasAccess.email||'есть'}</span><button onClick={()=>resetStaffAccessPassword(hasAccess,s)} style={{...btnG,padding:'3px 8px',fontSize:'11px'}}>🔑 Пароль</button></div>
                          : <button onClick={()=>createStaffAccessFromPrompt(s)} style={{...btnB,padding:'3px 8px',fontSize:'11px'}}>🔐 Выдать</button>}
                      </td>
                      <td style={tblC} onClick={e=>e.stopPropagation()}>
                        <div style={{display:'flex',gap:'4px'}}>
                          <button onClick={()=>{const access=findUserForStaff(s);setEditingItem(s);setNewStaff({...s,salary:String(s.salary||''),email:access?.email||s.emailWork||s.emailPersonal||'',password:'',systemRole:access?.role||''});setShowForm(true);}} style={{...btnG,padding:'3px 7px'}}><Edit2 size={11}/></button>
                          <button onClick={()=>deleteStaff(s.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button>
                        </div>
                      </td>
                    </tr>
                    {isExp&&(
                      <tr>
                        <td colSpan='8' style={{padding:'14px 18px',backgroundColor:C.bg,borderBottom:'1.5px solid '+C.border}}>
                          {staffProfileLoading?<p style={{color:C.textMuted,fontSize:'12px'}}>⏳ Загрузка профиля...</p>:staffProfile?(
                            <div>
                              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:'10px',marginBottom:'14px'}}>
                                <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Тип занятости</p><b style={{fontSize:'12px',color:C.text}}>{s.employmentType||'не указан'}</b></div>
                                <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Паспорт</p><b style={{fontSize:'12px',color:C.text}}>{s.passportSeries||s.passportNumber?(s.passportSeries+' '+s.passportNumber):'не заполнен'}</b></div>
                                <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>ИНН</p><b style={{fontSize:'12px',color:C.text}}>{s.inn||'не заполнен'}</b></div>
                                <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Банк</p><b style={{fontSize:'12px',color:C.text}}>{s.bankName||'не указан'}</b></div>
                              </div>

                              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'14px'}}>
                                <div style={{...card,padding:'12px'}}>
                                  <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>📄 Договоры ({staffProfile.contracts.length})</b>
                                  {staffProfile.contracts.length===0?<p style={{color:C.textMuted,fontSize:'11px'}}>Договоров нет</p>:staffProfile.contracts.map(c=>(<div key={c.id} style={{padding:'6px 0',borderBottom:'1px solid '+C.border,fontSize:'11px'}}><b>№{c.contractNumber}</b> · {c.project} · {c.status||'-'}</div>))}
                                </div>
                                <div style={{...card,padding:'12px'}}>
                                  <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>📋 Акты ({staffProfile.acts.length})</b>
                                  {staffProfile.acts.length===0?<p style={{color:C.textMuted,fontSize:'11px'}}>Актов нет</p>:staffProfile.acts.map(a=>(<div key={a.id} style={{padding:'6px 0',borderBottom:'1px solid '+C.border,fontSize:'11px',display:'flex',justifyContent:'space-between'}}><span>№{a.actNumber} · {a.project}</span><b style={{color:C.success}}>{a.totalAmount.toLocaleString()} ₽</b></div>))}
                                </div>
                                <div style={{...card,padding:'12px'}}>
                                  <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>✅ Согласия на ПД ({staffProfile.pdConsents.length})</b>
                                  {staffProfile.pdConsents.length===0?<p style={{color:C.warning,fontSize:'11px'}}>⚠️ Не подписано</p>:staffProfile.pdConsents.map(p=>(<div key={p.id} style={{padding:'6px 0',fontSize:'11px',color:C.success}}>✓ Подписано {p.signedAt}</div>))}
                                </div>
                                <div style={{...card,padding:'12px'}}>
                                  <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>🔒 Инструктажи ТБ ({staffProfile.tbJournal.length})</b>
                                  {staffProfile.tbJournal.length===0?<p style={{color:C.warning,fontSize:'11px'}}>⚠️ Инструктажей нет</p>:staffProfile.tbJournal.slice(0,5).map(t=>(<div key={t.id} style={{padding:'4px 0',fontSize:'11px'}}><b>{t.instructionType}</b> · {t.projectName} · {t.date}</div>))}
                                </div>
                              </div>

                              <div style={{...card,padding:'12px',marginTop:'14px'}}>
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
                                  <b style={{fontSize:'12px',color:C.text}}>📎 Прочие документы ({staffProfile.customDocuments.length})</b>
                                  <button onClick={()=>setShowStaffDocForm(true)} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><Plus size={11}/>Добавить</button>
                                </div>
                                {showStaffDocForm&&(
                                  <div style={{marginBottom:'10px',padding:'10px',backgroundColor:C.bg,borderRadius:'8px'}}>
                                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'6px'}}>
                                      <select value={newStaffDoc.docType} onChange={e=>setNewStaffDoc({...newStaffDoc,docType:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>
                                        {['Трудовой договор','Договор ГПХ','Договор с самозанятым','Договор с ИП','Приказ','Должн. инструкция','Мед. книжка','Справка о статусе самозанятого','Чек НПД','Прочее'].map(t=><option key={t}>{t}</option>)}
                                      </select>
                                      <input placeholder='Название/Номер' value={newStaffDoc.title} onChange={e=>setNewStaffDoc({...newStaffDoc,title:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    </div>
                                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'6px',marginBottom:'6px'}}>
                                      <input type='file' accept='image/*,.pdf' onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{projectName:s.project,context:'staff-documents'});setNewStaffDoc({...newStaffDoc,fileUrl:url});}}} style={{fontSize:'11px'}}/>
                                      <input type='date' value={newStaffDoc.signedAt} onChange={e=>setNewStaffDoc({...newStaffDoc,signedAt:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input type='date' placeholder='Истекает' value={newStaffDoc.expiresAt} onChange={e=>setNewStaffDoc({...newStaffDoc,expiresAt:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    </div>
                                    <div style={{display:'flex',gap:'6px'}}>
                                      <button onClick={()=>addStaffDoc(s.id)} style={{...btnO,fontSize:'11px',padding:'4px 10px'}}><Check size={11}/>Сохранить</button>
                                      <button onClick={()=>setShowStaffDocForm(false)} style={{...btnG,fontSize:'11px',padding:'4px 10px'}}><X size={11}/>Отмена</button>
                                    </div>
                                  </div>
                                )}
                                {staffProfile.customDocuments.map(d=>(
                                  <div key={d.id} style={{padding:'6px 0',borderBottom:'1px solid '+C.border,fontSize:'11px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                                    <div style={{flex:1}}><b>{d.docType}</b> · {d.title}{d.signedAt?' · подписан '+d.signedAt:''}{d.expiresAt?' · истекает '+d.expiresAt:''}</div>
                                    <div style={{display:'flex',gap:'4px'}}>
                                      {d.fileUrl&&<a href={fileSrc(d.fileUrl)} target='_blank' rel='noreferrer' style={{...btnB,padding:'2px 8px',fontSize:'10px',textDecoration:'none'}}>👁️</a>}
                                      <button onClick={async()=>{
                                        if(window.confirm('Удалить документ?')){
                                          await fetch(API+'/staff-documents/'+d.id,{method:'DELETE'});
                                          const data=await fetch(API+'/staff/'+s.id+'/profile').then(r=>r.json());
                                          setStaffProfile(data);
                                        }
                                      }} style={{...btnR,padding:'2px 7px'}}><Trash2 size={10}/></button>
                                    </div>
                                  </div>
                                ))}
                                {staffProfile.customDocuments.length===0&&<p style={{color:C.textMuted,fontSize:'11px',padding:'4px'}}>Нет загруженных документов</p>}
                              </div>

                              {staffProfile.workJournal.length>0&&(
                                <div style={{...card,padding:'12px',marginTop:'14px'}}>
                                  <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>💼 Последние работы ({staffProfile.workJournal.length})</b>
                                  {staffProfile.workJournal.slice(0,8).map((w,i)=>(<div key={i} style={{padding:'4px 0',borderBottom:'1px solid '+C.border,fontSize:'11px',display:'flex',justifyContent:'space-between'}}><span>{w.project} · {w.description} · {w.quantity} {w.unit}</span><b style={{color:C.success}}>{w.total.toLocaleString()} ₽</b></div>))}
                                </div>
                              )}
                            </div>
                          ):<p style={{color:C.textMuted,fontSize:'12px'}}>Не удалось загрузить профиль</p>}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {personnelTab==='timesheet'&&(
        <div>
          <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>Табель учёта</h3>
          <div style={{overflowX:'auto'}}>
            <table style={tbl}>
              <thead>
                <tr>
                  <th style={{...tblH,minWidth:'150px'}}>Сотрудник</th>
                  {daysInMonth.map(d=><th key={d} style={{...tblH,textAlign:'center',padding:'6px 4px',minWidth:'28px'}}>{d}</th>)}
                  <th style={tblH}>Дни</th>
                  <th style={tblH}>Итого</th>
                </tr>
              </thead>
              <tbody>
                {staff.map(s=>(
                  <tr key={s.id}>
                    <td style={tblC}><b style={{fontSize:'12px'}}>{s.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{s.role}</p></td>
                    {daysInMonth.map(d=>(
                      <td key={d} style={{...tblC,textAlign:'center',padding:'4px',cursor:'pointer'}} onClick={()=>toggleDay(s.id,d)}>
                        <div style={{width:'22px',height:'22px',borderRadius:'6px',backgroundColor:timesheet[s.id+'-'+d]?C.success:'transparent',border:'1.5px solid '+(timesheet[s.id+'-'+d]?C.success:C.border),display:'flex',alignItems:'center',justifyContent:'center',margin:'auto',fontSize:'10px',color:'white',fontWeight:'700'}}>
                          {timesheet[s.id+'-'+d]?'✓':''}
                        </div>
                      </td>
                    ))}
                    <td style={{...tblC,fontWeight:'600'}}>{workedDays(s.id)}</td>
                    <td style={{...tblC,fontWeight:'700',color:C.success}}>{calcSalary(s).toLocaleString()+' ₽'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {personnelTab==='piecework'&&(
        <div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
            <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Сдельные работы</b>
            <button onClick={()=>setShowPiecework(!showPiecework)} style={btnO}><Plus size={14}/>Добавить</button>
          </div>
          {showPiecework&&(
            <div style={{...card,padding:'20px',marginBottom:'16px'}}>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                <select value={newPiecework.staffId} onChange={e=>setNewPiecework({...newPiecework,staffId:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Сотрудник *</option>{staff.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>
                <select value={newPiecework.project} onChange={e=>setNewPiecework({...newPiecework,project:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Объект</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
                <input placeholder="Описание *" value={newPiecework.description} onChange={e=>setNewPiecework({...newPiecework,description:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder="Количество *" type="number" step="any" inputMode="decimal" value={newPiecework.quantity} onChange={e=>setNewPiecework({...newPiecework,quantity:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newPiecework.unit} onChange={e=>setNewPiecework({...newPiecework,unit:e.target.value})} style={{...inp,marginBottom:0}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                <input placeholder="Цена за единицу *" type="number" step="any" inputMode="decimal" value={newPiecework.pricePerUnit} onChange={e=>setNewPiecework({...newPiecework,pricePerUnit:e.target.value})} style={{...inp,marginBottom:0}}/>
                <div style={{padding:'10px',backgroundColor:C.accentLight,borderRadius:'8px',border:'1.5px solid '+C.accentBorder,display:'flex',alignItems:'center',justifyContent:'center'}}><b style={{color:C.accent}}>{newPiecework.quantity&&newPiecework.pricePerUnit?(Number(newPiecework.quantity)*Number(newPiecework.pricePerUnit)).toLocaleString()+' ₽':'0 ₽'}</b></div>
              </div>
              <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={addPiecework} style={btnO}><Check size={14}/>Добавить</button><button onClick={()=>setShowPiecework(false)} style={btnG}><X size={14}/>Отмена</button></div>
            </div>
          )}
          {staff.map(s=>{
            const sWorks=piecework.filter(p=>Number(p.staffId)===s.id);
            const sTotal=sWorks.reduce((ss,p)=>ss+p.total,0);
            if(sWorks.length===0) return null;
            const isOpen=expandedPieceworkProject===s.id;
            return (
              <div key={s.id} style={{...card,marginBottom:'10px'}}>
                <div style={{padding:'14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={()=>setExpandedPieceworkProject(isOpen?null:s.id)}>
                  <div><b style={{color:C.text,fontSize:'13px'}}>{s.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{sWorks.length+' работ'}</p></div>
                  <div style={{display:'flex',alignItems:'center',gap:'10px'}}><b style={{color:C.success,fontSize:'14px'}}>{sTotal.toLocaleString()+' ₽'}</b>{isOpen?<ChevronUp size={16}/>:<ChevronDown size={16}/>}</div>
                </div>
                {isOpen&&(
                  <div style={{borderTop:'1.5px solid '+C.border,padding:'12px 14px'}}>
                    {sWorks.map(w=>(
                      <div key={w.id} style={{padding:'8px 0',borderBottom:'1px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                        <div><b style={{fontSize:'12px',color:C.text}}>{w.description}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{w.quantity+' '+w.unit+' × '+w.pricePerUnit.toLocaleString()+' ₽ · '+w.date+(w.project?' · '+w.project:'')}</p></div>
                        <div style={{display:'flex',gap:'6px',alignItems:'center'}}><b style={{fontSize:'12px',color:C.success}}>{w.total.toLocaleString()+' ₽'}</b><button onClick={()=>deletePiecework(w.id)} style={{...btnR,padding:'3px 6px'}}><Trash2 size={10}/></button></div>
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
  );
}
