import React from 'react';
import {createRoot} from 'react-dom/client';
import {number, dollars, impactLevel, canApproveOption, crewStatus} from '../scoring.js';

export function PillarBar({label, value, values, unit, money = false}) {
  const level = impactLevel(value, values);
  return <div className={`pillar ${level.tone}`}>
    <div className="pillar-heading"><span>{label}</span><strong>{money ? dollars(value) : number(value)} <small>{unit}</small></strong></div>
    <div className="pillar-track" role="img" aria-label={`${label}: ${value} ${unit || 'dollars'}, ${level.label.toLowerCase()} among compared options`}><span style={{width: `${level.width}%`}} /></div>
    <small className="pillar-comparison">{level.label} among these options · lower is better</small>
  </div>;
}

export function AIRationale({rationale}) {
  return <div className="rationale">
    <h4>AI rationale &amp; citations</h4><small className="explanation-source">{rationale.generator}</small>
    <p><b>Why this was generated:</b> {rationale.why}</p>
    {rationale.context_applied.map(context => <details className="signal-detail" key={context.id}><summary>Context applied · {context.id}</summary><blockquote>{context.text}</blockquote><p>{context.translation}</p></details>)}
    <details className="math-citations"><summary>Citations · inspect the math</summary>
      {rationale.citations.map(c => <p key={c.id}><code>{c.id}</code><br/>{c.detail}</p>)}
      <a href={rationale.crew_reference} target="_blank" rel="noreferrer">FAA Part 117 reference material ↗</a><p>{rationale.crew_scope}</p>
    </details>
  </div>;
}

export function RecoveryOptionCard({option, options, selected, onSelect, onApprove, current}) {
  const canApprove = canApproveOption(option, current);
  const rejected = !option.feasible || !option.isLegal;
  const scores = option.scores;
  return <article className={`option ${rejected ? 'failed' : ''} ${selected ? 'selected' : ''}`} aria-label={option.title}>
    <div className="option-status"><span>{rejected ? 'REJECTED · HARD CONSTRAINT' : option.pareto_optimal ? 'FEASIBLE · YOUR DECISION' : 'FEASIBLE · DOMINATED'}</span><span>{option.pareto_optimal ? 'TRADE-OFF' : option.discovered ? 'SEARCH' : ''}</span></div>
    <h3>{option.title}</h3><p className="strategy">{option.description}</p>
    <PillarBar label="Financial cost" value={scores.financial_cost} values={options.map(o=>o.scores.financial_cost)} money />
    <PillarBar label="Passenger impact" value={scores.passenger_impact} values={options.map(o=>o.scores.passenger_impact)} unit="pts" />
    <PillarBar label="Network health penalty" value={scores.network_health} values={options.map(o=>o.scores.network_health)} unit="pts" />
    <div className={`crew-buffer ${option.isLegal ? 'pass' : 'fail'}`}><b>Crew buffer · hard constraint</b><p>{crewStatus(option)}</p><small>Simplified Part 117-inspired model, not a finding of FAA legality.</small></div>
    <div className="operation-counts">{option.metrics.delayed_flights} delayed · {option.details.cancelled} cancelled · {option.details.ferries} ferries</div>
    <AIRationale rationale={option.rationale}/>
    <div className="card-actions"><button className="quiet" data-plan={option.plan} onClick={()=>onSelect(option.plan)}>{selected ? 'Preview selected' : 'Inspect schedule & evidence'}</button>
    <button data-approve-plan={option.plan} disabled={!canApprove} onClick={()=>onApprove(option.plan)}>{rejected ? 'Approval blocked' : current ? 'Approve in simulation' : 'Approval unavailable'}</button></div>
  </article>;
}

export function RecoveryOptions({options=[], selectedPlan, onSelect, onApprove, current, placeholder}) {
  if (!options.length) return <p className="placeholder">{placeholder}</p>;
  return <>{options.map(option=><RecoveryOptionCard key={option.plan} option={option} options={options} selected={selectedPlan===option.plan} onSelect={onSelect} onApprove={onApprove} current={current}/>)}</>;
}
let root;
window.renderRecoveryCards = props => {
  root ||= createRoot(document.getElementById('optionList'));
  root.render(<RecoveryOptions {...props}/>);
};
window.dispatchEvent(new Event('recovery-cards-ready'));
