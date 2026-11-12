"""Mots de passe, jetons JWT, contrôle d'accès et limitation des tentatives de connexion."""
import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from database_api import ROLE_ADMIN, get_user_by_email

logger = logging.getLogger(__name__)

pwd_contenue = CryptContext(schemes=["bcrypt"], deprecated="auto", truncate_error=False)

SECRET_KEY = os.getenv("JWT_SECRET", "").strip()
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(48)
    logger.warning("JWT_SECRET absent : clé temporaire générée, les sessions seront perdues au redémarrage.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))


def verify_mdp(plain_password, hashed_password):
    """Vérifie si le mot de passe tapé correspond au haché en base."""
    try:
        return pwd_contenue.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False


def obtenir_mdp_hasher(password):
    """Hache un mot de passe (inscription)."""
    return pwd_contenue.hash(password)


def cree_acces_pour_token(data: dict):
    """Génère un JWT signé qui expire après ACCESS_TOKEN_EXPIRE_MINUTES."""
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------
#                         Contrôle d'accès
# ---------------------------------------------------------------------

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail):
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail,
                         headers={"WWW-Authenticate": "Bearer"})


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    """Décode le jeton envoyé dans l'en-tête `Authorization: Bearer ...`."""
    if credentials is None:
        raise _unauthorized("Authentification requise")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise _unauthorized("Session invalide ou expirée")
    email = payload.get("sub")
    if not email:
        raise _unauthorized("Session invalide ou expirée")
    return {"email": email, "role_id": int(payload.get("role_id") or 1)}


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Le rôle est relu en base : un compte supprimé ou rétrogradé perd l'accès tout de suite."""
    db_user = get_user_by_email(user["email"])
    if not db_user or int(db_user.get("role_id") or 0) != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux administrateurs")
    return user


def ensure_self_or_admin(email: str, user: dict):
    """Un utilisateur ne peut lire ou modifier que ses propres données (sauf admin)."""
    if user["email"].lower() != (email or "").lower() and user["role_id"] != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")


# ---------------------------------------------------------------------
#                 Limitation des tentatives de connexion
# ---------------------------------------------------------------------

class LoginRateLimiter:
    """Bloque une IP après `max_attempts` échecs dans une fenêtre glissante.

    Complète fail2ban : cette protection marche partout, même sans iptables.
    """

    def __init__(self, max_attempts=5, window_seconds=600):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._echecs = defaultdict(deque)
        self._lock = threading.Lock()

    def _purge(self, ip, now):
        tentatives = self._echecs[ip]
        while tentatives and now - tentatives[0] > self.window_seconds:
            tentatives.popleft()
        return tentatives

    def retry_after(self, ip) -> int:
        """Secondes restantes avant de pouvoir réessayer (0 si l'IP n'est pas bloquée)."""
        now = time.monotonic()
        with self._lock:
            tentatives = self._purge(ip, now)
            if len(tentatives) < self.max_attempts:
                return 0
            return max(1, int(self.window_seconds - (now - tentatives[0])))

    def record_failure(self, ip):
        with self._lock:
            self._echecs[ip].append(time.monotonic())

    def reset(self, ip=None):
        with self._lock:
            if ip is None:
                self._echecs.clear()
            else:
                self._echecs.pop(ip, None)


login_limiter = LoginRateLimiter(
    max_attempts=int(os.getenv("LOGIN_MAX_ATTEMPTS", "5")),
    window_seconds=int(os.getenv("LOGIN_WINDOW_SECONDS", "600")),
)
