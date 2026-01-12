"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";

// Mock data - will be replaced with API calls
const mockStats = {
  evaluationsToday: 1247,
  evaluationsWeek: 8934,
  matchRate: 78,
  avgDrift: 0.12,
  avgReliability: 0.89,
};

const mockRecentEvaluations = [
  {
    id: "eval-8834",
    correlationId: "invoice-8834",
    decision: "MATCH" as const,
    drift: 0.04,
    reliability: 0.92,
    template: "INV-ACME-001",
    timestamp: "2 min ago",
  },
  {
    id: "eval-9921",
    correlationId: "receipt-9921",
    decision: "REVIEW" as const,
    drift: 0.34,
    reliability: 0.71,
    template: "RCP-VENDOR-02",
    timestamp: "5 min ago",
  },
  {
    id: "eval-1234",
    correlationId: "contract-123",
    decision: "NEW" as const,
    drift: 0.89,
    reliability: 0.45,
    template: null,
    timestamp: "8 min ago",
  },
  {
    id: "eval-5567",
    correlationId: "invoice-5567",
    decision: "MATCH" as const,
    drift: 0.06,
    reliability: 0.94,
    template: "INV-ACME-001",
    timestamp: "12 min ago",
  },
  {
    id: "eval-7788",
    correlationId: "receipt-7788",
    decision: "REJECT" as const,
    drift: 0.78,
    reliability: 0.23,
    template: "RCP-OLD-01",
    timestamp: "15 min ago",
  },
];

const mockTemplates = [
  { id: "INV-ACME-001", name: "ACME Invoices", status: "ACTIVE", evaluations: 4521, avgDrift: 0.08 },
  { id: "RCP-VENDOR-02", name: "Vendor Receipts", status: "ACTIVE", evaluations: 2134, avgDrift: 0.15 },
  { id: "CON-LEGAL-01", name: "Legal Contracts", status: "REVIEW", evaluations: 892, avgDrift: 0.31 },
];

// Animated counter hook
function useAnimatedCounter(target: number, duration: number = 1000, decimals: number = 0) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const startTime = Date.now();
    const startValue = 0;

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = startValue + (target - startValue) * eased;
      setValue(current);

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    requestAnimationFrame(animate);
  }, [target, duration]);

  return decimals > 0 ? value.toFixed(decimals) : Math.round(value).toLocaleString();
}

// Card component
function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-white/[0.02] border border-white/5 rounded-2xl p-6 ${className}`}>
      {children}
    </div>
  );
}

// Stat card component
function StatCard({
  label,
  value,
  subValue,
  trend,
  suffix = "",
  decimals = 0,
  icon,
}: {
  label: string;
  value: number;
  subValue?: string;
  trend?: "up" | "down" | "stable";
  suffix?: string;
  decimals?: number;
  icon: ReactNode;
}) {
  const animatedValue = useAnimatedCounter(value, 1200, decimals);

  return (
    <Card>
      <div className="flex items-start justify-between mb-4">
        <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-400">
          {icon}
        </div>
        {trend && (
          <div className={`flex items-center gap-1 text-sm ${
            trend === "up" ? "text-emerald-400" : trend === "down" ? "text-red-400" : "text-white/40"
          }`}>
            {trend === "up" && (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
            )}
            {trend === "down" && (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            )}
            {trend === "stable" && (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14" />
              </svg>
            )}
          </div>
        )}
      </div>
      <div className="text-3xl font-semibold text-white mb-1">
        {animatedValue}{suffix}
      </div>
      <div className="text-sm text-white/40">{label}</div>
      {subValue && <div className="text-xs text-white/30 mt-1">{subValue}</div>}
    </Card>
  );
}

// Decision badge component
function DecisionBadge({ decision }: { decision: "MATCH" | "REVIEW" | "NEW" | "REJECT" }) {
  const styles = {
    MATCH: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    REVIEW: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    NEW: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
    REJECT: "bg-red-500/10 text-red-400 border-red-500/20",
  };

  return (
    <span className={`px-2 py-0.5 rounded-md text-xs font-medium border ${styles[decision]}`}>
      {decision}
    </span>
  );
}

// Status badge for templates
function StatusBadge({ status }: { status: string }) {
  const isActive = status === "ACTIVE";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium ${
      isActive
        ? "bg-emerald-500/10 text-emerald-400"
        : "bg-amber-500/10 text-amber-400"
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${isActive ? "bg-emerald-400" : "bg-amber-400"}`} />
      {status}
    </span>
  );
}

