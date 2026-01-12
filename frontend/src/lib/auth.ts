/**
 * Authentication utilities
 */

import { api, ApiError } from "./api";

export interface User {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
  tenant_name: string;
  created_at: string;
}

export interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

const TOKEN_KEY = "access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export async function signup(
  email: string,
  password: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const response = await api.auth.signup(email, password);
    setToken(response.access_token);
    return { success: true };
  } catch (error) {
    if (error instanceof ApiError) {
      return { success: false, error: error.message };
    }
    return { success: false, error: "An unexpected error occurred" };
  }
}

export async function login(
  email: string,
  password: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const response = await api.auth.login(email, password);
    setToken(response.access_token);
    return { success: true };
  } catch (error) {
    if (error instanceof ApiError) {
      return { success: false, error: error.message };
    }
    return { success: false, error: "An unexpected error occurred" };
  }
}

export async function logout(): Promise<void> {
  removeToken();
  window.location.href = "/login";
}

export async function getCurrentUser(): Promise<User | null> {
  if (!isAuthenticated()) return null;

  try {
    return await api.auth.me();
  } catch {
    // Token might be expired or invalid
    removeToken();
    return null;
  }
}
