import { useEffect } from 'react'
import type { ReactNode } from 'react'
import Landing from './Landing'
import { AuthProvider, useAuth } from './studio/auth'
import { navigate, PROTECTED, useRoute } from './studio/router'
import { Shell } from './studio/Shell'
import { Account } from './studio/pages/Account'
import { Admin } from './studio/pages/Admin'
import { Login, Register } from './studio/pages/AuthPages'
import { Dashboard } from './studio/pages/Dashboard'
import { DatasetDetail, Datasets } from './studio/pages/Datasets'
import { ExperimentPage } from './studio/pages/Experiment'
import { Help } from './studio/pages/Help'
import { Privacy, Terms } from './studio/pages/Legal'
import { NewExperiment } from './studio/pages/NewExperiment'
import { SharePage } from './studio/pages/Share'
import { Spinner } from './studio/ui'

function Router() {
  const route = useRoute()
  const { user, ready } = useAuth()
  const needsAuth = PROTECTED.has(route.name)
  useEffect(() => { if (route.name !== 'landing') window.scrollTo(0, 0) }, [route])
  useEffect(() => {
    if (!ready) return
    if (needsAuth && !user) {
      try { sessionStorage.setItem('dopt_next', window.location.hash.slice(1)) } catch { /* ignore */ }
      navigate('/login')
    } else if ((route.name === 'login' || route.name === 'register') && user) navigate('/app')
  }, [ready, needsAuth, user, route])

  if (route.name === 'landing') return <Landing />
  let page: ReactNode
  if (!ready || (needsAuth && !user)) page = <Spinner />
  else switch (route.name) {
    case 'login': page = <Login />; break
    case 'register': page = <Register />; break
    case 'app': page = <Dashboard />; break
    case 'datasets': page = <Datasets />; break
    case 'dataset': page = <DatasetDetail id={route.id} />; break
    case 'new': page = <NewExperiment preset={route.dataset} />; break
    case 'experiment': page = <ExperimentPage id={route.id} />; break
    case 'account': page = <Account />; break
    case 'admin': page = user?.is_admin ? <Admin /> : <p className="text-[13px] text-gray-600">Admins only.</p>; break
    case 'share': page = <SharePage token={route.token} />; break
    case 'privacy': page = <Privacy />; break
    case 'terms': page = <Terms />; break
    case 'help': page = <Help />; break
    default: page = <div className="text-center py-20"><p className="text-[1.5rem] font-medium">Page not found</p><a className="text-blue-600 text-[13px]" href="#/">Go home</a></div>
  }
  return <Shell route={route}>{page}</Shell>
}

export default function App() {
  return <AuthProvider><Router /></AuthProvider>
}
