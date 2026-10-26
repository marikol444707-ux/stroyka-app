import assert from 'node:assert/strict';
import {draftRepository,draftKey} from './project-draft.js';
const values=new Map(),storage={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)},repo=draftRepository(storage);
assert.equal(repo.load(),null);
const sample={version:1,project:'house-01',style:'warm',choices:{wall:'brick',roof:'metal-tile'},context:{adults:'2',children:'0',town:'Ставрополь',note:'Не терять пожелания',priorities:['office'],discussionTopics:['cost'],channel:'telegram'}};
repo.save(sample);assert.equal(repo.load().context.children,'0');assert.equal(repo.load().choices.wall,'brick');assert.equal(repo.load().choices.facade,undefined);assert.equal(repo.load().context.note,sample.context.note);
for(const bad of [{...sample,context:[]},{...sample,choices:[]},{...sample,version:2},{...sample,project:'other'},{...sample,choices:{wall:'metal-tile'}},{...sample,style:'unknown'}])assert.throws(()=>repo.save(bad));
assert.equal(repo.load().choices.wall,'brick');storage.setItem(draftKey,'{broken');assert.throws(()=>repo.load());storage.setItem(draftKey,'x'.repeat(32001));assert.throws(()=>repo.load());repo.remove();assert.equal(repo.load(),null);
const denied=draftRepository({getItem(){throw Error('denied')},setItem(){throw Error('quota')},removeItem(){throw Error('denied')}});assert.throws(()=>denied.load());assert.throws(()=>denied.save(sample));assert.throws(()=>denied.remove());console.log('PASS draft roundtrip, explicit zero, open decisions, invalid schema/project/material/style, corrupt/oversized data, removal and storage errors');
