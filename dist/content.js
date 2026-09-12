export const content = {
  brand: 'FlowBetter',
  hero: {
    heading: 'Compare recovery plans\nfor disrupted flights.',
    description: 'Simulate a disruption and compare recovery options. Review passenger impact and operating costs before choosing a plan.'
  },
  strategies: [
    {
      id: 'cfo',
      name: 'CFO',
      theme: 'Protect the budget',
      description: 'Wait for the original aircraft and crew.',
      cost: 31500,
      passengers: 33845,
      network: 20000,
      crew: -95,
      feasible: false,
      delays: 'The lowest modeled cost comes with a crew constraint.',
      detail: 'Waiting avoids additional ferry and reserve costs, but the original crew exceeds its modeled duty budget by 95 minutes. This plan is blocked in the simulation.',
      actions: ['Wait for original resources', 'Accept the downstream delay', 'Crew check blocks approval']
    },
    {
      id: 'loyalty',
      name: 'Loyalty',
      theme: 'Protect the journey',
      description: 'Use a spare aircraft, a reserve crew, and two ferries.',
      cost: 37000,
      passengers: 12635,
      network: 20000,
      crew: 50,
      feasible: true,
      delays: 'Lower passenger impact. An aircraft still finishes out of position.',
      detail: 'Additional resources reduce passenger disruption while keeping 50 minutes of modeled crew buffer. One aircraft misses its intended overnight position, leaving a trade-off for the next operating day.',
      actions: ['Deploy spare and reserve resources', 'Operate two positioning ferries', 'Retain 50 minutes of crew buffer']
    },
    {
      id: 'operations',
      name: 'Operations',
      theme: 'Protect tomorrow',
      description: 'Cancel the final ORD round trip to restore positioning.',
      cost: 37000,
      passengers: 305015,
      network: 0,
      crew: 50,
      feasible: true,
      delays: 'Restore overnight positioning, with a larger passenger impact.',
      detail: 'Cancelling the final ORD round trip puts aircraft back at their planned overnight hubs. It preserves crew buffer, but cancellations produce substantially higher modeled passenger impact.',
      actions: ['Cancel the final ORD round trip', 'Restore planned overnight positions', 'Retain 50 minutes of crew buffer']
    }
  ]
};
