// Presentation utilities only. Python is the authoritative scoring/legality engine.
export const number = value => Number(value).toLocaleString('en-US');
export const dollars = value => {
  const amount = Number(value);
  const options = Number.isInteger(amount) ? {maximumFractionDigits: 0} : {minimumFractionDigits: 2, maximumFractionDigits: 2};
  return '$' + amount.toLocaleString('en-US', options);
};
export function impactLevel(value, values) {
  const min = Math.min(...values), max = Math.max(...values);
  if (min === max) return {label: value === 0 ? 'No penalty' : 'Equal', tone: value === 0 ? 'good' : 'neutral', width: value === 0 ? 0 : 50};
  return {label: value === min ? 'Lowest' : value === max ? 'Highest' : 'Between', tone: value === min ? 'good' : value === max ? 'bad' : 'warn', width: max ? Math.max(4, value / max * 100) : 0};
}
export function canApproveOption(option, current) {
  return current && option.feasible === true && option.isLegal === true && option.scores?.crew_buffer?.isLegal === true;
}
export function crewStatus(option) {
  const c = option.scores.crew_buffer;
  if (c.minutes_remaining < 0) return `REJECTED: Exceeds modeled crew duty limits by ${Math.abs(c.minutes_remaining)} minutes.`;
  if (!option.isLegal) return 'REJECTED: Another modeled crew constraint failed.';
  return `${c.minutes_remaining} minutes (${(c.minutes_remaining / 60).toFixed(2)} hours) of minimum crew buffer remain.`;
}
