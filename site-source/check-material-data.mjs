import assert from 'node:assert/strict';
import {materials,makeProjectBrief,categories} from './materials-data.js';
assert.equal(new Set(materials.map(m=>m.id)).size,materials.length);
assert.equal(materials.filter(m=>m.category==='wall').length,5);
for(const m of materials){assert(m.category in categories);assert.equal(m.reviewStatus,'draft');assert.equal(m.price,null);assert.equal(m.technicalValues,null);assert(m.questions.length>=2);for(const key of ['title','summary','benefit','limitation','heat','budget'])assert(m[key].trim());}
const empty=makeProjectBrief({});assert(empty.includes('вариант ещё не выбран'));assert(empty.includes('Стоимость: не рассчитана'));assert(empty.includes('не утверждены'));
const chosen=makeProjectBrief({wall:'frame',roof:'standing-seam',facade:'timber-facade'},'Современная классика');assert(chosen.includes('Стены: Каркас — пожелание'));assert(chosen.includes('Кровля: Фальцевая стальная кровля'));assert(chosen.includes('Оформление: Современная классика'));assert(chosen.includes('не заказ, смета'));
const invalid=makeProjectBrief({wall:'standing-seam'});assert(invalid.includes('Стены: вариант ещё не выбран'));assert(!invalid.includes('Стены: Фальцевая'));
console.log(JSON.stringify({passed:true,materials:materials.length,wallAlternatives:5,checks:['unique material identifiers','draft-only review status','no invented prices or numerical technical values','complete content fields','unselected preferences remain unselected','category-safe project summary','style and draft limits in summary']},null,2));
