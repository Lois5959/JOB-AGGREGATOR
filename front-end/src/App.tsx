import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import HomePage from './pages/Home';
import Login from './pages/Auth';
import Sidebar from './pages/Sidebar';

// Pages chargées à la demande : le bundle initial ne contient que l'accueil et la connexion.
const Research = lazy(() => import('./pages/Research'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
import { translations } from './Trad';
import { apiFetch, clearToken, readToken, SESSION_EXPIRED_EVENT } from './lib/api';
import { EMPTY_USER, type NavigateTarget, type Page, type UserData } from './lib/types';

function userFromToken(): UserData {
  const payload = readToken();
  return payload ? { ...EMPTY_USER, email: payload.sub, role_id: payload.role_id } : EMPTY_USER;
}

// Récupère le profil (nom, compétences, rôle) de l'utilisateur connecté.
async function fetchProfile(email: string): Promise<Partial<UserData> | null> {
  const response = await apiFetch(`/api/dashboard/user/${encodeURIComponent(email)}`);
  if (!response.ok) return null;
  const data = await response.json();
  const nomComplet = (data.nom || "Utilisateur").trim();
  return {
    email,
    nom: nomComplet,
    name: nomComplet,
    prenom: nomComplet.split(' ')[0] || "Utilisateur",
    competences: data.competences || "",
    role_id: data.role_id || 1,
  };
}

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('home');
  const [isLoggedIn, setIsLoggedIn] = useState(() => readToken() !== null);
  const [savedJobs, setSavedJobs] = useState<number[]>([]);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);

  // Nouvel état pour savoir si l'utilisateur vient de s'inscrire ou se connecte normalement
  const [isNewUser, setIsNewUser] = useState(false);

  const [userData, setUserData] = useState<UserData>(userFromToken);

  const [homeFilters, setHomeFilters] = useState({ role: '', city: '' });
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');
  const [accessibility, setAccessibility] = useState(localStorage.getItem('accessibility') || 'none');
  const [language, setLanguage] = useState(localStorage.getItem('lang') || 'fr');

  const t = translations[language] || translations['fr'];

  useEffect(() => {
    localStorage.setItem('theme', theme);
    localStorage.setItem('accessibility', accessibility);
    localStorage.setItem('lang', language);
    document.body.className = `theme-${theme} access-${accessibility}`;
  }, [theme, accessibility, language]);

  const handleLogout = useCallback(() => {
    clearToken();
    setIsLoggedIn(false);
    setIsNewUser(false);
    setSelectedJobId(null);
    setUserData(EMPTY_USER);
    setCurrentPage('home');
  }, []);

  // Au chargement : si un jeton valide est présent, on complète le profil.
  useEffect(() => {
    const payload = readToken();
    if (!payload) {
      clearToken();
      return;
    }
    fetchProfile(payload.sub)
      .then(profile => {
        if (profile) setUserData(prev => ({ ...prev, ...profile }));
      })
      .catch(e => console.error("Erreur de récupération du profil", e));
  }, []);

  // Le serveur a refusé le jeton (expiré ou invalide) : retour à l'accueil, déconnecté.
  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED_EVENT, handleLogout);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleLogout);
  }, [handleLogout]);

  const handleNavigation = (target: NavigateTarget) => {
    if (typeof target === 'object') {
      setSelectedJobId(target.jobId);
      setCurrentPage('research');
      return;
    }
    if (target === 'logout') {
      handleLogout();
    } else {
      setSelectedJobId(null);
      setCurrentPage(target);
    }
  };

  const handleLoginSuccess = async (email: string, isRegister: boolean = false, fallbackName?: string) => {
    const nom = fallbackName || "Utilisateur";
    const base: UserData = { ...EMPTY_USER, email, nom, name: nom, prenom: nom.split(' ')[0], role_id: readToken()?.role_id || 1 };
    try {
      const profile = await fetchProfile(email);
      setUserData({ ...base, ...profile });
    } catch {
      setUserData(base);
    }
    setIsNewUser(isRegister);
    setIsLoggedIn(true);
    setCurrentPage('home');
  };

  const openLogin = () => {
    setAuthMode('login');
    setCurrentPage('login');
  };

  const openRegister = () => {
    setAuthMode('register');
    setCurrentPage('login');
  };

  const pagesWithSidebar = ['research', 'dashboard', 'notifs', 'settings', 'profile', 'admin'];
  const showSidebar = pagesWithSidebar.includes(currentPage);

  return (
    <div className="App" style={{ display: 'flex', minHeight: '100vh', width: '100%' }}>

      {showSidebar && (
        <Sidebar
          onNavigate={handleNavigation}
          userData={userData}
          currentPage={currentPage}
          t={t}
        />
      )}

      <div className="app-page-content" style={{ flex: 1, width: '100%', display: 'flex', flexDirection: 'column' }}>
        <Suspense fallback={<p style={{ padding: '40px', textAlign: 'center' }}>Chargement…</p>}>

        {currentPage === 'home' && (
          <HomePage
            onLoginClick={openLogin}
            onRegisterClick={openRegister}
            onDashboardClick={() => setCurrentPage('dashboard')}
            onNavigate={handleNavigation}
            isLoggedIn={isLoggedIn}
            theme={theme}
            setTheme={setTheme}
            t={t}
            currentLang={language}
            setLang={setLanguage}
            isNewUser={isNewUser}
            userData={userData}
          />
        )}

        {currentPage === 'login' && (
          <Login
            onLoginSuccess={handleLoginSuccess}
            theme={theme}
            setTheme={setTheme}
            initialStep={authMode}
            t={t}
          />
        )}

        {currentPage === 'research' && (
          <Research
            onNavigate={handleNavigation}
            t={t}
            savedJobs={savedJobs}
            setSavedJobs={setSavedJobs}
            userData={userData}
            homeFilters={homeFilters}
            setHomeFilters={setHomeFilters}
            selectedJobId={selectedJobId}
          />
        )}

        {currentPage === 'dashboard' && (
          <Dashboard
            onNavigate={handleNavigation}
            t={t}
            savedJobs={savedJobs}
            userData={userData}
          />
        )}

        {currentPage === 'notifs' && (
          <NotificationsPage
            onNavigate={handleNavigation}
            t={t}
            userData={userData}
          />
        )}

        {currentPage === 'settings' && (
          <SettingsPage
            onNavigate={handleNavigation}
            theme={theme}
            setTheme={setTheme}
            accessibility={accessibility}
            setAccessibility={setAccessibility}
            language={language}
            setLanguage={setLanguage}
            t={t}
            userData={userData}
          />
        )}

        {currentPage === 'profile' && (
          <ProfilePage
            onNavigate={handleNavigation}
            userData={userData}
            setUserData={setUserData}
            t={t}
          />
        )}

        {currentPage === 'admin' && userData?.role_id === 2 && (
          <AdminPage
            onNavigate={handleNavigation}
            t={t}
            userData={userData}
          />
        )}

        {currentPage === 'admin' && userData?.role_id !== 2 && (
          <div style={{ padding: '50px', textAlign: 'center' }}>
            <h2 style={{ color: 'red' }}>Accès refusé</h2>
            <p>Vous n'avez pas les droits d'administrateur pour voir cette page.</p>
            <button onClick={() => setCurrentPage('home')} style={{ marginTop: '20px', padding: '10px 20px' }}>
              Retourner à l'accueil
            </button>
          </div>
        )}
        </Suspense>
      </div>
    </div>
  );
}

export default App;
