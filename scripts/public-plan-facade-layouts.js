// Authored concept layouts inferred from the catalog renders, not measured plans.
// Coordinates: rear at top, the primary facade at bottom; x increases to the right.
const room = (id,x,y,w,h,label,type,windows=[],extra={}) => ({id,x,y,w,h,label,type,windows,...extra});
const terrace = (x,y,w,h,label='Терраса',extra={}) => ({x,y,w,h,label,type:'terrace',outdoor:true,...extra});
const stairs = (x,y,w=2.2,h=3.4) => room('stairs',x,y,w,h,'Лестница','hall',[],{fixtures:[{type:'u-stairs',x:.08,y:.06,w:.84,h:.88}]});
const layouts = {};
function put(slug,floor,rooms,outdoor=[],extra={}) { layouts[`${slug}/${floor}`]={rooms,outdoor,...extra}; }

// Single-storey bay house: enclosed bay at the front, entrance to its right.
put('b1-02',1,[
  room('bed1',0,0,3.6,3.6,'Спальня 1','bed',['top','left']),
  room('bed2',3.6,0,3.6,3.6,'Спальня 2','bed',['top']),
  room('bed3',7.2,0,3.8,3.6,'Спальня 3','bed',['top','right']),
  room('hall',0,3.6,11,1.3,'Холл','hall'),
  room('living',0,4.9,6.4,4.1,'Кухня-гостиная','living',['left','bottom']),
  room('bath',6.4,4.9,2.2,2.2,'Ванная','bath'),
  room('entry',6.4,7.1,2.2,1.9,'Прихожая','hall',[],{entrySide:'bottom'}),
  room('office',8.6,4.9,2.4,2.4,'Кабинет','work',['right']),
  room('shower',8.6,7.3,2.4,1.7,'Душевая','bath',['right']),
  room('bay',1.3,9,3.8,1.1,'Эркер гостиной','living',['bottom','left','right'],{fixtures:[],openTo:'living'}),
], [terrace(6.4,9,2.2,1.1,'Крыльцо',{porch:true})]);

// Front-left recessed terrace; the living room occupies the projecting right wing.
put('b1-03',1,[
  room('bed1',0,0,3.5,3.6,'Спальня 1','bed',['top','left']),
  room('bed2',3.5,0,3.5,3.6,'Спальня 2','bed',['top']),
  room('bed3',7,0,3.5,3.6,'Спальня 3','bed',['top']),
  room('bath',10.5,0,2.5,3.6,'Ванная','bath',['right']),
  room('hall',0,3.6,13,1.3,'Холл','hall'),
  room('guest',0,4.9,3.5,3.2,'Гостевая спальня','bed',['left']),
  room('entry',3.5,4.9,2.2,3.2,'Прихожая','hall',[],{entrySide:'bottom'}),
  room('shower',5.7,4.9,2.1,1.8,'Душевая','bath'),
  room('utility',5.7,6.7,2.1,1.4,'Хозблок','service'),
  room('living',7.8,4.9,5.2,5.3,'Кухня-гостиная','living',['bottom','right']),
], [terrace(0,8.1,7.8,2.1,'Крытая терраса',{access:'living'})]);

// High central living volume is one storey with a double-height ceiling, no staircase.
put('fam-02',1,[
  room('bed1',0,0,3.8,3.6,'Спальня 1','bed',['top','left']),
  room('bed2',3.8,0,3.8,3.6,'Спальня 2','bed',['top']),
  room('bed3',7.6,0,3.8,3.6,'Спальня 3','bed',['top']),
  room('bath',11.4,0,2.6,3.6,'Ванная','bath',['right']),
  room('hall',0,3.6,14,1.3,'Холл','hall'),
  room('office',0,4.9,3.8,3.1,'Кабинет','work',['left']),
  room('living',3.8,4.9,6,5.3,'Кухня-гостиная · второй свет','living',['bottom'],{windowWidths:{bottom:4.2}}),
  room('shower',9.8,4.9,2,2.2,'Душевая','bath'),
  room('utility',11.8,4.9,2.2,2.2,'Постирочная','service',['right']),
  room('entry',9.8,7.1,4.2,3.1,'Прихожая','hall',['right'],{entrySide:'bottom'}),
], [terrace(0,8,3.8,2.2,'Крытая терраса',{access:'living'})]);

