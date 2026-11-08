import { apiFetch, isInternetIssue, notifyInternetIssue } from "./network";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

export type AuthUser = {
  id: number;
  email: string;
  full_name: string;
  role: "student" | "faculty" | "admin" | "super_admin" | string;
  uis_username?: string | null;
  uis_linked?: boolean;
  /** hostel | day_scholar | bus */
  residence_type?: string | null;
  is_hosteller?: boolean;
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("campus_gpt_token");
}

export function setToken(token: string) {
  localStorage.setItem("campus_gpt_token", token);
}

export function clearAuth() {
  localStorage.removeItem("campus_gpt_token");
}

export function afterLoginPath(role?: string) {
  if (role === "admin" || role === "super_admin") return "/admin";
  return "/workspace";
}

export async function fetchMe(): Promise<AuthUser | null> {
  const token = getToken();
  if (!token) return null;
  try {
    const res = await apiFetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401 || res.status === 403) {
      clearAuth();
      return null;
    }
    if (!res.ok) return null;
    return res.json();
  } catch (err) {
    if (isInternetIssue(err)) {
      notifyInternetIssue();
      throw err;
    }
    return null;
  }
}
