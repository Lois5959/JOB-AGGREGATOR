// Types partagés entre les pages.

export type Translation = Record<string, string>;

export type Page = 'home' | 'login' | 'research' | 'dashboard' | 'notifs' | 'settings' | 'profile' | 'admin';

export type NavigateTarget = Page | 'logout' | { page: 'research'; jobId: number };

export type NavigateFn = (target: NavigateTarget) => void;

export interface UserData {
  name: string;
  nom: string;
  prenom: string;
  email: string;
  competences: string;
  experience?: string;
  avatar?: string | null;
  role_id: number;
}

export const EMPTY_USER: UserData = {
  name: '',
  nom: '',
  prenom: '',
  email: '',
  competences: '',
  experience: 'Junior (0-2 ans)',
  avatar: null,
  role_id: 1,
};

// Offre telle que renvoyée par l'API (/api/dashboard/jobs ou /api/recommendations).
export interface Job {
  id: number;
  titre: string;
  entreprise_nom: string;
  description?: string | null;
  salaire_min?: number | null;
  salaire_max?: number | null;
  location?: string | null;
  date?: string | null;
  contract_type?: string | null;
  competences?: string | null;
  url?: string | null;
  source?: string | null;
  matching_score?: number;
}

export interface Application {
  id: number;
  user_email: string;
  job_id: number;
  company: string;
  position: string;
  date: string;
  status: string;
  color?: string;
}

export interface AdminUser {
  id: number;
  name: string;
  email: string;
  role: string;
  status?: 'online' | 'offline';
}

export interface AdminJob {
  id: number;
  title: string;
  company: string;
  city: string | null;
}