// Three front volumes: two bedroom wings flank the recessed terrace.
put('fam-03',1,[
  room('bed1',0,0,3.7,3.7,'Спальня 1','bed',['top','left']),
  room('bed2',3.7,0,3.7,3.7,'Спальня 2','bed',['top']),
  room('bed3',7.4,0,3.7,3.7,'Спальня 3','bed',['top']),
  room('bath',11.1,0,2.9,3.7,'Ванная','bath',['right']),
  room('hall',0,3.7,14,1.3,'Холл','hall'),
  room('bed4',0,5,3.7,5.8,'Спальня 4','bed',['left','bottom']),
  room('living',3.7,5,6.6,3.5,'Кухня-гостиная','living',['bottom'],{windowWidths:{bottom:3.6}}),
  room('entry',10.3,5,1.3,5.8,'Прихожая','hall',[],{entrySide:'bottom'}),
  room('shower',11.6,5,2.4,2.1,'Душевая','bath',['right']),
  room('guest',11.6,7.1,2.4,3.7,'Гостевая','bed',['bottom','right']),
], [terrace(3.7,8.5,6.6,2.3,'Крытая терраса',{access:'living'})]);

// Main two-storey body on the left, single-storey garage on the right.
function garageHouse(slug,w,d,gw,workshop=false) {
  const sx=w-2.2, rear=3.4, strip=1.3, front=rear+strip;
  const split=sx-1.7;
  const base=[
    room('kitchen',0,0,split,rear,'Кухня','kitchen',['top','left']),
    room('bath',split,0,1.7,rear,'Душевая','bath',['top']),
    stairs(sx,0),
    room('hall',0,rear,w,strip,'Холл','hall'),
    room('living',0,front,sx,d-front,'Гостиная-столовая','living',['bottom','left']),
    room('entry',sx,front,2.2,d-front,'Прихожая / шлюз','hall',[],{entrySide:'bottom'}),
    room('garage',w,d-6,gw,6,gw>5?'Гараж · 2 автомобиля':'Гараж','garage',['right'],{gateSide:'bottom',gateWidth:gw>5?5:2.7,fixtures:gw>5?[{type:'car',x:.09,y:.08,w:.34,h:.73},{type:'car',x:.57,y:.08,w:.34,h:.73}]:[{type:'car',x:.18,y:.08,w:.64,h:.73}]}),
  ];
  if(workshop) base.push(room('workshop',w,0,gw,d-6,'Мастерская','work',['top','right'],{connectOnly:['garage'],fixtures:[{type:'desks',x:.08,y:.08,w:.8,h:.33,rows:1,cols:2},{type:'wardrobe',x:.76,y:.5,w:.17,h:.32}]}));
  // Access to the garage through an entrance vestibule, never through a bedroom/bathroom.
  base.find(r=>r.id==='garage').connectOnly=['entry',...(workshop?['workshop']:[])];
  if(workshop) {
    base[0]=room('guest',0,0,split,rear,'Гостевая спальня','bed',['top','left']);
    base.find(r=>r.id==='living').label='Кухня-гостиная';
  }
  put(slug,1,base,[terrace(-2,front,2,d-front,'Терраса',{access:'living'})]);
  put(slug,2,[
    room('bed1',0,0,split,rear,'Спальня 1','bed',['top','left']),
    room('bath',split,0,1.7,rear,'Ванная','bath',['top']),
    stairs(sx,0),
    room('hall',0,rear,w,strip,'Холл','hall'),
    room('master',0,front,w/2,d-front,'Мастер-спальня','bed',['bottom','left']),
    room('bed2',w/2,front,w/2,d-front,'Спальня 2','bed',['bottom','right']),
  ],[terrace(w,workshop?0:d-6,gw,workshop?d:6,'Кровля гаража',{roof:true})]);
}
garageHouse('gar-01',6.6,8.6,3.6);
garageHouse('gar-02',7.6,9.4,6.2);
garageHouse('gar-03',8.4,10.2,4,true);

