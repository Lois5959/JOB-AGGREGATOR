"""Inscription et connexion."""
import logging
import os

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from auth import cree_acces_pour_token, login_limiter, obtenir_mdp_hasher, verify_mdp
from database_api import ROLE_UTILISATEUR, creer_utilisateur, get_user_by_email

router = APIRouter()

# --- Journal des échecs de connexion, lu par fail2ban -----------------
# Format attendu par fail2ban/filter.d/jobaggregator.conf : `<IP> - "POST /api/login HTTP/1.1" 401`
auth_logger = logging.getLogger("auth_failures")
auth_logger.setLevel(logging.INFO)
auth_logger.propagate = False
_log_dir = os.getenv("AUTH_LOG_DIR", "/var/log/jobaggregator")
try:
    os.makedirs(_log_dir, exist_ok=True)
    _handler = logging.FileHandler(os.path.join(_log_dir, "app.log"))
except OSError:
    _handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter('%(message)s'))
auth_logger.addHandler(_handler)


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    competences: str | None = Field(default=None, max_length=2000)
    nom: str | None = Field(default=None, max_length=120)
    prenom: str | None = Field(default=None, max_length=120)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str
    email: str
    nom: str
    prenom: str
    role_id: int


@router.post("/api/register", status_code=status.HTTP_201_CREATED)
def register(user: UserRegister):
    if get_user_by_email(user.email):
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")

    if user.prenom and user.nom:
        nom_affichage = f"{user.prenom} {user.nom}"
    else:
        nom_affichage = user.prenom or user.nom or "Utilisateur"

    if not creer_utilisateur(user.email, obtenir_mdp_hasher(user.password), user.competences,
                             nom=nom_affichage, role_id=ROLE_UTILISATEUR):
        raise HTTPException(status_code=500, detail="Erreur lors de la création du compte")

    return {"message": "Utilisateur créé avec succès"}


@router.post("/api/login", response_model=Token)
def login(request: Request, user: UserLogin):
    client_ip = request.client.host if request.client else "unknown"

    attente = login_limiter.retry_after(client_ip)
    if attente:
        auth_logger.info('%s - "POST /api/login HTTP/1.1" 429', client_ip)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Trop de tentatives. Réessayez dans quelques minutes.",
                            headers={"Retry-After": str(attente)})

    db_user = get_user_by_email(user.email)
    if not db_user or not verify_mdp(user.password, db_user['password']):
        login_limiter.record_failure(client_ip)
        auth_logger.info('%s - "POST /api/login HTTP/1.1" 401', client_ip)
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    login_limiter.reset(client_ip)
    access_token = cree_acces_pour_token(data={"sub": db_user['email'], "role_id": db_user['role_id']})

    nom_complet = (db_user.get('nom') or "Utilisateur").strip()
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "email": db_user['email'],
        "nom": nom_complet,
        "prenom": nom_complet.split(' ', 1)[0],
        "role_id": int(db_user['role_id']),
    }
