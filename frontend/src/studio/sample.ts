function rng(seed: number): () => number {
  let a = seed
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Small synthetic "will this customer leave?" table so new users can try the product in one click. */
export function sampleChurnCsv(n = 600): string {
  const r = rng(7)
  const plans = ['basic', 'standard', 'premium']
  const rows = ['age,monthly_income,tenure_months,plan,support_calls,late_payments,churned']
  for (let i = 0; i < n; i++) {
    const age = 18 + Math.floor(r() * 50)
    const income = Math.round(1500 + r() * 6000)
    const tenure = Math.floor(r() * 72)
    const plan = plans[Math.floor(r() * 3)]
    const calls = Math.floor(r() * 8)
    const late = Math.floor(r() * 4)
    const risk = 0.9 * (calls / 8) + 0.6 * (late / 4) - 0.5 * (tenure / 72) + (plan === 'basic' ? 0.25 : plan === 'premium' ? -0.2 : 0) + (r() - 0.5) * 0.5
    rows.push([age, r() < 0.03 ? '' : income, tenure, plan, calls, late, risk > 0.4 ? 'yes' : 'no'].join(','))
  }
  return rows.join('\n')
}
