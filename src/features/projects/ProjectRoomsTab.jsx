import React from 'react';
import { createDoorForm, createRoomForm, createWindowForm } from '../project-operations/projectOperationInitialForms';

export default function ProjectRoomsTab({ ctx, project }) {
  const p = project;
  const {
    C, Check, ChevronDown, ChevronUp, DOOR_PURPOSES, DOOR_TYPES, Edit2, PhotoAttachmentField,
    Plus, REVEAL_MATERIALS, Trash2, WINDOW_TYPES, X, activeProjectTab, appendPhotos, badge,
    btnG, btnGr, btnO, btnR, calcDoorArea, calcDoorReveals, calcWindowArea, calcWindowReveals,
    card, customRoomTypes, deleteDoor, deleteRoom, deleteWindow, draftRoomDoors, draftRoomWindows, editingDoor,
    editingItem, editingWindow, expandedRoom, fileSrc, getRoomNetWall, inp, isMobile, isProrab,
    newDoor, newRoom, newWindow, roomCompleteness, roomDoors, roomWindows, rooms, saveDoor,
    saveRoom, saveWindow, setDraftRoomDoors, setDraftRoomWindows, setEditingDoor, setEditingItem, setEditingWindow, setExpandedRoom,
    setNewDoor, setNewRoom, setNewWindow, setRoomDoors, setRoomWindows, setShowPhotoModal, setShowRoomForm, showRoomForm,
    updateDoor, updateWindow,
  } = ctx;

  return (
    <>
	                    {activeProjectTab==='Помещения'&&(<div>
	                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
	                        <b style={{color:C.text}}>Помещения</b>
                        {isProrab()&&<button onClick={()=>{setShowRoomForm(!showRoomForm);setEditingItem(null);setDraftRoomWindows([]);setDraftRoomDoors([]);setNewRoom(createRoomForm({project:p.name}));}} style={btnO}><Plus size={14}/>Добавить</button>}
                      </div>
                      {showRoomForm&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                          <input placeholder="Название помещения * (например: Кабинет 204)" value={newRoom.name} onChange={e=>setNewRoom({...newRoom,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Этаж (1,2,3...)" type="number" step="any" inputMode="decimal" value={newRoom.floor||''} onChange={e=>setNewRoom({...newRoom,floor:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Литер (А,Б,В...)" value={newRoom.liter||''} onChange={e=>setNewRoom({...newRoom,liter:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <select value={['Комната','Кабинет','Коридор','Санузел','Кухня','Балкон','Лестница','Холл','Техническое','Другое',...customRoomTypes].includes(newRoom.roomType||'Комната')?(newRoom.roomType||'Комната'):'Другое'} onChange={e=>setNewRoom({...newRoom,roomType:e.target.value})} style={{...inp,marginBottom:0}}>
                            {[...'Комната,Кабинет,Коридор,Санузел,Кухня,Балкон,Лестница,Холл,Техническое'.split(','),...customRoomTypes,'Другое'].map(t=><option key={t}>{t}</option>)}
                          </select>
                          {(newRoom.roomType==='Другое'||(!['Комната','Кабинет','Коридор','Санузел','Кухня','Балкон','Лестница','Холл','Техническое','Другое',''].includes(newRoom.roomType||'Комната')))&&<input placeholder='Свой тип помещения, например: Серверная' value={newRoom.roomType==='Другое'?'':newRoom.roomType||''} onChange={e=>setNewRoom({...newRoom,roomType:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>}
                          <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={newRoom.height} onChange={e=>setNewRoom({...newRoom,height:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь пола (м2)" type="number" step="any" inputMode="decimal" value={newRoom.floorArea} onChange={e=>setNewRoom({...newRoom,floorArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь стен (м2)" type="number" step="any" inputMode="decimal" value={newRoom.wallArea} onChange={e=>setNewRoom({...newRoom,wallArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь потолка (м2)" type="number" step="any" inputMode="decimal" value={newRoom.ceilingArea} onChange={e=>setNewRoom({...newRoom,ceilingArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        {(()=>{
                          const existingWins = editingItem ? roomWindows.filter(w=>Number(w.room_id)===Number(editingItem.id)) : [];
                          const existingDoors = editingItem ? roomDoors.filter(d=>Number(d.room_id)===Number(editingItem.id)) : [];
                          const draftOpeningsArea = draftRoomWindows.reduce((s,w)=>s+calcWindowArea(w),0)+draftRoomDoors.reduce((s,d)=>s+calcDoorArea(d),0);
                          const draftWindowReveals = draftRoomWindows.reduce((s,w)=>s+calcWindowReveals(w),0);
                          const draftDoorReveals = draftRoomDoors.reduce((s,d)=>s+calcDoorReveals(d),0);
                          const draftNetWall = Math.max(0, Number(newRoom.wallArea||0)-draftOpeningsArea);
                          return (
                            <div style={{marginTop:'10px',padding:'12px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
                              <div style={{display:'flex',justifyContent:'space-between',gap:'10px',alignItems:'flex-start',marginBottom:'10px',flexWrap:'wrap'}}>
                                <div>
                                  <b style={{color:C.text,fontSize:'13px'}}>Окна, двери и откосы</b>
                                  <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>Окна и двери вычитаются из стен. Откосы считаются отдельной площадью.</p>
                                </div>
                                {!editingItem&&<div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
                                  <span style={badge(C.info,C.infoLight,C.infoBorder)}>{'Чистые стены: '+draftNetWall.toFixed(2)+' м2'}</span>
                                  <span style={badge(C.accent,C.accentLight,C.accentBorder)}>{'Откосы: '+(draftWindowReveals+draftDoorReveals).toFixed(2)+' м2'}</span>
                                </div>}
                              </div>
                              {editingItem?(
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border,flexWrap:'wrap'}}>
                                  <span style={{color:C.textSec,fontSize:'12px'}}>{'Сейчас в помещении: окон '+existingWins.length+', дверей '+existingDoors.length+'. Для правки размеров раскройте карточку помещения ниже.'}</span>
                                  <button onClick={()=>{setExpandedRoom(editingItem.id);setShowRoomForm(false);}} style={{...btnG,padding:'6px 10px',fontSize:'12px'}}>Открыть окна/двери</button>
                                </div>
                              ):(
                                <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr',gap:'10px'}}>
                                  <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}>
                                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px',gap:'8px'}}>
                                      <b style={{color:C.text,fontSize:'12px'}}>Окна</b>
                                      <button onClick={()=>setDraftRoomWindows(prev=>[...prev,{name:'Окно '+(prev.length+1),width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'}])} style={{...btnO,padding:'4px 8px',fontSize:'11px'}}><Plus size={11}/>Окно</button>
                                    </div>
                                    {draftRoomWindows.length===0&&<p style={{color:C.textMuted,fontSize:'11px',margin:'0'}}>Окон нет</p>}
                                    {draftRoomWindows.map((w,idx)=>(<div key={'draft-window-'+idx} style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'1.1fr .9fr .8fr .8fr .8fr 34px',gap:'6px',alignItems:'center',marginBottom:'6px'}}>
                                      <input placeholder="Название" value={w.name} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,name:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <select value={w.windowType||'ПВХ'} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,windowType:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}>{WINDOW_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Шир., м" type="number" step="any" inputMode="decimal" value={w.width} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,width:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Выс., м" type="number" step="any" inputMode="decimal" value={w.height} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,height:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Откос, см" type="number" step="any" inputMode="decimal" value={w.revealDepth} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,revealDepth:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <button onClick={()=>setDraftRoomWindows(prev=>prev.filter((_,i)=>i!==idx))} style={{...btnR,padding:'7px'}}><Trash2 size={11}/></button>
                                    </div>))}
                                  </div>
                                  <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}>
                                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px',gap:'8px'}}>
                                      <b style={{color:C.text,fontSize:'12px'}}>Двери</b>
                                      <button onClick={()=>setDraftRoomDoors(prev=>[...prev,{name:'Дверь '+(prev.length+1),width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'}])} style={{...btnO,padding:'4px 8px',fontSize:'11px'}}><Plus size={11}/>Дверь</button>
                                    </div>
                                    {draftRoomDoors.length===0&&<p style={{color:C.textMuted,fontSize:'11px',margin:'0'}}>Дверей нет</p>}
                                    {draftRoomDoors.map((d,idx)=>(<div key={'draft-door-'+idx} style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'1.1fr .9fr .8fr .8fr .8fr 34px',gap:'6px',alignItems:'center',marginBottom:'6px'}}>
                                      <input placeholder="Название" value={d.name} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,name:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <select value={d.doorPurpose||'Межкомнатная'} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,doorPurpose:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}>{DOOR_PURPOSES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Шир., м" type="number" step="any" inputMode="decimal" value={d.width} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,width:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Выс., м" type="number" step="any" inputMode="decimal" value={d.height} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,height:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Откос, см" type="number" step="any" inputMode="decimal" value={d.revealDepth} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,revealDepth:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <button onClick={()=>setDraftRoomDoors(prev=>prev.filter((_,i)=>i!==idx))} style={{...btnR,padding:'7px'}}><Trash2 size={11}/></button>
                                    </div>))}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })()}
                        <div style={{marginTop:'8px'}}>
                          <PhotoAttachmentField
                            C={C}
                            btnG={btnG}
                            value={newRoom.photoUrl || ''}
                            onChange={photoUrl => setNewRoom({...newRoom, photoUrl})}
                            appendPhotos={appendPhotos}
                            fileSrc={fileSrc}
                            setShowPhotoModal={setShowPhotoModal}
                            projectName={p.name}
                            context="room-measurements"
                            title="Фото помещения / лист замера"
                          />
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}><button onClick={saveRoom} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button><button onClick={()=>{setShowRoomForm(false);setEditingItem(null);setDraftRoomWindows([]);setDraftRoomDoors([]);}} style={btnG}><X size={14}/>Отмена</button></div>
                  </div>)}
                      {(()=>{const projectRooms=rooms.filter(r=>r.project===p.name);if(projectRooms.length===0)return null;const checked=projectRooms.map(roomCompleteness);const full=checked.filter(x=>x.status==='Обмер полный').length;const missing=checked.filter(x=>x.status==='Не хватает данных').length;const openings=checked.filter(x=>x.status==='Проверить проёмы').length;return(<div style={{...card,padding:'12px',marginBottom:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
                        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'repeat(4,1fr)',gap:'8px'}}>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Помещений</p><b style={{color:C.text,fontSize:'16px'}}>{projectRooms.length}</b></div>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.successLight,border:'1px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'10px',margin:'0 0 3px'}}>Обмер полный</p><b style={{color:C.success,fontSize:'16px'}}>{full}</b></div>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:missing?C.warningLight:C.bg,border:'1px solid '+(missing?C.warningBorder:C.border)}}><p style={{color:missing?C.warning:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Дозаполнить</p><b style={{color:missing?C.warning:C.text,fontSize:'16px'}}>{missing}</b></div>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:openings?C.infoLight:C.bg,border:'1px solid '+(openings?C.infoBorder:C.border)}}><p style={{color:openings?C.info:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Проёмы/откосы</p><b style={{color:openings?C.info:C.text,fontSize:'16px'}}>{openings}</b></div>
                        </div>
                      </div>);})()}
                      {rooms.filter(r=>r.project===p.name).map(room=>{
                        const wins=roomWindows.filter(w=>Number(w.room_id)===Number(room.id));
                        const doors=roomDoors.filter(d=>Number(d.room_id)===Number(room.id));
                        const netWall=getRoomNetWall(room);
                        const winRevTotal=wins.reduce((s,w)=>s+calcWindowReveals(w),0);
                        const doorRevTotal=doors.reduce((s,d)=>s+calcDoorReveals(d),0);
                        const isRoomOpen=expandedRoom===room.id;
                        const completeness=roomCompleteness(room);
                        const roomPhotos=String(room.photoUrl||room.photo_url||'').split(',').map(url=>url.trim()).filter(Boolean);
                        return(<div key={room.id} style={{...card,marginBottom:'10px'}}>
                          <div style={{padding:'14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={()=>setExpandedRoom(isRoomOpen?null:room.id)}>
                            <div style={{minWidth:0,flex:1}}><b style={{color:C.text,fontSize:'13px'}}>{room.name}</b>{room.floor&&<span style={{fontSize:'11px',color:C.accent,marginLeft:'6px',padding:'1px 6px',backgroundColor:C.accentLight,borderRadius:'4px'}}>{'Эт.'+room.floor+(room.liter?' Лит.'+room.liter:'')}</span>}{room.roomType&&<span style={{fontSize:'11px',color:C.textSec,marginLeft:'4px'}}>{'· '+room.roomType}</span>}<span style={{...badge(completeness.color,completeness.bg,completeness.border),marginLeft:'6px'}}>{completeness.status}</span><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{'Пол: '+room.floorArea+'м² · Стены: '+room.wallArea+'м² (чистые: '+netWall+'м²) · Потолок: '+room.ceilingArea+'м² · Высота: '+(room.height||'—')+'м'}</p><p style={{color:C.textSec,margin:'0',fontSize:'11px'}}>{'Окна: '+wins.length+'шт · Двери: '+doors.length+'шт'+(winRevTotal>0?' · Откосы окон: '+winRevTotal+'м²':'')+(doorRevTotal>0?' · Откосы дверей: '+doorRevTotal+'м²':'')}</p>{roomPhotos.length>0&&<div style={{display:'flex',gap:'4px',flexWrap:'wrap',marginTop:'6px'}}>{roomPhotos.slice(0,4).map((url,index)=><img key={url+index} src={fileSrc(url)} alt='' onClick={e=>{e.stopPropagation();setShowPhotoModal(fileSrc(url));}} style={{width:'44px',height:'44px',objectFit:'cover',borderRadius:'6px',cursor:'pointer',border:'1px solid '+C.border}}/>)}{roomPhotos.length>4&&<span style={{fontSize:'11px',color:C.textSec,alignSelf:'center'}}>+{roomPhotos.length-4}</span>}</div>}{completeness.issues.length>0&&<p style={{color:completeness.color,margin:'3px 0 0',fontSize:'11px',fontWeight:'600'}}>{'Нужно: '+completeness.issues.slice(0,4).join(', ')+(completeness.issues.length>4?' …':'')}</p>}</div>
                            <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                              {isProrab()&&(<><button onClick={e=>{e.stopPropagation();setEditingItem(room);setDraftRoomWindows([]);setDraftRoomDoors([]);setNewRoom({project:room.project,name:room.name,floor:room.floor||'',liter:room.liter||'',roomType:room.roomType||'Комната',floorArea:room.floorArea,wallArea:room.wallArea,ceilingArea:room.ceilingArea,height:room.height||'',ceilingType:room.ceiling_type||room.ceilingType||'Простой',wallMaterial:room.wall_material||room.wallMaterial||'Штукатурка',floorMaterial:room.floor_material||room.floorMaterial||'Стяжка',photoUrl:room.photoUrl||room.photo_url||'',notes:room.notes||''});setShowRoomForm(true);}} style={{...btnG,padding:'4px 8px'}}><Edit2 size={11}/></button><button onClick={e=>{e.stopPropagation();deleteRoom(room.id);}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button></>)}
                              {isRoomOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}
                            </div>
                          </div>
                          {isRoomOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'14px'}}>
                            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
                              <div>
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px'}}>
                                  <b style={{color:C.text,fontSize:'13px'}}>🪟 Окна</b>
                                  <button onClick={()=>setNewWindow(createWindowForm({roomId:room.id,name:'Окно '+(wins.length+1)}))} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><Plus size={11}/>Добавить</button>
                                </div>
                                {wins.map(w=>(<div key={w.id} style={{padding:'8px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}>
                                  {editingWindow===w.id?(<div>
                                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                      <input placeholder="Название" value={w.name} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,name:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={w.window_type||w.windowType||'ПВХ'} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,window_type:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{WINDOW_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={w.width} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,width:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={w.height} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,height:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={w.reveal_depth||w.revealDepth||''} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,reveal_depth:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={w.reveal_material||w.revealMaterial||'Штукатурка'} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,reveal_material:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                    </div>
                                    <div style={{display:'flex',gap:'6px'}}><button onClick={()=>updateWindow(w)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Сохранить</button><button onClick={()=>setEditingWindow(null)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                                  </div>):(<div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                                    <div><b style={{fontSize:'12px',color:C.text}}>{w.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{(w.window_type||w.windowType||'ПВХ')+' '+w.width+'×'+w.height+'м = '+calcWindowArea(w).toFixed(2)+'м²'}</p>{calcWindowReveals(w)>0&&<p style={{color:C.info,margin:'0',fontSize:'10px'}}>{'Откосы: '+calcWindowReveals(w).toFixed(2)+'м² ('+((w.reveal_depth||w.revealDepth)||0)+'см)'}</p>}</div>
                                    <div style={{display:'flex',gap:'4px'}}><button onClick={()=>setEditingWindow(w.id)} style={{...btnG,padding:'3px 7px'}}><Edit2 size={10}/></button><button onClick={()=>deleteWindow(w.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={10}/></button></div>
                  </div>)}
                                </div>))}
                                {newWindow.roomId===room.id&&(<div style={{padding:'10px',backgroundColor:C.accentLight,borderRadius:'8px',border:'1.5px solid '+C.accentBorder}}>
                                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                    <input placeholder="Название" value={newWindow.name} onChange={e=>setNewWindow({...newWindow,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newWindow.windowType} onChange={e=>setNewWindow({...newWindow,windowType:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{WINDOW_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                    <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={newWindow.width} onChange={e=>setNewWindow({...newWindow,width:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={newWindow.height} onChange={e=>setNewWindow({...newWindow,height:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={newWindow.revealDepth} onChange={e=>setNewWindow({...newWindow,revealDepth:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newWindow.revealMaterial} onChange={e=>setNewWindow({...newWindow,revealMaterial:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                  </div>
                                  <div style={{display:'flex',gap:'6px'}}><button onClick={()=>saveWindow(room.id)} style={{...btnO,padding:'5px 12px',fontSize:'11px'}}><Check size={11}/>Добавить</button><button onClick={()=>setNewWindow(createWindowForm())} style={{...btnG,padding:'5px 12px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                  </div>)}
                              </div>
                              <div>
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px'}}>
                                  <b style={{color:C.text,fontSize:'13px'}}>🚪 Двери</b>
                                  <button onClick={()=>setNewDoor(createDoorForm({roomId:room.id,name:'Дверь '+(doors.length+1)}))} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><Plus size={11}/>Добавить</button>
                                </div>
                                {doors.map(d=>(<div key={d.id} style={{padding:'8px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}>
                                  {editingDoor===d.id?(<div>
                                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                      <input placeholder="Название" value={d.name} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,name:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={d.door_type||d.doorType||'Деревянная'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,door_type:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                      <select value={d.door_purpose||d.doorPurpose||'Межкомнатная'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,door_purpose:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_PURPOSES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={d.width} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,width:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={d.height} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,height:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={d.reveal_depth||d.revealDepth||''} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,reveal_depth:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={d.reveal_material||d.revealMaterial||'Штукатурка'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,reveal_material:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                    </div>
                                    <div style={{display:'flex',gap:'6px'}}><button onClick={()=>updateDoor(d)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Сохранить</button><button onClick={()=>setEditingDoor(null)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                                  </div>):(<div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                                    <div><b style={{fontSize:'12px',color:C.text}}>{d.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{(d.door_type||d.doorType||'')+(d.door_purpose||d.doorPurpose?'/'+(d.door_purpose||d.doorPurpose):'')+ ' '+d.width+'×'+d.height+'м = '+calcDoorArea(d).toFixed(2)+'м²'}</p>{calcDoorReveals(d)>0&&<p style={{color:C.info,margin:'0',fontSize:'10px'}}>{'Откосы: '+calcDoorReveals(d).toFixed(2)+'м² ('+((d.reveal_depth||d.revealDepth)||0)+'см)'}</p>}</div>
                                    <div style={{display:'flex',gap:'4px'}}><button onClick={()=>setEditingDoor(d.id)} style={{...btnG,padding:'3px 7px'}}><Edit2 size={10}/></button><button onClick={()=>deleteDoor(d.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={10}/></button></div>
                  </div>)}
                                </div>))}
                                {newDoor.roomId===room.id&&(<div style={{padding:'10px',backgroundColor:C.accentLight,borderRadius:'8px',border:'1.5px solid '+C.accentBorder}}>
                                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                    <input placeholder="Название" value={newDoor.name} onChange={e=>setNewDoor({...newDoor,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newDoor.doorType} onChange={e=>setNewDoor({...newDoor,doorType:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                    <select value={newDoor.doorPurpose} onChange={e=>setNewDoor({...newDoor,doorPurpose:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_PURPOSES.map(t=><option key={t}>{t}</option>)}</select>
                                    <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={newDoor.width} onChange={e=>setNewDoor({...newDoor,width:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={newDoor.height} onChange={e=>setNewDoor({...newDoor,height:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={newDoor.revealDepth} onChange={e=>setNewDoor({...newDoor,revealDepth:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newDoor.revealMaterial} onChange={e=>setNewDoor({...newDoor,revealMaterial:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                  </div>
                                  <div style={{display:'flex',gap:'6px'}}><button onClick={()=>saveDoor(room.id)} style={{...btnO,padding:'5px 12px',fontSize:'11px'}}><Check size={11}/>Добавить</button><button onClick={()=>setNewDoor(createDoorForm())} style={{...btnG,padding:'5px 12px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                  </div>)}
                              </div>
                            </div>
                  </div>)}
                        </div>);
                      })}
                      {rooms.filter(r=>r.project===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Помещений нет</p>}
                  </div>)}
    </>
  );
}
