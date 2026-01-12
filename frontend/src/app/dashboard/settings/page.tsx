"use client";

import { useState } from "react";
import { Box, Button, Input } from "@/components/ui";
import { useAuth } from "@/lib/AuthContext";

export default function SettingsPage() {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saved, setSaved] = useState(false);
  const [passwordError, setPasswordError] = useState("");

  const handleChangePassword = (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError("");

    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match");
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError("Password must be at least 8 characters");
      return;
    }

    // TODO: API call to change password
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <div>
        <h1 className="text-xl text-terminal-white">Settings</h1>
        <p className="text-terminal-white-dim text-sm">
          Manage your account settings
        </p>
      </div>

      {/* Profile Settings */}
      <Box title="PROFILE">
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <span className="text-terminal-white-dim">Email</span>
            <span className="text-terminal-green">{user?.email}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-terminal-white-dim">Role</span>
            <span className="text-terminal-amber">{user?.role}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-terminal-white-dim">Member Since</span>
            <span className="text-terminal-white-dim">
              {user?.created_at
                ? new Date(user.created_at).toLocaleDateString()
                : "..."}
            </span>
          </div>
        </div>
      </Box>

      {/* Change Password */}
      <Box title="CHANGE PASSWORD">
        <form onSubmit={handleChangePassword} className="space-y-4">
          {passwordError && (
            <div className="text-terminal-red text-sm border border-terminal-red px-3 py-2">
              [ERROR] {passwordError}
            </div>
          )}
          {saved && (
            <div className="text-terminal-green text-sm border border-terminal-green px-3 py-2">
              [OK] Password changed successfully
            </div>
          )}

          <Input
            label="Current Password"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            placeholder="********"
          />
          <Input
            label="New Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Min. 8 characters"
          />
          <Input
            label="Confirm New Password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Re-enter new password"
          />

          <div className="flex justify-end">
            <Button
              type="submit"
              variant="primary"
              disabled={
                !currentPassword ||
                !newPassword ||
                newPassword !== confirmPassword
              }
            >
              Update Password
            </Button>
          </div>
        </form>
      </Box>

      {/* Tenant Info */}
      <Box title="ORGANIZATION">
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-terminal-white-dim">Tenant ID</span>
            <code className="text-terminal-green">
              {user?.tenant_id?.slice(0, 8)}...
            </code>
          </div>
          <div className="flex justify-between">
            <span className="text-terminal-white-dim">Organization Name</span>
            <span className="text-terminal-amber">{user?.tenant_name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-terminal-white-dim">Plan</span>
            <span className="text-terminal-green">Free</span>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-terminal-gray">
          <Button variant="secondary" size="sm">
            [^] Upgrade Plan
          </Button>
        </div>
      </Box>

      {/* Danger Zone */}
      <Box title="DANGER ZONE" variant="error">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-terminal-white">Delete Account</p>
              <p className="text-terminal-white-dim text-sm">
                Permanently delete your account and all associated data
              </p>
            </div>
            <Button variant="danger">Delete Account</Button>
          </div>
        </div>
      </Box>
    </div>
  );
}