// Icons
const Icons = {
  evaluations: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
    </svg>
  ),
  match: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  drift: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
  ),
  reliability: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  ),
  plus: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
    </svg>
  ),
  template: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
    </svg>
  ),
  arrow: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  ),
  docs: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
    </svg>
  ),
};

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-white">Overview</h1>
        <p className="text-white/40 mt-1">Real-time monitoring of your document extraction pipeline</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Evaluations Today"
          value={mockStats.evaluationsToday}
          subValue={`${mockStats.evaluationsWeek.toLocaleString()} this week`}
          trend="up"
          icon={Icons.evaluations}
        />
        <StatCard
          label="Match Rate"
          value={mockStats.matchRate}
          suffix="%"
          trend="up"
          icon={Icons.match}
        />
        <StatCard
          label="Avg Drift Score"
          value={mockStats.avgDrift}
          decimals={2}
          subValue="Target: < 0.15"
          trend="stable"
          icon={Icons.drift}
        />
        <StatCard
          label="Avg Reliability"
          value={mockStats.avgReliability}
          decimals={2}
          subValue="Target: > 0.80"
          trend="up"
          icon={Icons.reliability}
        />
      </div>

      {/* Decision Breakdown + Drift Trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Decision Breakdown */}
        <Card>
          <h3 className="text-lg font-medium text-white mb-6">Decision Breakdown</h3>
          <div className="space-y-4">
            {[
              { label: "Match", count: 973, total: 1247, color: "bg-emerald-500" },
              { label: "Review", count: 198, total: 1247, color: "bg-amber-500" },
              { label: "New", count: 52, total: 1247, color: "bg-cyan-500" },
              { label: "Reject", count: 24, total: 1247, color: "bg-red-500" },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-4">
                <span className="w-16 text-sm text-white/60">{item.label}</span>
                <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${item.color} rounded-full transition-all duration-1000`}
                    style={{ width: `${(item.count / item.total) * 100}%` }}
                  />
                </div>
                <span className="w-12 text-sm text-white/40 text-right">{item.count}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Drift Trend */}
        <Card>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-medium text-white">Drift Trend</h3>
            <span className="text-sm text-white/40">Last 7 days</span>
          </div>
          <div className="h-32 flex items-end gap-1">
            {[0.08, 0.09, 0.11, 0.10, 0.09, 0.12, 0.14, 0.12, 0.11, 0.13, 0.15, 0.12].map((value, i) => (
              <div
                key={i}
                className="flex-1 bg-gradient-to-t from-emerald-500/40 to-emerald-500/20 rounded-t"
                style={{ height: `${(value / 0.2) * 100}%` }}
              />
            ))}
          </div>
          <div className="flex justify-between mt-3 text-xs text-white/30">
            <span>7 days ago</span>
            <span>Today</span>
          </div>
        </Card>
      </div>

      {/* Tables Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Evaluations */}
        <Card>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-medium text-white">Recent Evaluations</h3>
            <Link href="/dashboard/evaluations" className="text-sm text-emerald-400 hover:text-emerald-300 flex items-center gap-1">
              View all {Icons.arrow}
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-white/30 border-b border-white/5">
                  <th className="pb-3 font-medium">ID</th>
                  <th className="pb-3 font-medium">Decision</th>
                  <th className="pb-3 font-medium">Drift</th>
                  <th className="pb-3 font-medium">Rel.</th>
                  <th className="pb-3 font-medium">Time</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {mockRecentEvaluations.map((eval_) => (
                  <tr key={eval_.id} className="border-b border-white/5 last:border-0">
                    <td className="py-3 text-white/70">{eval_.correlationId}</td>
                    <td className="py-3">
                      <DecisionBadge decision={eval_.decision} />
                    </td>
                    <td className={`py-3 ${
                      eval_.drift > 0.3 ? "text-red-400" : eval_.drift > 0.15 ? "text-amber-400" : "text-emerald-400"
                    }`}>
                      {eval_.drift.toFixed(2)}
                    </td>
                    <td className="py-3 text-white/50">{eval_.reliability.toFixed(2)}</td>
                    <td className="py-3 text-white/30">{eval_.timestamp}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Top Templates */}
        <Card>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-medium text-white">Top Templates</h3>
            <Link href="/dashboard/templates" className="text-sm text-emerald-400 hover:text-emerald-300 flex items-center gap-1">
              Manage {Icons.arrow}
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-white/30 border-b border-white/5">
                  <th className="pb-3 font-medium">Template</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Evals</th>
                  <th className="pb-3 font-medium">Avg Drift</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {mockTemplates.map((template) => (
                  <tr key={template.id} className="border-b border-white/5 last:border-0">
                    <td className="py-3">
                      <div className="text-white/80">{template.id}</div>
                      <div className="text-xs text-white/30">{template.name}</div>
                    </td>
                    <td className="py-3">
                      <StatusBadge status={template.status} />
                    </td>
                    <td className="py-3 text-white/50">{template.evaluations.toLocaleString()}</td>
                    <td className={`py-3 ${
                      template.avgDrift > 0.3 ? "text-red-400" : template.avgDrift > 0.15 ? "text-amber-400" : "text-emerald-400"
                    }`}>
                      {template.avgDrift.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <h3 className="text-lg font-medium text-white mb-4">Quick Actions</h3>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/dashboard/api-keys"
            className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-lg transition-colors"
          >
            {Icons.plus}
            <span>Create API Key</span>
          </Link>
          <Link
            href="/dashboard/templates"
            className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 text-white/70 rounded-lg transition-colors"
          >
            {Icons.template}
            <span>Manage Templates</span>
          </Link>
          <Link
            href="/dashboard/evaluations"
            className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 text-white/70 rounded-lg transition-colors"
          >
            {Icons.evaluations}
            <span>View All Evaluations</span>
          </Link>
          <Link
            href="/docs"
            className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 text-white/70 rounded-lg transition-colors"
          >
            {Icons.docs}
            <span>Documentation</span>
          </Link>
        </div>
      </Card>
    </div>
  );
}
