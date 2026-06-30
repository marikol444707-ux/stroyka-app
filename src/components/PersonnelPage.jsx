import React from 'react';
import { Check, CheckCircle, ChevronDown, ChevronUp, Edit2, Eye, FileText, Plus, Search, Trash2, X } from 'lucide-react';
import DocumentRecognitionPanel from './DocumentRecognitionPanel';

const STAFF_SORT_GROUPS = [
  { key: 'management', label: 'Руководство', hint: 'директор, замы' },
  { key: 'engineering', label: 'ИТР / прорабы', hint: 'прорабы, инженеры, сметчики' },
  { key: 'masters', label: 'Мастера', hint: 'мастера, бригадиры' },
  { key: 'contractors', label: 'Субподрядчики', hint: 'ИП, ООО, подрядчики' },
  { key: 'supply', label: 'Снабжение / склад', hint: 'снабженцы, кладовщики' },
  { key: 'accounting', label: 'Бухгалтерия', hint: 'бухгалтерия, офис' },
  { key: 'other', label: 'Прочие', hint: 'без категории' },
];

const staffGroupOrder = STAFF_SORT_GROUPS.reduce((acc, group, index) => ({ ...acc, [group.key]: index }), {});
const staffCollator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' });

const normalizeStaffText = (value) => String(value || '')
  .toLowerCase()
  .replaceAll('ё', 'е')
  .replace(/[_-]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

const staffTextHas = (text, words) => words.some(word => text.includes(word));

const getStaffGroupKey = (staffRow = {}) => {
  const text = normalizeStaffText([
    staffRow.systemRole,
    staffRow.role,
    staffRow.specialization,
    staffRow.category,
    staffRow.employmentType,
    staffRow.brigade,
  ].filter(Boolean).join(' '));

  if (staffTextHas(text, ['директор', 'зам директора', 'замдиректора', 'руководитель', 'управляющий'])) return 'management';
  if (staffTextHas(text, ['прораб', 'главный инженер', 'инженер', 'сметчик', 'пто', 'технадзор', 'стройконтроль'])) return 'engineering';
  if (staffTextHas(text, ['мастер', 'бригадир', 'отделочник', 'электрик', 'сантехник', 'монтажник', 'штукатур', 'маляр', 'плиточник'])) return 'masters';
  if (staffTextHas(text, ['субподрядчик', 'подрядчик', 'самозанятый', 'ип', 'ооо', 'организация'])) return 'contractors';
  if (staffTextHas(text, ['снабженец', 'снабжение', 'кладовщик', 'склад', 'логист'])) return 'supply';
  if (staffTextHas(text, ['бухгалтер', 'кассир', 'офис', 'кадры', 'юрист', 'документооборот'])) return 'accounting';
  return 'other';
};

const compareStaffRows = (a, b) => {
  const groupDiff = (staffGroupOrder[getStaffGroupKey(a)] ?? 99) - (staffGroupOrder[getStaffGroupKey(b)] ?? 99);
  if (groupDiff !== 0) return groupDiff;
  const specializationDiff = staffCollator.compare(a.specialization || a.category || '', b.specialization || b.category || '');
  if (specializationDiff !== 0) return specializationDiff;
  const roleDiff = staffCollator.compare(a.role || '', b.role || '');
  if (roleDiff !== 0) return roleDiff;
  return staffCollator.compare(a.name || '', b.name || '');
};

export default function PersonnelPage({
  C,
  ROLE_GROUPS,
  ROLE_LABELS,
  PD_CONSENT_TEXT,
  API,
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
  deleteStaff,
  editingItem,
  expandedMaster,
  expandedMasterProject,
  expandedPieceworkProject,
  expandedStaffId,
  estimatesList = [],
  fileSrc,
  findUserForStaff,
  fmtMeasure,
  inp,
  interimActs,
  isMobile = false,
  listSearch,
  masterProfiles,
  masterRatings,
  matchSearch,
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
  setNewStaff,
  setNewStaffDoc,
  setPersonnelTab,
  setShowForm,
  setShowPhotoModal,
  setShowStaffDocForm,
  setStaffProfile,
  setStaffExpandedSections,
  showForm,
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
  const [staffGroupFilter, setStaffGroupFilter] = React.useState('all');
  const [staffOpenGroups, setStaffOpenGroups] = React.useState({});
  const workPayTotal = (work) => Number(work.executionTotal ?? work.execution_total ?? 0);
  const emptyStaffForm = () => ({name:'',role:'',phone:'',salary:'',project:'',payType:'оклад',email:'',password:'',systemRole:'',lastName:'',firstName:'',middleName:'',birthDate:'',citizenship:'РФ',address:'',photoUrl:'',emailWork:'',emailPersonal:'',phoneExtra:'',passportSeries:'',passportNumber:'',passportIssuedBy:'',passportIssuedDate:'',inn:'',snils:'',specialization:'',category:'',employmentType:'',hiredDate:'',firedDate:'',status:'Активен',brigade:'',bankAccount:'',bankName:'',bankBik:'',bankCorr:'',ogrnip:'',cardNumber:'',signatureUrl:'',notes:'',assignedProjects:[],assignedPackages:[]});
  const appendStaffNote = (current, line) => {
    const base = String(current || '').trim();
    const addition = String(line || '').trim();
    if (!addition || base.includes(addition)) return base;
    return base ? base + '\n' + addition : addition;
  };
  const splitPassportData = (value = '') => {
    const match = String(value).match(/(\d{4})\s*(\d{6})/);
    return { passportSeries: match?.[1] || '', passportNumber: match?.[2] || '' };
  };
  const splitFullName = (value = '') => {
    const parts = String(value || '').replace(/^(?:ИП|ООО|АО|ПАО|ЗАО)\s+/i, '').trim().split(/\s+/).filter(Boolean);
    return {
      lastName: parts[0] || '',
      firstName: parts[1] || '',
      middleName: parts.slice(2).join(' '),
      name: parts.slice(0, 3).join(' '),
    };
  };
  const employmentTypeFromRecognition = (legalForm = '', docType = '') => {
    const text = (legalForm + ' ' + docType).toLowerCase();
    if (text.includes('самозан')) return 'Самозанятый';
    if (text.includes('ип')) return 'ИП';
    if (text.includes('юр') || text.includes('ооо')) return 'ООО';
    if (text.includes('физ')) return 'ГПХ';
    return '';
  };
  const staffPatchFromRecognition = (result, current = {}) => {
    const extracted = result?.extracted || {};
    const passport = splitPassportData(extracted.passportData);
    const employmentType = employmentTypeFromRecognition(extracted.legalForm, extracted.docType);
    let notes = current.notes || '';
    if (extracted.contractSubject) notes = appendStaffNote(notes, 'Предмет договора: ' + extracted.contractSubject);
    if (extracted.passportData && (!passport.passportSeries || !passport.passportNumber)) notes = appendStaffNote(notes, 'Паспортные данные: ' + extracted.passportData);
    const patch = {
      inn: extracted.inn || '',
      bankAccount: extracted.bankAccount || '',
      bankName: extracted.bank || '',
      bankBik: extracted.bik || '',
      bankCorr: extracted.corrAccount || '',
      ogrnip: extracted.ogrn || '',
      specialization: extracted.workType || '',
      role: extracted.workType || '',
      employmentType,
      passportSeries: passport.passportSeries,
      passportNumber: passport.passportNumber,
      notes,
    };
    if (extracted.counterpartyName && !current.name) Object.assign(patch, splitFullName(extracted.counterpartyName));
    return Object.fromEntries(Object.entries(patch).filter(([, value]) => value));
  };
  const applyStaffRecognition = (result) => {
    setNewStaff(prev => ({ ...prev, ...staffPatchFromRecognition(result, prev) }));
    setStaffExpandedSections(prev => ({ ...prev, docs: true, finance: true, extra: true }));
  };
  const applyStaffDocRecognition = (result) => {
    const extracted = result?.extracted || {};
    const titleParts = [extracted.docType, extracted.number ? '№ ' + extracted.number : '', extracted.counterpartyName].filter(Boolean);
    const notes = [extracted.contractSubject ? 'Предмет договора: ' + extracted.contractSubject : '', extracted.amount ? 'Сумма: ' + extracted.amount : ''].filter(Boolean).join('\n');
    setNewStaffDoc(prev => ({
      ...prev,
      docType: extracted.docType || prev.docType,
      title: titleParts.join(' ') || extracted.documentTitle || prev.title,
      fileUrl: result?.fileUrl || prev.fileUrl,
      signedAt: extracted.docDate || prev.signedAt,
      notes: appendStaffNote(prev.notes, notes),
    }));
  };
  const normalizeAccessList = (value) => Array.isArray(value) ? value.filter(Boolean) : [];
  const staffWorkScope = (s) => {
    const access = findUserForStaff(s);
    const packages = normalizeAccessList(access?.assignedPackages || access?.assigned_packages || s.assignedPackages || s.assigned_packages);
    return packages[0] || s.specialization || s.category || s.brigade || s.project || 'Без специализации';
  };
  const staffSectionsForGroup = (group) => {
    if (!['masters', 'contractors'].includes(group.key)) return [{ key: 'all', label: '', rows: group.rows }];
    const sections = new Map();
    group.rows.forEach((row) => {
      const scope = staffWorkScope(row);
      if (!sections.has(scope)) sections.set(scope, []);
      sections.get(scope).push(row);
    });
    return [...sections.entries()]
      .sort(([a], [b]) => staffCollator.compare(a, b))
      .map(([label, rows]) => ({ key: label, label, rows: rows.slice().sort(compareStaffRows) }));
  };
  const openStaffEdit = (s) => {
    const access = findUserForStaff(s);
    const accessProject = access?.projectName || access?.project_name || s.project || '';
    const assignedProjects = normalizeAccessList(access?.assignedProjects || access?.assigned_projects || s.assignedProjects || s.assigned_projects);
    const assignedPackages = normalizeAccessList(access?.assignedPackages || access?.assigned_packages || s.assignedPackages || s.assigned_packages);
    setEditingItem(s);
    setNewStaff({
      ...emptyStaffForm(),
      ...s,
      salary: String(s.salary || ''),
      project: s.project || accessProject,
      email: access?.email || s.emailWork || s.email || s.emailPersonal || '',
      emailWork: access?.email || s.emailWork || s.email || '',
      password: '',
      systemRole: access?.role || s.systemRole || '',
      assignedProjects: assignedProjects.length ? assignedProjects : (accessProject ? [accessProject] : []),
      assignedPackages
    });
    setStaffExpandedSections(prev => ({...prev, access: true}));
    setShowForm(true);
  };
  const estimatePackage = (est) => est?.workPackage || est?.work_package || 'Основная';
  const packageOptionsForProjects = (projectNames=[]) => {
    const names = Array.isArray(projectNames) ? projectNames.filter(Boolean) : [];
    const packages = (estimatesList||[])
      .filter(est => names.length===0 || names.includes(est.projectName||est.project_name||est.project||''))
      .map(estimatePackage)
      .filter(Boolean);
    return [...new Set(packages)].sort((a,b)=>a.localeCompare(b,'ru'));
  };
  const accessProjectRoles = ['прораб','технадзор','стройконтроль','мастер','субподрядчик','бригадир'];
  const packageAccessRoles = ['мастер','субподрядчик','бригадир','прораб','главный_инженер'];
  const formGrid2 = {display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr',gap:'10px'};
  const formGrid3 = {display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr 1fr',gap:'10px'};
  const fullWidthInput = {...inp,marginBottom:0,gridColumn:isMobile?'auto':'span 2'};
  const staffProfileGrid = {display:'grid',gridTemplateColumns:isMobile?'1fr':'repeat(auto-fit,minmax(200px,1fr))',gap:'10px',marginBottom:'14px'};
  const staffProfileDocsGrid = {display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr',gap:'14px'};
  const staffDocumentFormGrid = {display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr',gap:'6px',marginBottom:'6px'};
  const staffDocumentFileGrid = {display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr 1fr',gap:'6px',marginBottom:'6px'};
  const searchedStaff = staff
    .filter(s=>matchSearch(
      listSearch,
      s.name,
      s.role,
      s.project,
      s.specialization,
      s.systemRole,
      s.category,
      s.employmentType,
      s.brigade,
      s.email,
      s.emailWork,
      s.phone
    ))
    .slice()
    .sort(compareStaffRows);
  const filteredStaff = staffGroupFilter === 'all'
    ? searchedStaff
    : searchedStaff.filter(s => getStaffGroupKey(s) === staffGroupFilter);
  const visibleStaffLimit = isMobile ? 40 : filteredStaff.length;
  const visibleStaff = filteredStaff.slice(0, visibleStaffLimit);
  const staffGroupCounts = STAFF_SORT_GROUPS.reduce((acc, group) => {
    acc[group.key] = searchedStaff.filter(s => getStaffGroupKey(s) === group.key).length;
    return acc;
  }, { all: searchedStaff.length });
  const visibleStaffGroups = STAFF_SORT_GROUPS
    .map(group => ({ ...group, rows: visibleStaff.filter(s => getStaffGroupKey(s) === group.key) }))
    .filter(group => group.rows.length > 0);
  const isStaffGroupOpen = (groupKey) => Boolean(staffOpenGroups[groupKey]);
  const toggleStaffGroup = (groupKey) => setStaffOpenGroups(prev => ({ ...prev, [groupKey]: !prev[groupKey] }));
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
                            const pTotal=pWorks.reduce((s,w)=>s+workPayTotal(w),0);
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
                                        <b style={{fontSize:'12px',color:C.success}}>{workPayTotal(w).toLocaleString()+' ₽'}</b>
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
            <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewStaff(emptyStaffForm());}} style={btnO}><Plus size={14}/>Добавить</button>
          </div>
          {showForm&&(
            <div style={{...card,padding:'20px',marginBottom:'16px'}}>
              <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>👤 Основное</b>
              <div style={{...formGrid3,marginBottom:'10px'}}>
                <input placeholder='Фамилия *' value={newStaff.lastName} onChange={e=>setNewStaff({...newStaff,lastName:e.target.value,name:[e.target.value,newStaff.firstName,newStaff.middleName].filter(Boolean).join(' ')})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Имя *' value={newStaff.firstName} onChange={e=>setNewStaff({...newStaff,firstName:e.target.value,name:[newStaff.lastName,e.target.value,newStaff.middleName].filter(Boolean).join(' ')})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Отчество' value={newStaff.middleName} onChange={e=>setNewStaff({...newStaff,middleName:e.target.value,name:[newStaff.lastName,newStaff.firstName,e.target.value].filter(Boolean).join(' ')})} style={{...inp,marginBottom:0}}/>
              </div>
              <div style={{...formGrid2,marginBottom:'10px'}}>
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
                  <div style={formGrid2}>
                    <select value={newStaff.systemRole} onChange={e=>setNewStaff({...newStaff,systemRole:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>Системная роль</option>{Object.keys(ROLE_LABELS).filter(r=>!['заказчик','поставщик','system_owner'].includes(r)).map(r=><option key={r} value={r}>{ROLE_LABELS[r]}</option>)}</select>
                    <input type='email' placeholder='Email для входа' value={newStaff.email} onChange={e=>setNewStaff({...newStaff,email:e.target.value,emailWork:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='text' placeholder={editingItem ? 'Новый пароль (оставьте пустым, если не меняем)' : 'Пароль'} value={newStaff.password} onChange={e=>setNewStaff({...newStaff,password:e.target.value})} style={fullWidthInput}/>
                  </div>
                  {accessProjectRoles.includes(newStaff.systemRole)&&(()=>{const ap=newStaff.assignedProjects||[];return(
                    <div style={{marginTop:'10px',padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1px solid '+C.border}}>
                      <b style={{fontSize:'11px',color:C.text,display:'block',marginBottom:'6px'}}>📍 Назначить объекты (приказ директора)</b>
                      <p style={{color:C.textMuted,fontSize:'10px',margin:'0 0 8px'}}>Исполнитель увидит только назначенные объекты. Для мастера, субподрядчика и бригадира объект обязателен: без объекта рабочие данные не откроются.</p>
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
                  {packageAccessRoles.includes(newStaff.systemRole)&&(()=>{const selectedProjects=newStaff.assignedProjects?.length?newStaff.assignedProjects:(newStaff.project?[newStaff.project]:[]);const packages=packageOptionsForProjects(selectedProjects);const apk=newStaff.assignedPackages||[];return(
                    <div style={{marginTop:'10px',padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1px solid '+C.border}}>
                      <b style={{fontSize:'11px',color:C.text,display:'block',marginBottom:'6px'}}>📁 Пакеты работ и смет</b>
                      <p style={{color:C.textMuted,fontSize:'10px',margin:'0 0 8px'}}>Для электрика выбираем «Электрика», для вентиляции — «Вентиляция». Так мастер не увидит чужие сметы и работы.</p>
                      {packages.length===0?<p style={{color:C.textMuted,fontSize:'11px',margin:0}}>По выбранным объектам активных пакетов смет пока нет.</p>:(
                        <div style={{maxHeight:'150px',overflowY:'auto',display:'flex',flexWrap:'wrap',gap:'6px'}}>
                          {packages.map(pkg=>(
                            <label key={pkg} style={{display:'flex',alignItems:'center',gap:'6px',cursor:'pointer',padding:'5px 8px',borderRadius:'999px',border:'1px solid '+(apk.includes(pkg)?C.info:C.border),backgroundColor:apk.includes(pkg)?C.infoLight:'transparent'}}>
                              <input type='checkbox' checked={apk.includes(pkg)} onChange={()=>{const next=apk.includes(pkg)?apk.filter(n=>n!==pkg):[...apk,pkg];setNewStaff({...newStaff,assignedPackages:next});}}/>
                              <span style={{fontSize:'11px',color:C.text}}>{pkg}</span>
                            </label>
                          ))}
                        </div>
                      )}
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
                  <div style={formGrid2}>
                    <input placeholder='Паспорт серия' value={newStaff.passportSeries} onChange={e=>setNewStaff({...newStaff,passportSeries:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Паспорт номер' value={newStaff.passportNumber} onChange={e=>setNewStaff({...newStaff,passportNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Кем выдан' value={newStaff.passportIssuedBy} onChange={e=>setNewStaff({...newStaff,passportIssuedBy:e.target.value})} style={fullWidthInput}/>
                    <input type='date' placeholder='Дата выдачи' value={newStaff.passportIssuedDate} onChange={e=>setNewStaff({...newStaff,passportIssuedDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='date' placeholder='Дата рождения' value={newStaff.birthDate} onChange={e=>setNewStaff({...newStaff,birthDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='ИНН' value={newStaff.inn} onChange={e=>setNewStaff({...newStaff,inn:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='СНИЛС' value={newStaff.snils} onChange={e=>setNewStaff({...newStaff,snils:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Гражданство' value={newStaff.citizenship} onChange={e=>setNewStaff({...newStaff,citizenship:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Адрес проживания' value={newStaff.address} onChange={e=>setNewStaff({...newStaff,address:e.target.value})} style={fullWidthInput}/>
                  </div>
                </div>
              )}

              <div onClick={()=>setStaffExpandedSections(s=>({...s,finance:!s.finance}))} style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',cursor:'pointer',marginBottom:'6px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <b style={{fontSize:'12px',color:C.text}}>💰 Финансы (для выплат)</b>
                <span style={{fontSize:'14px',color:C.textSec}}>{staffExpandedSections.finance?'▾':'▸'}</span>
              </div>
              {staffExpandedSections.finance&&(
                <div style={{padding:'10px',marginBottom:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}>
                  <div style={formGrid2}>
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
                  <div style={formGrid2}>
                    <input placeholder='Email личный' value={newStaff.emailPersonal} onChange={e=>setNewStaff({...newStaff,emailPersonal:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Доп. телефон (родственник)' value={newStaff.phoneExtra} onChange={e=>setNewStaff({...newStaff,phoneExtra:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='date' placeholder='Дата приёма' value={newStaff.hiredDate} onChange={e=>setNewStaff({...newStaff,hiredDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='date' placeholder='Дата увольнения' value={newStaff.firedDate} onChange={e=>setNewStaff({...newStaff,firedDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Бригада/Подразделение' value={newStaff.brigade} onChange={e=>setNewStaff({...newStaff,brigade:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Категория/разряд' value={newStaff.category} onChange={e=>setNewStaff({...newStaff,category:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <textarea placeholder='Заметки' value={newStaff.notes} onChange={e=>setNewStaff({...newStaff,notes:e.target.value})} style={{...fullWidthInput,minHeight:'60px',fontFamily:'inherit'}}/>
                  </div>
                </div>
              )}

              <DocumentRecognitionPanel
                C={C}
                card={card}
                inp={inp}
                btnG={btnG}
                btnO={btnO}
                btnB={btnB}
                uploadPhoto={uploadPhoto}
                fileSrc={fileSrc}
                projectName={newStaff.project || newStaff.name || 'Персонал'}
                context="staff-documents"
                entityType="worker"
                currentFields={newStaff}
                onApplyExtracted={applyStaffRecognition}
                applyExtractedLabel="Заполнить сотрудника"
              />

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
          <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginBottom:'12px'}}>
            {[{key:'all',label:'Все',hint:'все сотрудники'}, ...STAFF_SORT_GROUPS].map(group => {
              const count = staffGroupCounts[group.key] || 0;
              if (group.key !== 'all' && count === 0) return null;
              const active = staffGroupFilter === group.key;
              return (
                <button
                  key={group.key}
                  onClick={() => setStaffGroupFilter(group.key)}
                  title={group.hint}
                  style={{
                    ...(active ? btnO : btnG),
                    padding: isMobile ? '8px 10px' : '7px 12px',
                    fontSize: isMobile ? '11px' : '12px',
                    lineHeight: 1.2,
                  }}
                >
                  {group.label} · {count}
                </button>
              );
            })}
          </div>
          {isMobile&&(
            <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
              {visibleStaffGroups.map(group => {
                const groupOpen = isStaffGroupOpen(group.key);
                return (
                <div key={group.key} style={{...card,overflow:'hidden'}}>
                  <div
                    onClick={() => toggleStaffGroup(group.key)}
                    role="button"
                    aria-expanded={groupOpen}
                    style={{padding:'12px 14px',backgroundColor:C.bg,borderBottom:groupOpen?'1.5px solid '+C.border:'none',cursor:'pointer'}}
                  >
                    <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'10px'}}>
                      <div>
                        <b style={{color:C.text,fontSize:'13px'}}>{group.label}</b>
                        {groupOpen&&<p style={{color:C.textMuted,fontSize:'11px',margin:'2px 0 0'}}>{group.hint}</p>}
                      </div>
                      <div style={{display:'flex',alignItems:'center',gap:'8px',color:C.textSec,fontSize:'12px',fontWeight:700}}>
                        <span>{group.rows.length}</span>
                        {groupOpen?<ChevronUp size={16}/>:<ChevronDown size={16}/>}
                      </div>
                    </div>
                  </div>
                  {groupOpen&&<div style={{display:'flex',flexDirection:'column'}}>
                    {staffSectionsForGroup(group).map(section => (
                      <React.Fragment key={section.key}>
                        {section.label&&(
                          <div style={{padding:'8px 14px',backgroundColor:C.bgWhite,borderBottom:'1px solid '+C.border,color:C.textSec,fontSize:'11px',fontWeight:800,letterSpacing:0,textTransform:'uppercase'}}>
                            {section.label} · {section.rows.length}
                          </div>
                        )}
                        {section.rows.map(s=>{
                          const hasAccess=findUserForStaff(s);
                          const isExp=expandedStaffId===s.id;
                          return (
                            <div key={s.id} style={{borderBottom:'1px solid '+C.border}}>
                              <div
                                onClick={()=>openStaffProfile(s)}
                                style={{padding:'12px 14px',display:'flex',gap:'10px',alignItems:'flex-start',cursor:'pointer',backgroundColor:isExp?C.bg:'transparent'}}
                              >
                                <div style={{width:'36px',height:'36px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,display:'flex',alignItems:'center',justifyContent:'center',color:C.text,fontWeight:800,flexShrink:0}}>
                                  {(s.name||'?').slice(0,1)}
                                </div>
                                <div style={{minWidth:0,flex:1}}>
                                  <b style={{display:'block',color:C.text,fontSize:'13px',lineHeight:1.25,overflowWrap:'anywhere'}}>{s.name||'Без имени'}</b>
                                  <p style={{color:C.textSec,margin:'3px 0 0',fontSize:'11px',lineHeight:1.35,overflowWrap:'anywhere'}}>
                                    {[s.role, s.specialization].filter(Boolean).join(' · ') || 'Должность не указана'}
                                  </p>
                                  <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginTop:'7px'}}>
                                    <span style={{padding:'3px 7px',borderRadius:'999px',backgroundColor:C.bgWhite,border:'1px solid '+C.border,color:C.textSec,fontSize:'10px'}}>{s.project||'Без объекта'}</span>
                                    <span style={{padding:'3px 7px',borderRadius:'999px',backgroundColor:C.bgWhite,border:'1px solid '+C.border,color:C.textSec,fontSize:'10px'}}>{s.payType==='сдельно'?'Сдельно':'Оклад'}</span>
                                    {staffWorkScope(s)&&<span style={{padding:'3px 7px',borderRadius:'999px',backgroundColor:C.bgWhite,border:'1px solid '+C.border,color:C.textSec,fontSize:'10px'}}>{staffWorkScope(s)}</span>}
                                  </div>
                                  <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'8px',marginTop:'9px'}}>
                                    <b style={{color:C.success,fontSize:'12px'}}>{calcSalary(s).toLocaleString()+' ₽'}</b>
                                    {hasAccess
                                      ? <span style={{padding:'3px 7px',borderRadius:'999px',backgroundColor:C.successLight,color:C.success,fontSize:'10px',fontWeight:700,maxWidth:'140px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>✅ {hasAccess.email||'доступ'}</span>
                                      : <span style={{padding:'3px 7px',borderRadius:'999px',backgroundColor:C.bgWhite,color:C.textMuted,fontSize:'10px'}}>без доступа</span>}
                                  </div>
                                </div>
                                <div style={{paddingTop:'2px',color:C.textSec,flexShrink:0}}>{isExp?<ChevronUp size={16}/>:<ChevronDown size={16}/>}</div>
                              </div>
                              {isExp&&(
                                <div style={{padding:'0 14px 12px 60px'}}>
                                  {staffProfileLoading?<p style={{color:C.textMuted,fontSize:'11px',margin:'0 0 10px'}}>Загрузка профиля...</p>:staffProfile?(
                                    <div style={{display:'grid',gap:'8px',marginBottom:'10px'}}>
                                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                                        <div style={{padding:'8px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Тип</p><b style={{fontSize:'11px',color:C.text}}>{s.employmentType||'не указан'}</b></div>
                                        <div style={{padding:'8px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>ИНН</p><b style={{fontSize:'11px',color:C.text}}>{s.inn||'не заполнен'}</b></div>
                                        <div style={{padding:'8px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Договоры</p><b style={{fontSize:'11px',color:C.text}}>{staffProfile.contracts.length}</b></div>
                                        <div style={{padding:'8px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Акты</p><b style={{fontSize:'11px',color:C.text}}>{staffProfile.acts.length}</b></div>
                                      </div>
                                    </div>
                                  ):<p style={{color:C.textMuted,fontSize:'11px',margin:'0 0 10px'}}>Не удалось загрузить профиль</p>}
                                  <div style={{display:'flex',gap:'6px',flexWrap:'wrap'}} onClick={e=>e.stopPropagation()}>
                                    {hasAccess
                                      ? <button onClick={()=>resetStaffAccessPassword(hasAccess,s)} style={{...btnG,padding:'6px 9px',fontSize:'11px'}}>🔑 Пароль</button>
                                      : <button onClick={()=>createStaffAccessFromPrompt(s)} style={{...btnB,padding:'6px 9px',fontSize:'11px'}}>🔐 Доступ</button>}
                                    <button onClick={()=>openStaffEdit(s)} style={{...btnG,padding:'6px 9px',fontSize:'11px'}}><Edit2 size={11}/>Изменить</button>
                                    <button onClick={()=>deleteStaff(s.id)} style={{...btnR,padding:'6px 9px',fontSize:'11px'}}><Trash2 size={11}/>Удалить</button>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </React.Fragment>
                    ))}
                  </div>}
                </div>
                );
              })}
            </div>
          )}
          {!isMobile&&(<table style={tbl}>
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
              {visibleStaffGroups.map(group => {
                const groupOpen = isStaffGroupOpen(group.key);
                return (
                <React.Fragment key={group.key}>
                  <tr onClick={() => toggleStaffGroup(group.key)} style={{cursor:'pointer'}}>
                    <td colSpan='8' style={{...tblC,backgroundColor:C.bg,borderTop:'1.5px solid '+C.border,borderBottom:'1.5px solid '+C.border}}>
                      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'8px',flexWrap:'wrap'}}>
                        <div style={{display:'flex',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
                          <b style={{color:C.text,fontSize:'12px'}}>{group.label}</b>
                          <span style={{color:C.textSec,fontSize:'11px'}}>· {group.rows.length}</span>
                          {groupOpen&&<span style={{color:C.textMuted,fontSize:'10px'}}>{group.hint}</span>}
                        </div>
                        <span style={{display:'inline-flex',alignItems:'center',gap:'6px',color:C.textSec,fontSize:'11px',fontWeight:700}}>
                          {groupOpen ? 'Свернуть' : 'Открыть'}
                          {groupOpen?<ChevronUp size={14}/>:<ChevronDown size={14}/>}
                        </span>
                      </div>
                    </td>
                  </tr>
                  {groupOpen&&staffSectionsForGroup(group).map(section => (
                    <React.Fragment key={section.key}>
                      {section.label&&(
                        <tr>
                          <td colSpan='8' style={{...tblC,backgroundColor:C.bgWhite,borderBottom:'1px solid '+C.border,padding:'8px 12px'}}>
                            <b style={{color:C.textSec,fontSize:'11px',textTransform:'uppercase',letterSpacing:0}}>{section.label} · {section.rows.length}</b>
                          </td>
                        </tr>
                      )}
                      {section.rows.map(s=>{
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
                              <button onClick={()=>openStaffEdit(s)} style={{...btnG,padding:'3px 7px'}}><Edit2 size={11}/></button>
                              <button onClick={()=>deleteStaff(s.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button>
                            </div>
                          </td>
                        </tr>
                        {isExp&&(
                          <tr>
                            <td colSpan='8' style={{padding:'14px 18px',backgroundColor:C.bg,borderBottom:'1.5px solid '+C.border}}>
                              {staffProfileLoading?<p style={{color:C.textMuted,fontSize:'12px'}}>⏳ Загрузка профиля...</p>:staffProfile?(
                                <div>
                                  <div style={staffProfileGrid}>
                                    <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Тип занятости</p><b style={{fontSize:'12px',color:C.text}}>{s.employmentType||'не указан'}</b></div>
                                    <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Паспорт</p><b style={{fontSize:'12px',color:C.text}}>{s.passportSeries||s.passportNumber?(s.passportSeries+' '+s.passportNumber):'не заполнен'}</b></div>
                                    <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>ИНН</p><b style={{fontSize:'12px',color:C.text}}>{s.inn||'не заполнен'}</b></div>
                                    <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Банк</p><b style={{fontSize:'12px',color:C.text}}>{s.bankName||'не указан'}</b></div>
                                  </div>

                              <div style={staffProfileDocsGrid}>
                                <div style={{...card,padding:'12px'}}>
                                  <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>📄 Договоры ({staffProfile.contracts.length})</b>
                                  {staffProfile.contracts.length===0?<p style={{color:C.textMuted,fontSize:'11px'}}>Договоров нет</p>:staffProfile.contracts.map(c=>(<div key={c.id} style={{padding:'6px 0',borderBottom:'1px solid '+C.border,fontSize:'11px'}}><b>№{c.contractNumber}</b> · {c.project} · {c.status||'-'}</div>))}
                                </div>
                                <div style={{...card,padding:'12px'}}>
                                  <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>📋 Акты ({staffProfile.acts.length})</b>
                                  {staffProfile.acts.length===0?<p style={{color:C.textMuted,fontSize:'11px'}}>Актов нет</p>:staffProfile.acts.map(a=>(<div key={a.id} style={{padding:'6px 0',borderBottom:'1px solid '+C.border,fontSize:'11px',display:'flex',justifyContent:'space-between',gap:'8px'}}><span>№{a.actNumber} · {a.project}{a.workPackage?' · '+a.workPackage:''}</span><b style={{color:C.success,whiteSpace:'nowrap'}}>{a.totalAmount.toLocaleString()} ₽</b></div>))}
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
                                    <div style={staffDocumentFormGrid}>
                                      <select value={newStaffDoc.docType} onChange={e=>setNewStaffDoc({...newStaffDoc,docType:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>
                                        {['Трудовой договор','Договор ГПХ','Договор с самозанятым','Договор с ИП','Приказ','Должн. инструкция','Мед. книжка','Справка о статусе самозанятого','Чек НПД','Прочее'].map(t=><option key={t}>{t}</option>)}
                                      </select>
                                      <input placeholder='Название/Номер' value={newStaffDoc.title} onChange={e=>setNewStaffDoc({...newStaffDoc,title:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    </div>
                                    <div style={staffDocumentFileGrid}>
                                      <input type='file' accept='image/*,.pdf' onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{projectName:s.project,context:'staff-documents'});setNewStaffDoc({...newStaffDoc,fileUrl:url});}}} style={{fontSize:'11px'}}/>
                                      <input type='date' value={newStaffDoc.signedAt} onChange={e=>setNewStaffDoc({...newStaffDoc,signedAt:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input type='date' placeholder='Истекает' value={newStaffDoc.expiresAt} onChange={e=>setNewStaffDoc({...newStaffDoc,expiresAt:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    </div>
                                    <DocumentRecognitionPanel
                                      C={C}
                                      card={card}
                                      inp={inp}
                                      btnG={btnG}
                                      btnO={btnO}
                                      btnB={btnB}
                                      uploadPhoto={uploadPhoto}
                                      fileSrc={fileSrc}
                                      projectName={s.project || s.name || 'Документы персонала'}
                                      context="staff-documents"
                                      entityType="staff_document"
                                      currentFields={newStaffDoc}
                                      onApplyExtracted={applyStaffDocRecognition}
                                      applyExtractedLabel="Заполнить документ"
                                    />
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
                                  {staffProfile.workJournal.slice(0,8).map((w,i)=>(<div key={i} style={{padding:'4px 0',borderBottom:'1px solid '+C.border,fontSize:'11px',display:'flex',justifyContent:'space-between'}}><span>{w.project} · {w.description} · {w.quantity} {w.unit}</span><b style={{color:C.success}}>{workPayTotal(w).toLocaleString()} ₽</b></div>))}
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
                    </React.Fragment>
                  ))}
                </React.Fragment>
                );
              })}
            </tbody>
          </table>)}
          {visibleStaff.length < filteredStaff.length&&(
            <div style={{padding:'12px',color:C.textMuted,fontSize:'12px',textAlign:'center'}}>
              Показаны первые {visibleStaff.length} из {filteredStaff.length}. Уточните поиск, чтобы быстрее найти сотрудника.
            </div>
          )}
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
                {visibleStaff.map(s=>(
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
            {visibleStaff.length < filteredStaff.length&&(
              <div style={{padding:'12px',color:C.textMuted,fontSize:'12px',textAlign:'center'}}>
                Показаны первые {visibleStaff.length} из {filteredStaff.length}. Уточните поиск для нужной бригады или сотрудника.
              </div>
            )}
          </div>
        </div>
      )}

      {personnelTab==='piecework'&&(
        <div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',gap:'12px',flexWrap:'wrap'}}>
            <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Сдельные начисления</b>
            <span style={{color:C.textSec,fontSize:'12px'}}>Формируются автоматически из подтверждённого ЖПР и актов</span>
          </div>
          <div style={{...card,padding:'14px',marginBottom:'16px',borderColor:C.warningBorder||C.border,backgroundColor:C.warningLight||C.bg}}>
            <b style={{color:C.warning||C.text,fontSize:'12px'}}>Ручное добавление отключено</b>
            <p style={{color:C.textSec,margin:'6px 0 0',fontSize:'12px',lineHeight:1.45}}>
              Чтобы начислить оплату мастеру или субподрядчику, исполнитель закрывает работу в ЖПР с помещением, руководитель подтверждает, затем бухгалтерия формирует акт закрытия.
            </p>
          </div>
          {visibleStaff.map(s=>{
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
                        <div style={{display:'flex',gap:'6px',alignItems:'center'}}><b style={{fontSize:'12px',color:C.success}}>{w.total.toLocaleString()+' ₽'}</b></div>
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
