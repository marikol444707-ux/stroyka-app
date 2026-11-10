// Architectural presentation of unverified concepts, not construction documents.
const { autoFixtures } = require('./generate-public-project-plan-assets');
const { architecturalFixture } = require('./public-plan-fixtures');
const near = (a, b) => Math.abs(a - b) < .001;
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));

function roomsForPresentation(def) {
  const rooms = def.rooms.map(r => ({ ...r }));
  // Repair overlaps in the old illustrative rectangles, without asserting dimensions.
  if (def.slug === 'b1-02') {
    rooms[0].w = 3.6; rooms[1].x = 3.6; rooms[1].w = 2.2; rooms[2].h = 2.1;
  }
  if (def.slug === 'apt-03') { rooms[5].w = 1.6; rooms[6].x = 4.8; rooms[6].w = 6.4; rooms[7].w = 4.8; }
  if (def.slug === 'fin-02') {
    rooms[0].w = 2.8; rooms[1].x = 2.8; rooms[1].w = 2.4; rooms[3].h = 2.3;
  }
  if (/^2\s/.test(def.level || '') && /^(h2-02|gar-0[123]|town-0[123])$/.test(def.slug)) {
    const split = Math.min(...rooms.filter(r=>r.y>0).map(r=>r.y));
    const width = Math.max(...rooms.map(r=>r.x+r.w));
    // A dedicated circulation strip avoids access through another bedroom.
    rooms.forEach(r=>{if(r.y>=split)r.y+=1.1;});
    if (/^(h2|gar)/.test(def.slug)) {
      const lower = rooms.filter(r=>r.y>split).sort((a,b)=>b.x-a.x)[0];
      if (lower && ['hall','living'].includes(lower.type)) lower.w=width-lower.x;
    }
    rooms.push({x:0,y:split,w:width,h:1.1,label:'Коридор',type:'hall'});
  }
  return rooms;
}

function outdoorForPresentation(def) {
  const shift = /^2\s/.test(def.level || '') && /^(h2-02|gar-0[123]|town-0[123])$/.test(def.slug) ? 1.1 : 0;
  return (def.outdoor || []).map(r=>({...r,y:r.y+shift,outdoor:true}));
}

function sharedEdge(a, b) {
  let start = Math.max(a.x, b.x), end = Math.min(a.x + a.w, b.x + b.w);
  if (end - start > .01 && (near(a.y + a.h, b.y) || near(b.y + b.h, a.y)))
    return { axis:'h', at:near(a.y+a.h,b.y) ? b.y : a.y, start, end };
  start = Math.max(a.y, b.y); end = Math.min(a.y + a.h, b.y + b.h);
  if (end - start > .01 && (near(a.x + a.w, b.x) || near(b.x + b.w, a.x)))
    return { axis:'v', at:near(a.x+a.w,b.x) ? b.x : a.x, start, end };
  return null;
}

function exterior(rooms) {
  const segments = [];
  rooms.forEach((r, index) => {
    for (const side of ['top','bottom','left','right']) {
      const horizontal = ['top','bottom'].includes(side);
      const axis = horizontal ? 'h' : 'v';
      const at = horizontal ? r.y + (side === 'bottom' ? r.h : 0) : r.x + (side === 'right' ? r.w : 0);
      const start = horizontal ? r.x : r.y, end = start + (horizontal ? r.w : r.h);
      let remaining = [[start,end]];
      rooms.forEach((other, j) => {
        if (index === j) return;
        const shared = sharedEdge(r,other);
        if (!shared || shared.axis !== axis || !near(shared.at,at)) return;
        remaining = remaining.flatMap(([lo,hi]) => {
          const a = Math.max(lo,shared.start), b = Math.min(hi,shared.end);
          return a >= b ? [[lo,hi]] : [[lo,a],[b,hi]].filter(([x,y])=>y-x>.01);
        });
      });
      remaining.forEach(([lo,hi])=>segments.push({axis,at,start:lo,end:hi,room:index,side}));
    }
  });
  return segments;
}

function doorConnections(rooms) {
  const candidates = [];
  rooms.forEach((a,i)=>rooms.slice(i+1).forEach((b,k)=>{
    const edge = sharedEdge(a,b);
    if (edge && edge.end-edge.start >= .85) {
      const rank = r => /лест/i.test(r.label) ? 4 : r.type === 'hall' ? 0 : r.type === 'living' ? 1 : r.type === 'kitchen' ? 3 : r.type === 'work' ? 5 : 8;
      candidates.push({...edge,a:i,b:i+k+1,rank:rank(a)+rank(b)});
    }
  }));
  const parents = rooms.map((_,i)=>i);
  const root = i => parents[i] === i ? i : (parents[i]=root(parents[i]));
  return candidates.sort((a,b)=>a.rank-b.rank).filter(e=>{
    const a=root(e.a),b=root(e.b); if(a===b) return false; parents[a]=b; return true;
  });
}