// Tall glazing is assigned to the stair hall; stairs align on both floors.
// A single balcony on the left sits over the covered ground-floor terrace.
const h2base=[
  room('kitchen',0,0,3.8,3.5,'Кухня-столовая','kitchen',['top','left']),
  room('guest',3.8,0,3.5,3.5,'Гостевая спальня','bed',['top']),
  room('bath',7.3,0,2.3,3.5,'Душевая / постирочная','bath',['top','right']),
  room('hall',0,3.5,9.6,1.3,'Холл','hall'),
  room('living',0,4.8,5,4.2,'Гостиная','living',['bottom','left']),
  {...stairs(5,4.8,2.3,4.2),windows:['bottom'],windowWidths:{bottom:1.8},connectOnly:['hall'],fixtures:[{type:'u-stairs',x:.08,y:.06,w:.84,h:.88,rotation:180}]},
  room('entry',7.3,4.8,2.3,4.2,'Прихожая','hall',['right'],{entrySide:'bottom'}),
];
put('h2-02',1,h2base,[terrace(-2.3,4.8,2.3,4.2,'Крытая терраса',{access:'living'})]);
put('h2-02',2,[
  room('bed1',0,0,3.8,3.5,'Спальня 1','bed',['top','left']),
  room('bed2',3.8,0,3.5,3.5,'Спальня 2','bed',['top']),
  room('bath',7.3,0,2.3,3.5,'Ванная','bath',['top','right']),
  room('hall',0,3.5,9.6,1.3,'Холл','hall'),
  room('master',0,4.8,5,4.2,'Мастер-спальня','bed',['bottom','left']),
  {...stairs(5,4.8,2.3,4.2),windows:['bottom'],windowWidths:{bottom:1.8},connectOnly:['hall'],fixtures:[{type:'u-stairs',x:.08,y:.06,w:.84,h:.88,rotation:180}]},
  room('wardrobe',7.3,4.8,2.3,4.2,'Гардеробная','service',['right']),
],[terrace(-2.3,4.8,2.3,4.2,'Балкон',{access:'master'})]);

// Attached townhouse: no windows in party walls, same footprint and stair shaft.
function townhouse(slug,w,d,threeBedrooms,office=false) {
  const rear=threeBedrooms?3.2:2.8, sy=rear+1.2, sx=w-2.2, sh=3.2, end=sy+sh;
  const first=[
    room('living',0,0,w,rear,'Кухня-гостиная','living',['top']),
    room('hall',0,rear,w,1.2,'Холл','hall'),
    room('passage',0,sy,1,sh,'Коридор','hall',[],{fixtures:[]}),
    room('bath',1,sy,sx-1,1.7,'Душевая','bath'),
    room('landing',1,sy+1.7,sx-1,sh-1.7,'Лестничный холл','hall',[],{fixtures:[],openTo:'stairs'}),
    {...stairs(sx,sy,2.2,sh),connectOnly:['landing']},
    room('entry',0,end,w,d-end,'Прихожая','hall',['bottom'],{entrySide:'bottom'}),
  ];
  // Office faces the street instead of an internal blind space.
  if(office) {
    first[first.length-1]=room('entry',sx,end,2.2,d-end,'Прихожая','hall',[],{entrySide:'bottom'});
    first.push(room('office',0,end,sx,d-end,'Кабинет','work',['bottom']));
  }
  const upper=[
    room('bed1',0,0,threeBedrooms?w/2:w,rear,'Спальня 1','bed',['top']),
    ...(threeBedrooms?[room('bed2',w/2,0,w/2,rear,'Спальня 2','bed',['top'])]:[]),
    room('hall',0,rear,w,1.2,'Холл','hall'),
    room('passage',0,sy,1,sh,'Коридор','hall',[],{fixtures:[]}),
    room('bath',1,sy,sx-1,1.7,'Душевая','bath'),
    room('landing',1,sy+1.7,sx-1,sh-1.7,'Лестничный холл','hall',[],{fixtures:[],openTo:'stairs'}),
    {...stairs(sx,sy,2.2,sh),connectOnly:['landing']},
    room('master',0,end,w,d-end,'Мастер-спальня','bed',['bottom']),
  ];
  put(slug,1,first,[terrace(0,-1.5,w,1.5,'Задняя терраса',{access:'living'})],{partyWalls:true});
  put(slug,2,upper,[],{partyWalls:true});
}
townhouse('town-01',4.8,10,false);
townhouse('town-02',5.4,11.2,true);
townhouse('town-03',5.8,12,true,true);

function layoutFor(def) { return layouts[`${def.slug}/${/^2\s/.test(def.level||'')?2:1}`]; }
module.exports={layoutFor,layouts};
