import { NavLink, Outlet } from "react-router-dom";
import {
  Activity,
  Bug,
  GitBranch,
  LayoutDashboard,
  Server,
  Settings,
} from "lucide-react";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/providers", icon: Server, label: "Providers" },
  { to: "/routing", icon: GitBranch, label: "Routing" },
  { to: "/logs", icon: Activity, label: "Logs" },
  { to: "/debug", icon: Bug, label: "Debug" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Layout() {
  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <nav className="w-56 border-r border-border bg-card flex flex-col">
        <div className="p-4 border-b border-border">
          <h1 className="text-xl font-bold text-foreground">a2c</h1>
          <p className="text-xs text-muted-foreground">AI API Router</p>
        </div>

        <div className="flex-1 py-4">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2 mx-2 rounded-md transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                }`
              }
            >
              <Icon className="w-4 h-4" />
              <span className="text-sm font-medium">{label}</span>
            </NavLink>
          ))}
        </div>

        <div className="p-4 border-t border-border">
          <p className="text-xs text-muted-foreground">v0.1.0</p>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
