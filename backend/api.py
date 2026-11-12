"""API FastAPI de Job Aggregator : offres, profils, candidatures, administration."""
import asyncio
import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Optional

from email_validator import EmailNotValidError, validate_email
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import feature_ia
from auth import ensure_self_or_admin, get_current_user, obtenir_mdp_hasher, require_admin
from collector import collect_everything, collecte_activee
from database_api import (
    ROLE_ADMIN, add_application, count_offres, creer_utilisateur, delete_job, delete_user,
    get_admin_jobs, get_all_users, get_applications, get_filtered_jobs, get_monthly_stats_from_db,
    get_stats, get_user_by_email, inserer_database, ping_db, set_user_role, update_user_profile,
)
from routes import router as auth_router

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s : %(message)s")
logger = logging.getLogger("jobaggregator")

COLLECT_INTERVAL_MINUTES = int(os.getenv("COLLECT_INTERVAL_MINUTES", "30"))
CV_EXTENSIONS = {".pdf", ".doc", ".docx", ".odt"}
CV_MAX_BYTES = 5 * 1024 * 1024
DEMO_FILE = Path(__file__).with_name("demo_offers.json")


# =====================================================================
#                      DÉMARRAGE ET COLLECTE
# =====================================================================

def lancer_collecte() -> int:
    """Collecte les offres WeLoveDevs et les insère. Renvoie le nombre d'offres reçues."""
    offres = collect_everything()
    if offres:
        inserer_database(offres)
    else:
        logger.info("Collecte : aucune offre récupérée.")
    return len(offres)


async def boucle_collecte(interval_minutes: int):
    while True:
        await asyncio.to_thread(lancer_collecte)
        await asyncio.sleep(interval_minutes * 60)


def creer_admin_initial():
    """Crée (ou promeut) le compte admin défini par ADMIN_EMAIL / ADMIN_PASSWORD."""
    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        return
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError as e:
        logger.error("ADMIN_EMAIL invalide (%s) : compte admin non créé.", e)
        return
    existant = get_user_by_email(email)
    if existant is None:
        if creer_utilisateur(email, obtenir_mdp_hasher(password), "", nom="Administrateur", role_id=ROLE_ADMIN):
            logger.info("Compte administrateur créé : %s", email)
    elif int(existant.get("role_id") or 0) != ROLE_ADMIN:
        set_user_role(email, ROLE_ADMIN)
        logger.info("Compte %s promu administrateur.", email)


def charger_offres_demo():
    """Sans clé WeLoveDevs, remplit une base vide avec des offres fictives pour la démo."""
    if os.getenv("DEMO_DATA", "auto").lower() == "never" or collecte_activee() or count_offres() > 0:
        return
    offres = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
    aujourd_hui = date.today().isoformat()
    for offre in offres:
        offre.setdefault("date", aujourd_hui)
        offre.setdefault("source", "Démo")
    inserer_database(offres)
    logger.info("Base vide et collecte désactivée : %s offres de démonstration chargées.", len(offres))


def initialiser():
    for etape in (creer_admin_initial, charger_offres_demo):
        try:
            etape()
        except Exception as e:
            logger.error("Initialisation (%s) : %s", etape.__name__, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(initialiser)

    taches = []
    if collecte_activee():
        logger.info("Collecte WeLoveDevs activée (toutes les %s min).", COLLECT_INTERVAL_MINUTES)
        taches.append(asyncio.create_task(boucle_collecte(COLLECT_INTERVAL_MINUTES)))
    else:
        logger.info("Collecte désactivée : WELOVEDEVS_API_KEY non renseignée.")

    if os.getenv("WARMUP_MODEL", "true").lower() == "true":
        threading.Thread(target=feature_ia.warmup, daemon=True).start()

    yield

    for tache in taches:
        tache.cancel()
    logger.info("Arrêt du serveur.")


app = FastAPI(title="Job Aggregator API", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:8082,http://localhost:5173").split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


# =====================================================================
#                          ROUTES PUBLIQUES
# =====================================================================

@app.get("/")
def read_root():
    return {"status": "Job Aggregator API is running"}


@app.get("/api/health")
def health():
    if ping_db():
        return {"status": "ok", "database": "up"}
    return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})


@app.get("/api/dashboard/stats")
def dashboard_stats():
    return get_stats()


@app.get("/api/dashboard/jobs")
def dashboard_list(location: Optional[str] = None, contract: Optional[str] = None):
    return get_filtered_jobs(location, contract)


