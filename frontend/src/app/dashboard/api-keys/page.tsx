"use client";

import { useState } from "react";
import { Box, Button, Input, Modal, Table } from "@/components/ui";

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

export default function ApiKeysPage() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [generatedKey, setGeneratedKey] = useState("");
  const [copied, setCopied] = useState(false);

  const handleCreateKey = () => {
    // Mock key generation
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl text-terminal-white">API Keys</h1>
          <p className="text-terminal-white-dim text-sm">
            Manage authentication keys for API access
          </p>
        </div>
        <Button variant="primary" onClick={() => setShowCreateModal(true)}>
          [+] Create API Key
        </Button>
      </div>

      {/* Warning Box */}
      <Box title="SECURITY NOTICE" variant="warning">
        <p className="text-terminal-amber text-sm">
          API keys provide full access to your tenant&apos;s resources. Keep
          them secure and never expose them in client-side code or version
          control.
        </p>
      </Box>

      {/* Keys List */}
      <Box title="ACTIVE KEYS">
        <Table
          columns={[
            {
              key: "prefix",
              header: "Key Prefix",
              render: (row) => (
                <code className="text-terminal-green">{row.prefix}...</code>
              ),
            },
            { key: "name", header: "Name" },
            { key: "created", header: "Created" },
            { key: "lastUsed", header: "Last Used" },
            {
              key: "actions",
              header: "Actions",
              render: () => (
                <div className="flex gap-2">
                  <button className="text-terminal-amber hover:underline text-sm">
                    Rotate
                  </button>
                  <button className="text-terminal-red hover:underline text-sm">
                    Revoke
                  </button>
                </div>
              ),
            },
          ]}
          data={mockApiKeys}
          emptyMessage="No API keys created yet"
        />
      </Box>

      {/* Usage Guide */}
      <Box title="QUICK START">
        <div className="space-y-4 text-sm">
          <div>
            <p className="text-terminal-white mb-2">1. Install the SDK:</p>
            <pre className="bg-terminal-black p-3 border border-terminal-gray">
              pip install preflight
            </pre>
          </div>
          <div>
            <p className="text-terminal-white mb-2">
              2. Set your API key (recommended):
            </p>
            <pre className="bg-terminal-black p-3 border border-terminal-gray">
              export PREFLIGHT_API_KEY=cp_xxxxx
            </pre>
          </div>
          <div>
            <p className="text-terminal-white mb-2">3. Use in your code:</p>
            <pre className="bg-terminal-black p-3 border border-terminal-gray">{`from preflight import PreFlight

pf = PreFlight()  # Uses PREFLIGHT_API_KEY env var
result = pf.evaluate(textract_response)`}</pre>
          </div>
        </div>
      </Box>

      {/* Create Key Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="CREATE API KEY"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => setShowCreateModal(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleCreateKey}
              disabled={!newKeyName.trim()}
            >
              Create Key
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <Input
            label="Key Name"
            placeholder="e.g., Production API Key"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            hint="A descriptive name to identify this key"
          />
          <div className="text-terminal-white-dim text-sm">
            <p>
              The full API key will only be shown once after creation. Make sure
              to copy and store it securely.
            </p>
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
        title="API KEY CREATED"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="primary"
              onClick={() => {
                setShowKeyModal(false);
                setGeneratedKey("");
              }}
            >
              Done
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div className="text-terminal-amber text-sm border border-terminal-amber p-3">
            [!] This is the only time your API key will be shown. Copy it now
            and store it securely.
          </div>

          <div>
            <label className="block text-terminal-white-dim text-sm mb-1">
              Your API Key
            </label>
            <div className="flex gap-2">
              <code className="flex-1 bg-terminal-black border border-terminal-green p-3 text-terminal-green break-all">
                {generatedKey}
              </code>
              <Button variant="secondary" onClick={handleCopyKey}>
                {copied ? "[OK]" : "[CP]"}
              </Button>
            </div>
          </div>

          <div className="text-terminal-white-dim text-sm space-y-2">
            <p>Usage example:</p>
            <pre className="bg-terminal-black p-3 border border-terminal-gray overflow-x-auto">
              {`from preflight import PreFlight

pf = PreFlight(api_key="${generatedKey}")`}
            </pre>
          </div>
        </div>
      </Modal>
    </div>
  );
}
