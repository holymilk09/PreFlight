"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

interface NavItem {
  href: string;
  label: string;
  icon: string;
}

const navItems: NavItem[] = [
  { href: "/admin", label: "Overview", icon: "[~]" },
  { href: "/admin/tenants", label: "Tenants", icon: "[T]" },
  { href: "/admin/health", label: "System Health", icon: "[H]" },
  { href: "/admin/errors", label: "Errors", icon: "[!]" },
  { href: "/admin/audit", label: "Audit Log", icon: "[A]" },
];

function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-terminal-red bg-terminal-black min-h-screen">
      <div className="p-4 border-b border-terminal-red">
        <Link href="/admin" className="text-terminal-red font-bold text-lg">
          [PREFLIGHT ADMIN]
        </Link>
      </div>

      <nav className="p-4">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive =
              item.href === "/admin"
                ? pathname === "/admin"
                : pathname.startsWith(item.href);

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`
                    flex items-center gap-3 px-3 py-2 transition-colors
                    ${
                      isActive
                        ? "text-terminal-red bg-terminal-darkgray"
                        : "text-terminal-white-dim hover:text-terminal-red hover:bg-terminal-darkgray"
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

        <div className="mt-8 pt-4 border-t border-terminal-gray">
          <Link
            href="/dashboard"
            className="flex items-center gap-3 px-3 py-2 text-terminal-green hover:bg-terminal-darkgray transition-colors"
          >
            <span>[&lt;-]</span>
            <span>Back to Dashboard</span>
          </Link>
        </div>
      </nav>

      <div className="absolute bottom-0 w-64 p-4 border-t border-terminal-red">
        <div className="text-xs text-terminal-red mb-2">
          ADMIN MODE ACTIVE
        </div>
        <div className="text-xs text-terminal-white-dim">
          admin@preflight.dev
        </div>
      </div>
    </aside>
  );
}

function TopBar() {
  return (
    <header className="h-14 border-b border-terminal-red bg-terminal-black flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <span className="text-terminal-red text-sm font-bold">
          ADMIN CONSOLE
        </span>
        <span className="text-terminal-white-dim text-sm">|</span>
        <span className="text-terminal-white-dim text-sm">
          Last refresh: <span className="text-terminal-green">just now</span>
        </span>
      </div>

      <div className="flex items-center gap-4">
        <span className="text-terminal-green text-sm">
          [API: OK] [DB: OK] [REDIS: OK]
        </span>
      </div>
    </header>
  );
}

export default function AdminLayout({ children }: { children: ReactNode }) {
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
