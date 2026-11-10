const test = require('node:test');
const assert = require('node:assert/strict');
const { definitions } = require('./generate-public-project-plan-assets');
const { codes } = require('./generate-public-plan-presentation');
const { roomsForPresentation, doorConnections, sharedEdge, exterior } = require('./public-plan-architectural-renderer');

test('revised upper floors give bedrooms access without passing through another bedroom', () => {
  const plans = definitions.filter(d => /^2\s/.test(d.level || '') && /^(h2-02|gar-0[123]|town-0[123])$/.test(d.slug));
  assert.equal(plans.length, 7);
  for (const def of plans) {
    const rooms = roomsForPresentation(def);
    const doors = doorConnections(rooms);
    rooms.forEach((room, index) => {
      if (room.type !== 'bed') return;
      const neighbors = doors.filter(d => d.a === index || d.b === index)
        .map(d => rooms[d.a === index ? d.b : d.a]);
      assert.ok(neighbors.some(r => r.type === 'hall' || r.type === 'living'), `${def.slug}: bedroom lacks circulation access`);
      assert.ok(neighbors.every(r => r.type !== 'bed'), `${def.slug}: bedroom is a passage`);
    });
  }
});

test('concept rooms do not overlap and doors belong to shared room walls', () => {
  for (const def of definitions.filter(d => codes.has(d.slug))) {
    const rooms = roomsForPresentation(def);
    const label = `${def.code}/${def.file}`;
    rooms.forEach((a, i) => rooms.slice(i + 1).forEach(b => {
      const overlapX = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      const overlapY = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      assert.ok(overlapX < .001 || overlapY < .001, `${label}: overlapping rooms`);
    }));
    const doors = doorConnections(rooms);
    assert.equal(doors.length, rooms.length - (def.slug === 'fin-03' ? 2 : 1), `${label}: disconnected rooms`);
    for (const door of doors) {
      const wall = sharedEdge(rooms[door.a], rooms[door.b]);
      assert.ok(wall && wall.end - wall.start >= .85, `${label}: door outside shared wall`);
    }
    for (const edge of exterior(rooms)) {
      const mid = (edge.start + edge.end) / 2;
      for (let j = 0; j < rooms.length; j++) {
        if (j === edge.room) continue;
        const shared = sharedEdge(rooms[edge.room], rooms[j]);
        assert.ok(!shared || shared.axis !== edge.axis || Math.abs(shared.at - edge.at) > .001 || mid <= shared.start || mid >= shared.end,
          `${label}: internal wall classified as exterior`);
      }
    }
  }
});

const { layouts } = require('./public-plan-facade-layouts');
test('facade layouts align stairs and wet rooms across floors; garage roofs remain unoccupied', () => {
  for (const slug of ['h2-02','gar-01','gar-02','gar-03','town-01','town-02','town-03']) {
    const lower=layouts[`${slug}/1`], upper=layouts[`${slug}/2`];
    for (const id of ['stairs','bath']) {
      const a=lower.rooms.find(r=>r.id===id), b=upper.rooms.find(r=>r.id===id);
      assert.deepEqual([a.x,a.y,a.w,a.h],[b.x,b.y,b.w,b.h],`${slug}: ${id} shaft differs`);
    }
    for(const r of upper.rooms) {
      const supported=lower.rooms.filter(a=>a.type!=='garage').reduce((sum,a)=>sum+Math.max(0,Math.min(r.x+r.w,a.x+a.w)-Math.max(r.x,a.x))*Math.max(0,Math.min(r.y+r.h,a.y+a.h)-Math.max(r.y,a.y)),0);
      assert.ok(Math.abs(supported-r.w*r.h)<.001,`${slug}: unsupported upper room`);
    }
    const garage=lower.rooms.find(r=>r.type==='garage');
    if(garage) {
      assert.equal(garage.gateSide,'bottom');
      assert.ok(upper.rooms.every(r=>r.x+r.w<=garage.x+.001));
      const ds=doorConnections(lower.rooms);
      assert.ok(ds.some(e=>[e.a,e.b].map(i=>lower.rooms[i].id).sort().join(',')==='entry,garage'));
      assert.ok(upper.outdoor.some(r=>r.roof));
    }
  }
});
test('entrances and terraces connect to exterior walls; townhouses have no party-wall windows', () => {
  for (const [key,layout] of Object.entries(layouts)) {
    const edges=exterior(layout.rooms);
    if(key.endsWith('/1')) {
      const entry=layout.rooms.find(r=>r.entrySide);
      assert.ok(entry && edges.some(e=>layout.rooms[e.room]===entry && e.side===entry.entrySide && e.end-e.start>=1.2),`${key}: missing exterior entrance`);
    }
    for(const t of layout.outdoor.filter(r=>r.access)) {
      const target=layout.rooms.find(r=>r.id===t.access), edge=sharedEdge(t,target);
      assert.ok(edge && edge.end-edge.start>=1.3,`${key}: terrace disconnected`);
    }
    if(layout.partyWalls) assert.ok(layout.rooms.every(r=>r.windows.every(s=>s==='top'||s==='bottom')),`${key}: party-wall window`);
  }
  assert.ok(!layouts['fam-02/1'].rooms.some(r=>r.id==='stairs'));
  assert.equal(layouts['h2-02/2'].outdoor.filter(r=>r.label==='Балкон').length,1);
  assert.equal(layouts['b1-02/1'].rooms.find(r=>r.id==='bay').openTo,'living');
});

test('every bedroom is reachable without crossing another bedroom, bathroom or stair flight', () => {
  for (const [key, layout] of Object.entries(layouts)) {
    const rooms=layout.rooms, edges=doorConnections(rooms);
    const start=rooms.findIndex(r=>r.entrySide || r.id==='hall');
    const seen=new Set([start]), queue=[start];
    while(queue.length) {
      const i=queue.shift();
      for(const e of edges.filter(e=>e.a===i||e.b===i)) {
        const j=e.a===i?e.b:e.a, r=rooms[j];
        if(seen.has(j)) continue;
        seen.add(j);
        if(r.type!=='bed' && r.type!=='bath' && r.id!=='stairs') queue.push(j);
      }
    }
    rooms.forEach((r,i)=>{if(r.type==='bed') assert.ok(seen.has(i),`${key}: private room blocks ${r.id}`);});
  }
});
