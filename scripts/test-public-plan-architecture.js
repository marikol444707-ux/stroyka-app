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
