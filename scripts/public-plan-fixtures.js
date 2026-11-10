// Top-view symbols for conceptual plans. These are not measured equipment layouts.
const { drawFixture } = require('./generate-public-project-plan-assets');

function architecturalFixture(room, fixture, box) {
  let x = box.x + box.w * (fixture.x ?? .08);
  const y = box.y + box.h * (fixture.y ?? .08);
  let w = box.w * (fixture.w ?? .32);
  const h = box.h * (fixture.h ?? .28);
  if (fixture.type === 'car') {
    const carWidth = Math.min(w,h*.48);
    x += (w-carWidth)/2;
    w = carWidth;
  }
  const rect = (a,b,c,d,r=0,fill='white') => `<rect x="${a}" y="${b}" width="${c}" height="${d}" rx="${r}" fill="${fill}"/>`;
  const path = d => `<path d="${d}" fill="none"/>`;
  const ellipse = (a,b,c,d) => `<ellipse cx="${a}" cy="${b}" rx="${c}" ry="${d}" fill="white"/>`;
  let svg;
  if (fixture.type === 'bed') {
    svg = rect(0,0,w,h,2,'#f4f2ed') + rect(w*.04,h*.03,w*.92,h*.12,1);
    svg += rect(w*.08,h*.1,w*.38,h*.2,3) + rect(w*.54,h*.1,w*.38,h*.2,3);
    svg += path(`M0 ${h*.37}H${w}M${w*.04} ${h*.44}H${w*.96}`);
  } else if (fixture.type === 'sofa') {
    svg = rect(0,0,w,h,3,'#edf0ed') + rect(w*.06,h*.05,w*.88,h*.19,2);
    svg += [0,1,2].map(i=>rect(w*(.1+i*.27),h*.29,w*.25,h*.59,2)).join('');
    svg += rect(0,h*.18,w*.08,h*.78,2) + rect(w*.92,h*.18,w*.08,h*.78,2);
  } else if (fixture.type === 'bath') {
    svg = rect(0,0,w,h*.46,2) + rect(w*.06,h*.05,w*.88,h*.35,h*.12);
    svg += ellipse(w*.13,h*.22,w*.025,w*.025);
    // Cistern, toilet bowl, and basin, rather than anonymous circles.
    svg += rect(w*.06,h*.61,w*.25,h*.12,1) + ellipse(w*.185,h*.83,w*.105,h*.13);
    svg += ellipse(w*.185,h*.83,w*.065,h*.085);
    svg += rect(w*.59,h*.62,w*.36,h*.32,2) + ellipse(w*.77,h*.78,w*.13,h*.1);
    svg += path(`M${w*.77} ${h*.62}v${h*.07}`);
  } else if (fixture.type === 'stairs') {
    const count = 10;
    svg = rect(0,0,w,h);
    svg += Array.from({length:count-1},(_,i)=>path(`M0 ${h*(i+1)/count}H${w}`)).join('');
    svg += `<path d="M${w*.5} ${h*.92}V${h*.1}m${-w*.08} ${h*.1}l${w*.08} ${-h*.1}l${w*.08} ${h*.1}" fill="none" stroke="#4f5d54" stroke-width="1.6"/>`;
  } else if (fixture.type === 'car') {
    svg = rect(w*.07,0,w*.86,h,h*.13,'#f3f4f1');
    svg += rect(w*.14,h*.25,w*.72,h*.48,4);
    svg += path(`M${w*.14} ${h*.25}l${w*.08} ${-h*.12}h${w*.56}l${w*.08} ${h*.12}M${w*.14} ${h*.73}l${w*.08} ${h*.12}h${w*.56}l${w*.08} ${-h*.12}`);
    svg += [0,.9].map(a=>rect(w*a,h*.2,w*.1,h*.14,1,'#5d6860')+rect(w*a,h*.7,w*.1,h*.14,1,'#5d6860')).join('');
    svg += path(`M${w*.18} ${h*.08}h${w*.18}M${w*.64} ${h*.08}h${w*.18}M${w*.18} ${h*.94}h${w*.18}M${w*.64} ${h*.94}h${w*.18}`);
  }
  if (svg) return `<g transform="translate(${x} ${y})" stroke="#7b847d" stroke-width="1.1" stroke-linejoin="round">${svg}</g>`;
  return drawFixture(room,fixture,box).replaceAll('#a8b0b5','#828b87').replaceAll('#dce2e4','#eceeea');
}

module.exports = { architecturalFixture };
