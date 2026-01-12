"use client";

import { useState, ReactNode } from "react";

// Mock data
const mockApiKeys = [
  {
    id: "key-1",
    prefix: "cp_a3f8",
    name: "Production API Key",
    created: "2024-01-01 09:00:00",
    lastUsed: "2 min ago",
    status: "active" as const,
  },
  {
    id: "key-2",
    prefix: "cp_b7c2",
    name: "Development Key",
    created: "2024-01-05 14:30:00",
    lastUsed: "1 hour ago",
    status: "active" as const,
  },
  {
    id: "key-3",
    prefix: "cp_x9d4",
    name: "Testing Key",
    created: "2024-01-10 11:15:00",
    lastUsed: "Never",
    status: "active" as const,
  },
];

// Card component
function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-white/[0.02] border border-white/5 rounded-2xl p-6 ${className}`}>
      {children}
    </div>
  );
}

// Modal component
function Modal({
  isOpen,
  onClose,
  title,
  children,
}: {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[#111] border border-white/10 rounded-2xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
          <h2 className="text-lg font-medium text-white">{title}</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-white/40 hover:text-white hover:bg-white/5 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}

// Icons
const Icons = {
  plus: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
    </svg>
  ),
  key: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
    </svg>
  ),
  warning: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  ),
  copy: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  ),
  check: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  ),
};

export default function ApiKeysPage() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [generatedKey, setGeneratedKey] = useState("");
  const [copied, setCopied] = useState(false);

  const handleCreateKey = () => {
    const mockKey = `cp_${Math.random().toString(36).substring(2, 34)}`;
    setGeneratedKey(mockKey);
    setShowCreateModal(false);
    setShowKeyModal(true);
    setNewKeyName("");
  };

  const handleCopyKey = async () => {
    await navigator.clipboard.writeText(generatedKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">API Keys</h1>
          <p className="text-white/40 mt-1">Manage authentication keys for API access</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-black font-medium rounded-lg transition-colors"
        >
          {Icons.plus}
          <span>Create API Key</span>
        </button>
      </div>

      {/* Security Notice */}
      <div className="bg-amber-500/5 border border-amber-500/20 rounded-2xl p-4 flex gap-4">
        <div className="text-amber-400">{Icons.warning}</div>
        <div>
          <h3 className="font-medium text-amber-400 mb-1">Security Notice</h3>
          <p className="text-sm text-amber-400/70">
            API keys provide full access to your tenant&apos;s resources. Keep them secure and never expose them in client-side code or version control.
          </p>
        </div>
      </div>

      {/* Keys Table */}
      <Card className="overflow-hidden p-0">
        <div className="px-6 py-4 border-b border-white/5">
          <h3 className="text-lg font-medium text-white">Active Keys</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-white/30 border-b border-white/5">
                <th className="px-6 py-3 font-medium">Key Prefix</th>
                <th className="px-6 py-3 font-medium">Name</th>
                <th className="px-6 py-3 font-medium">Created</th>
                <th className="px-6 py-3 font-medium">Last Used</th>
                <th className="px-6 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {mockApiKeys.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-white/30">
                    No API keys created yet
                  </td>
                </tr>
              ) : (
                mockApiKeys.map((key) => (
                  <tr key={key.id} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                    <td className="px-6 py-4">
                      <code className="text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded text-xs">
                        {key.prefix}...
                      </code>
                    </td>
                    <td className="px-6 py-4 text-white/70">{key.name}</td>
                    <td className="px-6 py-4 text-white/40">{key.created}</td>
                    <td className="px-6 py-4 text-white/40">{key.lastUsed}</td>
                    <td className="px-6 py-4">
                      <div className="flex gap-3">
                        <button className="text-amber-400 hover:text-amber-300 text-sm transition-colors">
                          Rotate
                        </button>
                        <button className="text-red-400 hover:text-red-300 text-sm transition-colors">
                          Revoke
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Quick Start */}
      <Card>
        <h3 className="text-lg font-medium text-white mb-6">Quick Start</h3>
        <div className="space-y-6">
          <div>
            <p className="text-sm text-white/60 mb-2">1. Install the SDK:</p>
            <div className="bg-black/30 border border-white/5 rounded-xl p-4 font-mono text-sm text-white/80">
              pip install preflight
            </div>
          </div>
          <div>
            <p className="text-sm text-white/60 mb-2">2. Set your API key (recommended):</p>
            <div className="bg-black/30 border border-white/5 rounded-xl p-4 font-mono text-sm text-white/80">
              export PREFLIGHT_API_KEY=cp_xxxxx
            </div>
          </div>
          <div>
            <p className="text-sm text-white/60 mb-2">3. Use in your code:</p>
            <div className="bg-black/30 border border-white/5 rounded-xl p-4 font-mono text-sm text-white/80">
              <pre>{`from preflight import PreFlight