# =====================================================================
#                ROUTES UTILISATEUR (jeton obligatoire)
# =====================================================================

@app.get("/api/dashboard/user/{email}")
def dashboard_user_info(email: str, user: dict = Depends(get_current_user)):
    ensure_self_or_admin(email, user)
    db_user = get_user_by_email(email)
    if not db_user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    nom = (db_user.get("nom") or "Utilisateur").strip()
    return {
        "email": db_user["email"],
        "nom": nom,
        "prenom": nom.split(" ", 1)[0],
        "competences": db_user.get("competences") or "",
        "role_id": db_user["role_id"],
    }


class UserProfileUpdate(BaseModel):
    nom: Optional[str] = Field(default=None, max_length=120)
    competences: Optional[str] = Field(default=None, max_length=2000)
    experience: Optional[str] = Field(default=None, max_length=120)


@app.put("/api/dashboard/user/{email}")
def dashboard_user_update(email: str, profile_data: UserProfileUpdate, user: dict = Depends(get_current_user)):
    ensure_self_or_admin(email, user)
    if not update_user_profile(email, profile_data.nom, profile_data.competences):
        raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour en base de données")
    return {"message": "Profil mis à jour avec succès"}


@app.get("/api/dashboard/stats/monthly")
def dashboard_monthly_stats(email: str = Query(...), user: dict = Depends(get_current_user)):
    ensure_self_or_admin(email, user)
    return get_monthly_stats_from_db(email)


@app.get("/api/recommendations/{email}")
def get_recommendations(email: str, user: dict = Depends(get_current_user)):
    ensure_self_or_admin(email, user)
    return feature_ia.get_matching_jobs(email)


@app.post("/api/applications", status_code=201)
def create_application(
    user_email: str = Form(...),
    job_id: int = Form(...),
    company: str = Form(..., max_length=255),
    position: str = Form(..., max_length=255),
    message: Optional[str] = Form(None),
    cv: UploadFile = File(...),
    motivation_letter: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
):
    ensure_self_or_admin(user_email, user)
    for fichier in (cv, motivation_letter):
        if fichier is None:
            continue
        if Path(fichier.filename or "").suffix.lower() not in CV_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Formats acceptés : PDF, DOC, DOCX ou ODT")
        if fichier.size is not None and fichier.size > CV_MAX_BYTES:
            raise HTTPException(status_code=413, detail="Fichier trop lourd (5 Mo maximum)")

    if not add_application(user_email, job_id, company, position):
        raise HTTPException(status_code=500, detail="Erreur lors de l'envoi de la candidature")
    logger.info("Candidature de %s pour l'offre %s (CV : %s).", user_email, job_id, cv.filename)
    return {"message": "Candidature enregistrée avec succès"}


@app.get("/api/applications/{email}")
def read_applications(email: str, user: dict = Depends(get_current_user)):
    ensure_self_or_admin(email, user)
    return get_applications(email)


# =====================================================================
#                ROUTES ADMINISTRATION (rôle admin vérifié en base)
# =====================================================================

@app.post("/api/fetch")
def trigger_fetch(admin: dict = Depends(require_admin)):
    if not collecte_activee():
        raise HTTPException(status_code=400, detail="Collecte impossible : WELOVEDEVS_API_KEY non renseignée")
    recues = lancer_collecte()
    if recues:
        return {"message": f"{recues} offres collectées"}
    return {"message": "Aucune nouvelle offre trouvée."}


@app.get("/api/admin/users")
def admin_get_users(admin: dict = Depends(require_admin)):
    return get_all_users()


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, admin: dict = Depends(require_admin)):
    moi = get_user_by_email(admin["email"])
    if moi and moi.get("id") == user_id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")
    resultat = delete_user(user_id)
    if resultat is None:
        raise HTTPException(status_code=500, detail="Échec de la suppression de l'utilisateur")
    if not resultat:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return {"message": "Utilisateur supprimé avec succès"}


@app.get("/api/admin/jobs")
def admin_get_jobs(admin: dict = Depends(require_admin)):
    return get_admin_jobs()


@app.delete("/api/admin/jobs/{job_id}")
def admin_delete_job(job_id: int, admin: dict = Depends(require_admin)):
    resultat = delete_job(job_id)
    if resultat is None:
        raise HTTPException(status_code=500, detail="Échec de la suppression de l'offre")
    if not resultat:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    return {"message": "Offre supprimée avec succès"}