function renderArchitecture(def, m) {
  const rooms = roomsForPresentation(def);
  const outdoor = outdoorForPresentation(def);
  const zones = [...rooms,...outdoor];
  const box = r => ({x:m.ox+r.x*m.s,y:m.oy+r.y*m.s,w:r.w*m.s,h:r.h*m.s});
  const line = (e,width,color) => {
    const x1=m.ox+(e.axis==='h'?e.start:e.at)*m.s, y1=m.oy+(e.axis==='h'?e.at:e.start)*m.s;
    const x2=m.ox+(e.axis==='h'?e.end:e.at)*m.s, y2=m.oy+(e.axis==='h'?e.at:e.end)*m.s;
    return `<path d="M${x1} ${y1}L${x2} ${y2}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="square"/>`;
  };
  const defs = `<defs><pattern id="wallHatch" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="#bfc3c0"/><path d="M-1 1L1-1M0 6L6 0M5 7L7 5" stroke="#777d78" stroke-width=".65"/></pattern><pattern id="planTiles" width="22" height="22" patternUnits="userSpaceOnUse"><rect width="22" height="22" fill="#f4f5f3"/><path d="M22 0H0V22" fill="none" stroke="#d8ddda" stroke-width=".6"/></pattern></defs>`;
  const floors = zones.map(r=>{
    const b=box(r);
    return `<rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" fill="${r.outdoor?'#f2f0e9':r.type==='bath'?'url(#planTiles)':'#fff'}" ${r.outdoor?'stroke="#a5aaa4" stroke-width="1" stroke-dasharray="5 4"':''}/>`;
  }).join('');
  const furnishings = zones.map(r=>{
    const b=box(r);
    const combinedKitchen = r.label.toLowerCase().includes('кухня-гостиная');
    const fixtures = combinedKitchen ? [
      {type:'table',x:.36,y:.38,w:.26,h:.15}, {type:'sofa',x:.58,y:.66,w:.31,h:.21}
    ] : autoFixtures(r);
    // Leave the circulation strip below the entrance clear of kitchen cabinetry.
    const kx=b.x+.19*m.s, ky=b.y+Math.min(1.15,r.h*.26)*m.s;
    const kw=Math.min(.62,r.w*.13)*m.s, kh=Math.min(3.0,r.h*.47)*m.s;
    const kitchen=combinedKitchen?`<g stroke="#828b87" stroke-width="1.2" fill="white"><rect x="${kx}" y="${ky}" width="${kw}" height="${kh}"/>${[1,2,3,4].map(i=>`<path d="M${kx} ${ky+kh*i/5}h${kw}"/>`).join('')}<rect x="${kx+kw*.18}" y="${ky+kh*.24}" width="${kw*.64}" height="${kw*.8}" rx="3" fill="#edf0ed"/><circle cx="${kx+kw*.32}" cy="${ky+kh*.74}" r="${kw*.13}"/><circle cx="${kx+kw*.72}" cy="${ky+kh*.74}" r="${kw*.13}"/></g>`:'';
    return kitchen+fixtures.map(f=>architecturalFixture(r,f,b)).join('');
  }).join('');
  const innerWidth = Math.max(5,m.s*.12), outerWidth = Math.max(10,m.s*.24);
  const internal=[];
  rooms.forEach((a,i)=>rooms.slice(i+1).forEach(b=>{const e=sharedEdge(a,b);if(e)internal.push(e);}));
  const ext=exterior(rooms);
  const garageFronts = rooms.flatMap((r,i)=>r.type!=='garage'?[]:ext.filter(e=>e.room===i && e.end-e.start>=2).sort((a,b)=>(a.side==='top'?0:1)-(b.side==='top'?0:1)).slice(0,1));
  const walls = [...internal.map(e=>line(e,innerWidth+1.5,'#363d39')+line(e,innerWidth,'url(#wallHatch)')),
    ...ext.map(e=>line(e,outerWidth+1.5,'#363d39')+line(e,outerWidth,'url(#wallHatch)'))].join('');
  const entrance = ext.filter(e=>e.end-e.start>=1.2).sort((a,b)=>{
    const priority=e=>(/прихож|тамбур|ресепшен/i.test(rooms[e.room].label)?0:rooms[e.room].type==='hall'?1:10)+(e.side==='bottom'?0:1);
    return priority(a)-priority(b);
  })[0];
  const doors = doorConnections(rooms);
  const hasEntrance = entrance && !/^2\s/.test(def.level || '');
  if (hasEntrance) doors.push({...entrance,external:true});
  const doorSvg = doors.map(e=>{
    const length=Math.min(.9,(e.end-e.start)*.55), start=e.start+(e.end-e.start-length)*.6;
    const x=m.ox+(e.axis==='h'?start:e.at)*m.s, y=m.oy+(e.axis==='h'?e.at:start)*m.s, d=length*m.s;
    const swingRank = r => /лест/i.test(r.label) ? 3 : r.type==='hall' ? 0 : r.type==='living' ? 1 : 2;
    const target=e.external?rooms[e.room]:[rooms[e.a],rooms[e.b]].sort((a,b)=>swingRank(a)-swingRank(b))[0];
    const flip=e.axis==='h'?(target.y>=e.at-.001?1:-1):(target.x>=e.at-.001?1:-1);
    const trans=e.axis==='h'?`translate(${x} ${y}) scale(1 ${flip})`:`translate(${x} ${y}) rotate(90) scale(1 ${-flip})`;
    return `<g transform="${trans}" data-plan-door="true"><path d="M0 0H${d}" stroke="white" stroke-width="${(e.external?outerWidth:innerWidth)+3}"/><path d="M0 0V${d}M${d} 0A${d} ${d} 0 0 1 0 ${d}" fill="none" stroke="#626b65" stroke-width="1.1"/><path d="M0 0V${d}" stroke="#343f37" stroke-width="2"/></g>`;
  }).join('');
  const patioDoors=outdoor.map(p=>{
    const e=rooms.map(r=>sharedEdge(p,r)).find(Boolean);
    if(!e||e.end-e.start<1.3)return '';
    const mid=(e.start+e.end)/2, half=Math.min(1.6,e.end-e.start-.4)/2;
    const opening={...e,start:mid-half,end:mid+half};
    const halfOpening={...opening,end:mid};
    const otherHalf={...opening,start:mid,at:e.at+.055};
    return line(opening,outerWidth+3,'white')+line(opening,outerWidth-2,'#b1b9b3')+line(opening,outerWidth-4,'white')+
      line(halfOpening,2,'#65796a')+line(otherHalf,2,'#65796a');
  }).join('');
  const garageDoors = garageFronts.map(e=>{
    const mid=(e.start+e.end)/2, half=Math.min(2.7,e.end-e.start-.5)/2;
    const opening={...e,start:mid-half,end:mid+half};
    return line(opening,outerWidth+3,'white')+line(opening,4,'#66736a')+line({...opening,at:e.at+.09},1,'#66736a');
  }).join('');
  const windows = ext.filter(e=>!garageFronts.includes(e) && (!hasEntrance || e!==entrance) && rooms[e.room].windows?.includes(e.side) && e.end-e.start>=1.1).map(e=>{
    const mid=(e.start+e.end)/2, half=Math.min(1.8,(e.end-e.start)*.6)/2;
    const opening={...e,start:mid-half,end:mid+half};
    const mullion={axis:e.axis==='h'?'v':'h',at:mid,start:e.at-.1,end:e.at+.1};
    return line(opening,outerWidth+2,'white')+line(opening,outerWidth-2,'#b1b9b3')+line(opening,outerWidth-4,'white')+line(opening,1.4,'#68756c')+line(mullion,1.4,'#68756c');
  }).join('');
  const labels = zones.map((r,i)=>{
    const b=box(r), x=b.x+b.w*.5, y=b.y+b.h-22;
    const name=r.label.length>22 ? r.label.replace(' / ',' · ') : r.label;
    return `<circle cx="${b.x+19}" cy="${b.y+19}" r="10" fill="white" stroke="#59665d" stroke-width="1"/><text x="${b.x+19}" y="${b.y+23}" text-anchor="middle" font-family="Arial,sans-serif" font-size="11" fill="#28392f">${i+1}</text>${b.w>125&&b.h>100?`<text x="${x}" y="${y}" text-anchor="middle" font-family="Arial,sans-serif" font-size="${Math.min(13,(b.w-18)/(name.length*.57))}" fill="#344b3c" stroke="white" stroke-width="4" paint-order="stroke">${esc(name)}</text>`:''}`;
  }).join('');
  return {body:defs+floors+furnishings+walls+windows+doorSvg+patioDoors+garageDoors+labels,zones,doors};
}

module.exports = { roomsForPresentation, outdoorForPresentation, sharedEdge, exterior, doorConnections, renderArchitecture };