pf = PreFlight()  # Uses PREFLIGHT_API_KEY env var
result = pf.evaluate(textract_response)`}</pre>
            </div>
          </div>
        </div>
      </Card>

      {/* Create Key Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create API Key"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-white/60 mb-2">Key Name</label>
            <input
              type="text"
              placeholder="e.g., Production API Key"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              className="w-full bg-white/[0.02] border border-white/10 rounded-xl px-4 py-2.5 text-white placeholder-white/30 focus:outline-none focus:border-emerald-500/50 transition-colors"
            />
            <p className="text-xs text-white/30 mt-1">A descriptive name to identify this key</p>
          </div>
          <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 text-sm text-white/50">
            The full API key will only be shown once after creation. Make sure to copy and store it securely.
          </div>
          <div className="flex gap-3 pt-2">
            <button
              onClick={() => setShowCreateModal(false)}
              className="flex-1 px-4 py-2.5 border border-white/10 text-white/70 hover:bg-white/5 rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleCreateKey}
              disabled={!newKeyName.trim()}
              className="flex-1 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-400 disabled:bg-emerald-500/30 disabled:cursor-not-allowed text-black font-medium rounded-xl transition-colors"
            >
              Create Key
            </button>
          </div>
        </div>
      </Modal>

      {/* Show Generated Key Modal */}
      <Modal
        isOpen={showKeyModal}
        onClose={() => {
          setShowKeyModal(false);
          setGeneratedKey("");
        }}
        title="API Key Created"
      >
        <div className="space-y-4">
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 flex gap-3">
            <div className="text-amber-400">{Icons.warning}</div>
            <p className="text-sm text-amber-400">
              This is the only time your API key will be shown. Copy it now and store it securely.
            </p>
          </div>

          <div>
            <label className="block text-sm text-white/60 mb-2">Your API Key</label>
            <div className="flex gap-2">
              <div className="flex-1 bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 font-mono text-sm text-emerald-400 break-all">
                {generatedKey}
              </div>
              <button
                onClick={handleCopyKey}
                className="px-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl transition-colors flex items-center justify-center"
              >
                {copied ? (
                  <span className="text-emerald-400">{Icons.check}</span>
                ) : (
                  <span className="text-white/50">{Icons.copy}</span>
                )}
              </button>
            </div>
          </div>

          <div>
            <p className="text-sm text-white/40 mb-2">Usage example:</p>
            <div className="bg-black/30 border border-white/5 rounded-xl p-4 font-mono text-xs text-white/70 overflow-x-auto">
              <pre>{`from preflight import PreFlight

pf = PreFlight(api_key="${generatedKey}")`}</pre>
            </div>
          </div>

          <button
            onClick={() => {
              setShowKeyModal(false);
              setGeneratedKey("");
            }}
            className="w-full px-4 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-black font-medium rounded-xl transition-colors"
          >
            Done
          </button>
        </div>
      </Modal>
    </div>
  );
}
