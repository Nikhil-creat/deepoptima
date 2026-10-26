import type { ReactNode } from 'react'
import { SUPPORT_EMAIL } from './AuthPages'
import { card, PageTitle, useTitle } from '../ui'

function Doc({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  useTitle(title)
  return <div className="max-w-3xl"><PageTitle title={title} sub={`Last updated ${updated}. Plain-language summary, not legal advice. Have a lawyer review it before commercial use.`} /><div className={`${card} space-y-4 text-[13px] leading-relaxed text-gray-700`}>{children}</div></div>
}
const H = ({ children }: { children: ReactNode }) => <h2 className="text-[14.5px] font-medium text-gray-900 mt-2">{children}</h2>

export function Privacy() {
  return (
    <Doc title="Privacy Policy" updated="October 2026">
      <H>What we store</H>
      <p>Your account (name, email, a salted password hash), the CSV files you upload (compressed), the experiments you run and the models trained from your data. We also keep short technical logs and any feedback you send.</p>
      <H>What we use it for</H>
      <p>Only to run the service for you: profiling your tables, training and scoring models, letting you download them and (if you choose) share a read-only results page. Your data is not sold, not used for advertising and not used to train anything for other people.</p>
      <H>Sharing</H>
      <p>Nothing is public by default. If you create a share link, anyone with the link can see model names, scores and feature names for that experiment, never your rows or the model files. You can switch it off at any time.</p>
      <H>Please do not upload</H>
      <p>Passwords, payment data, government IDs, medical records or other sensitive personal data. Remove personal identifiers (names, emails, phone numbers) before uploading whenever you can.</p>
      <H>Retention and deletion</H>
      <p>Data stays until you delete it (the site owner may also set an automatic clean-up period). Deleting a dataset removes its experiments; deleting your account removes everything linked to you immediately. Short-lived backups made by the hosting provider may persist for a limited time.</p>
      <H>Security</H>
      <p>Passwords are hashed with scrypt, sessions use signed tokens, connections use HTTPS, rate limits slow down abuse, and every account can only access its own data. No service is perfectly secure; keep a copy of anything important.</p>
      <H>Contact</H>
      <p>Questions or deletion requests: <a className="text-blue-600 underline" href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.</p>
    </Doc>
  )
}

export function Terms() {
  return (
    <Doc title="Terms of Use" updated="October 2026">
      <H>The service</H>
      <p>DeepOptima Studio is a free, best-effort tool that trains machine-learning models on tables you upload. It may be slow, limited or unavailable at times, and these limits or the service itself may change.</p>
      <H>Your responsibilities</H>
      <p>You may upload only data you have the right to use. Do not upload unlawful content or sensitive personal data, do not attack or overload the service, and do not try to access other people's data. We may suspend accounts that break these rules.</p>
      <H>Your data and models</H>
      <p>You keep all rights to your data and to the models trained from it. You grant us permission to store and process them only to provide the service to you.</p>
      <H>No guarantees</H>
      <p>Models are statistical estimates and can be wrong or biased. Do not rely on them alone for decisions about health, safety, credit, employment or other high-stakes matters. The service is provided “as is”, without warranties, and the owner is not liable for losses arising from its use, to the extent permitted by law.</p>
      <H>Open source</H>
      <p>The software is released under the MIT license; the service operated for you is subject to these terms.</p>
      <H>Contact</H>
      <p><a className="text-blue-600 underline" href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a></p>
    </Doc>
  )
}
