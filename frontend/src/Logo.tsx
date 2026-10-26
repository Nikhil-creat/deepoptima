/* DeepOptima mark: a "D" outline holding a tiny evolving neural net; the blue node is the Pareto-optimal output. */
export const Logo = ({ size = 22 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M12 8h18c14.4 0 26 10.7 26 24S44.4 56 30 56H12V8z" stroke="rgb(84, 84, 84)" strokeWidth="4" strokeLinejoin="round" />
    <g stroke="rgb(84, 84, 84)" strokeWidth="1.6" opacity="0.7"><path d="M22 21L35 26M22 21L35 38M22 32L35 26M22 32L35 38M22 43L35 26M22 43L35 38" /></g>
    <path d="M35 26L47 32M35 38L47 32" stroke="#3b82f6" strokeWidth="2" />
    <g fill="rgb(84, 84, 84)"><circle cx="22" cy="21" r="3" /><circle cx="22" cy="32" r="3" /><circle cx="22" cy="43" r="3" /><circle cx="35" cy="26" r="3" /><circle cx="35" cy="38" r="3" /></g>
    <circle cx="47" cy="32" r="4.5" fill="#3b82f6" />
  </svg>
)
