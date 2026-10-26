import assert from 'node:assert/strict';
import {sampleEnter,sampleExit,ease,enterSeconds,exitSeconds} from './scene-journey.js';
assert(enterSeconds>0&&exitSeconds>0);assert.equal(ease(-1),0);assert.equal(ease(2),1);
assert.deepEqual([sampleEnter(0).view,sampleEnter(0).spread,sampleEnter(0).veil],['house',0,0]);
assert.equal(sampleEnter(.44).view,'study');assert.equal(sampleEnter(.44).veil,1);assert.equal(sampleEnter(.53).spread,0);
assert.deepEqual([sampleEnter(1).phase,sampleEnter(1).spread,sampleEnter(1).veil],['ready',1,0]);
assert.equal(sampleExit(0).view,'study');assert.equal(sampleExit(.36).view,'house');assert.equal(sampleExit(.36).veil,1);assert.equal(sampleExit(.36).spread,0);assert.equal(sampleExit(1).camera,1);
let oldEnter=0,oldExit=1;
for(let i=0;i<=1000;i++){const p=i/1000,a=sampleEnter(p),b=sampleExit(p),c=sampleExit(p,true);for(const o of [a,b,c])for(const key of ['progress','camera','veil','spread'])assert(Number.isFinite(o[key])&&o[key]>=0&&o[key]<=1);assert(a.spread>=oldEnter);assert(b.spread<=oldExit);oldEnter=a.spread;oldExit=b.spread;assert.equal(c.view,'house');assert.equal(c.veil,0);}
console.log(JSON.stringify({passed:true,checks:['bounded finite timelines','house before material study','scene switch covered by veil','monotonic unfolding and assembly','return to original camera','cancel during approach avoids flashing a study']},null,2));
