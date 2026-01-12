/**
 * API client for PreFlight backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorData.detail || response.statusText,
      errorData
    );
  }
  return response.json();
}

function getAuthHeaders(): HeadersInit {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const api = {
  // Auth endpoints
  auth: {
    async signup(email: string, password: string) {
      const response = await fetch(`${API_BASE_URL}/v1/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      return handleResponse<{
        access_token: string;
        token_type: string;
        expires_in: number;
      }>(response);
    },

    async login(email: string, password: string) {
      const response = await fetch(`${API_BASE_URL}/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      return handleResponse<{
        access_token: string;
        token_type: string;
        expires_in: number;
      }>(response);
    },

    async me() {
      const response = await fetch(`${API_BASE_URL}/v1/auth/me`, {
        headers: {
          ...getAuthHeaders(),
        },
      });
      return handleResponse<{
        id: string;
        email: string;
        role: string;
        tenant_id: string;
        tenant_name: string;
        created_at: string;
      }>(response);
    },
  },

  // Dashboard endpoints
  dashboard: {
    async getOverview() {
      const response = await fetch(`${API_BASE_URL}/v1/dashboard/overview`, {
        headers: {
          ...getAuthHeaders(),
        },
      });
      return handleResponse<{
        evaluations_today: number;
        evaluations_week: number;
        match_rate: number;
        avg_drift: number;
        avg_reliability: number;
      }>(response);
    },
  },

  // Templates endpoints
  templates: {
    async list() {
      const response = await fetch(`${API_BASE_URL}/v1/templates`, {
        headers: {
          ...getAuthHeaders(),
        },
      });
      return handleResponse<
        Array<{
          id: string;
          template_id: string;
          version: string;
          fingerprint: string;
          baseline_reliability: number;
          status: string;
          created_at: string;
        }>
      >(response);
    },
  },

  // Health check
  async health() {
    const response = await fetch(`${API_BASE_URL}/health`);
    return handleResponse<{ status: string }>(response);
  },
};
