import test from 'node:test';
import assert from 'node:assert/strict';
import {impactLevel,canApproveOption,crewStatus} from './scoring.js';
const option={feasible:true,isLegal:true,scores:{crew_buffer:{isLegal:true,minutes_remaining:50}}};
test('approval fails closed for negative legality, stale or infeasible state',()=>{
  assert.equal(canApproveOption(option,true),true);
  assert.equal(canApproveOption(option,false),false);
  assert.equal(canApproveOption({...option,feasible:false},true),false);
  assert.equal(canApproveOption({...option,isLegal:false},true),false);
  assert.equal(canApproveOption({...option,scores:{crew_buffer:{isLegal:false}}},true),false);
});
test('relative bars retain exact direction and handle tied/zero scores',()=>{
  assert.equal(impactLevel(0,[0,20000]).tone,'good');
  assert.equal(impactLevel(20000,[0,20000]).tone,'bad');
  assert.equal(impactLevel(0,[0,0]).width,0);
  assert.equal(impactLevel(37000,[37000,37000]).label,'Equal');
});
test('negative crew buffer gives exact modeled excess without false FAA certification',()=>{
  const status=crewStatus({...option,isLegal:false,scores:{crew_buffer:{minutes_remaining:-95}}});
  assert.match(status,/95 minutes/);assert.match(status,/modeled crew duty/);
});
