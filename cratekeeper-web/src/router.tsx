import {
  createRootRoute, createRoute, createRouter, Link, Outlet, RouterProvider,
} from '@tanstack/react-router'
import { Disc3, Settings as SettingsIcon, LayoutDashboard, Library, ScrollText } from 'lucide-react'
import { Dashboard } from './Dashboard'
import { EventDetail } from './EventDetail'
import { Settings } from './Settings'
import { MasterLibrary } from './MasterLibrary'
import { AuditLog } from './AuditLog'

const rootRoute = createRootRoute({
  component: () => (
    <div className="min-h-screen flex">
      <aside className="w-56 bg-ink-700 border-r border-ink-500 p-4 space-y-1">
        <div className="flex items-center gap-2 mb-6">
          <Disc3 className="text-crate-500" />
          <span className="font-bold text-lg">cratekeeper</span>
        </div>
        <NavLink to="/library" icon={<Library size={16} />}>Library</NavLink>
        <NavLink to="/" icon={<LayoutDashboard size={16} />}>Dashboard</NavLink>
        <NavLink to="/audit" icon={<ScrollText size={16} />}>Audit</NavLink>
        <NavLink to="/settings" icon={<SettingsIcon size={16} />}>Settings</NavLink>
      </aside>
      <main className="flex-1 p-8 overflow-auto">
        <Outlet />
      </main>
    </div>
  ),
})

function NavLink({ to, icon, children }: { to: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-2 px-3 py-2 rounded-md text-sm hover:bg-ink-500 transition"
      activeProps={{ className: 'flex items-center gap-2 px-3 py-2 rounded-md text-sm bg-ink-500' }}
    >{icon}{children}</Link>
  )
}

const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: '/', component: Dashboard })
const settingsRoute = createRoute({ getParentRoute: () => rootRoute, path: '/settings', component: Settings })
const libraryRoute = createRoute({ getParentRoute: () => rootRoute, path: '/library', component: MasterLibrary })
const auditRoute = createRoute({ getParentRoute: () => rootRoute, path: '/audit', component: AuditLog })
const eventRoute = createRoute({ getParentRoute: () => rootRoute, path: '/events/$eventId', component: EventDetail })

const routeTree = rootRoute.addChildren([indexRoute, settingsRoute, libraryRoute, auditRoute, eventRoute])

const router = createRouter({ routeTree, defaultPreload: 'intent' })

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}

export function AppRouter() {
  return <RouterProvider router={router} />
}
