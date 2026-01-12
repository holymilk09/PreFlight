"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { useAuth } from "@/lib/AuthContext";
import { Loading } from "@/components/ui";

interface NavItem {
  href: string;
  label: string;
  icon: string;
}

const navItems: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: "[~]" },
  { href: "/dashboard/evaluations", label: "Evaluations", icon: "[>]" },
  { href: "/dashboard/templates", label: "Templates", icon: "[#]" },
  { href: "/dashboard/api-keys", label: "API Keys", icon: "[*]" },
  { href: "/dashboard/settings", label: "Settings", icon: "[@]" },
];

function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <aside className="w-64 border-r border-terminal-gray bg-terminal-black min-h-screen relative">
      <div className="p-4 border-b border-terminal-gray">
        <Link href="/" className="text-terminal-green font-bold text-lg">
          [PREFLIGHT]
        </Link>
      </div>

      <nav className="p-4">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`
                    flex items-center gap-3 px-3 py-2 transition-colors
                    ${
                      isActive
                        ? "text-terminal-green bg-terminal-darkgray"
                        : "text-terminal-white-dim hover:text-terminal-green hover:bg-terminal-darkgray"
                    }
                  `}
                >
                  <span className="text-terminal-amber">{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>

        {user?.role === "superadmin" && (
          <div className="mt-6 pt-4 border-t border-terminal-gray">
            <Link
              href="/admin"
              className="flex items-center gap-3 px-3 py-2 text-terminal-red hover:bg-terminal-darkgray transition-colors"
            >
              <span className="text-terminal-red">[!]</span>
              <span>Admin Console</span>
            </Link>
          </div>
        )}
      </nav>

      <div className="absolute bottom-0 w-64 p-4 border-t border-terminal-gray">
        <div className="text-xs text-terminal-white-dim mb-2">
          <span className="text-terminal-green">TENANT:</span>{" "}
          {user?.tenant_name || "Loading..."}
        </div>
        <div className="text-xs text-terminal-white-dim">
          <span className="text-terminal-green">ROLE:</span>{" "}
          {user?.role || "..."}
        </div>
      </div>
    </aside>
  );
}

function TopBar() {
  const { user, logout } = useAuth();

  return (
    <header className="h-14 border-b border-terminal-gray bg-terminal-black flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <span className="text-terminal-white-dim text-sm">
          Last sync: <span className="text-terminal-green">just now</span>
        </span>
      </div>

      <div className="flex items-center gap-4">
        <button className="text-terminal-white-dim hover:text-terminal-green text-sm">
          [?] Help
        </button>
        <button className="text-terminal-white-dim hover:text-terminal-green text-sm">
          [!] Alerts
        </button>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-terminal-amber">[U]</span>
          <span className="text-terminal-white-dim">
            {user?.email || "Loading..."}
          </span>
        </div>
        <button
          onClick={logout}
          className="text-terminal-red hover:underline text-sm"
        >
          [Logout]
        </button>
      </div>
    </header>
  );
}

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { isLoading, isAuthenticated } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loading text="Loading dashboard" size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loading text="Redirecting to login" size="lg" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <TopBar />
        <main className="flex-1 p-6 bg-terminal-darkgray">{children}</main>
      </div>
    </div>
  );
}
