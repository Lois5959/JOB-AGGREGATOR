// Client HTTP de l'application : ajoute le jeton de connexion et gère les sessions expirées.

const TOKEN_KEY = 'token';
export const SESSION_EXPIRED_EVENT = 'auth:expired';

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export interface TokenPayload {
  sub: string;
  role_id: number;
  exp?: number;
}

// Lit le contenu du jeton (sans le vérifier : seul le serveur fait foi).
export function readToken(token: string | null = getToken()): TokenPayload | null {
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    if (!payload.sub || (payload.exp && payload.exp * 1000 < Date.now())) return null;
    return payload as TokenPayload;
  } catch {
    return null;
  }
}

// fetch() avec l'en-tête Authorization. Une réponse 401 signale une session expirée.
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(path, { ...init, headers });
  if (response.status === 401 && token) {
    clearToken();
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
  return response;
}

// Transforme une erreur FastAPI ({ detail: "..." } ou liste de validations) en message lisible.
export async function errorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      const first = data.detail[0];
      const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : '';
      if (field === 'password') return 'Le mot de passe doit contenir au moins 8 caractères.';
      if (field === 'email') return 'Adresse e-mail invalide.';
      return first.msg || fallback;
    }
  } catch {
    // réponse sans JSON
  }
  return fallback;
}

export function formatSalary(min?: number | null, max?: number | null): string {
  const k = (v: number) => `${v >= 1000 ? Math.round(v / 1000) : v}k€`;
  if (min && max && max > min) return `${k(min)} - ${k(max)}`;
  if (min) return k(min);
  if (max) return k(max);
  return 'Non communiqué';
}

export function initials(name?: string | null): string {
  const words = (name || '').replace(/\(.*?\)/g, '').trim().split(/\s+/).filter(Boolean);
  return (words.slice(0, 2).map(w => w[0]).join('') || '?').toUpperCase();
}
