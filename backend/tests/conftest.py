"""Fixtures partagées : une fausse base en mémoire remplace MySQL pour les tests unitaires."""
import os
import tempfile

# Ces variables doivent exister avant l'import des modules de l'API.
os.environ.setdefault("JWT_SECRET", "secret-de-test-uniquement")
os.environ.setdefault("AUTH_LOG_DIR", tempfile.mkdtemp(prefix="jobagg-logs-"))
os.environ.setdefault("WARMUP_MODEL", "false")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import auth  # noqa: E402
import feature_ia  # noqa: E402
import routes  # noqa: E402
from auth import cree_acces_pour_token, obtenir_mdp_hasher  # noqa: E402

MOT_DE_PASSE = "motdepasse-solide"
_HASH = obtenir_mdp_hasher(MOT_DE_PASSE)


class FakeDB:
    """Reproduit le comportement des fonctions de database_api utilisées par les routes."""

    def __init__(self):
        self.up = True
        self.users = {}
        self.jobs = [
            {"id": 1, "titre": "Ingénieur DevOps", "entreprise_nom": "Nordwave", "location": "Lille",
             "contract_type": "CDI", "description": "Docker et CI/CD", "competences": "Docker"},
            {"id": 2, "titre": "Développeur Python", "entreprise_nom": "Datalis", "location": "Lyon",
             "contract_type": "Stage", "description": "FastAPI", "competences": "Python"},
        ]
        self.applications = []
        self.add_user("alice@example.com", "Alice Martin", role_id=1, competences="")
        self.add_user("bob@example.com", "Bob Durand", role_id=1, competences="Python")
        self.add_user("admin@example.com", "Admin", role_id=2)

    def add_user(self, email, nom, role_id=1, competences=""):
        self.users[email] = {"id": len(self.users) + 1, "email": email, "nom": nom,
                             "password": _HASH, "competences": competences, "role_id": role_id}

    # --- fonctions remplacées ---
    def get_user_by_email(self, email):
        return self.users.get(email)

    def creer_utilisateur(self, email, hashed_password, competences, nom="Utilisateur", role_id=1):
        self.users[email] = {"id": len(self.users) + 1, "email": email, "nom": nom,
                             "password": hashed_password, "competences": competences or "", "role_id": role_id}
        return True

    def update_user_profile(self, email, nom=None, competences=None):
        user = self.users.get(email)
        if user:
            user["nom"] = nom if nom is not None else user["nom"]
            user["competences"] = competences if competences is not None else user["competences"]
        return True

    def get_all_users(self):
        return [{"id": u["id"], "name": u["nom"], "email": u["email"],
                 "role": "admin" if u["role_id"] == 2 else "utilisateur"} for u in self.users.values()]

    def delete_user(self, user_id):
        for email, user in list(self.users.items()):
            if user["id"] == user_id:
                del self.users[email]
                return True
        return False

    def get_admin_jobs(self):
        return [{"id": j["id"], "title": j["titre"], "company": j["entreprise_nom"], "city": j["location"]}
                for j in self.jobs]

    def delete_job(self, job_id):
        avant = len(self.jobs)
        self.jobs = [j for j in self.jobs if j["id"] != job_id]
        return len(self.jobs) < avant

    def get_filtered_jobs(self, location=None, contract=None):
        return [dict(j) for j in self.jobs
                if (not location or location.lower() in j["location"].lower())
                and (not contract or contract.lower() in j["contract_type"].lower())]

    def get_all_jobs(self):
        return [dict(j) for j in self.jobs]

    def get_stats(self):
        return {"total": len(self.jobs), "cdi_count": sum("CDI" in j["contract_type"] for j in self.jobs)}

    def add_application(self, user_email, job_id, company, position):
        self.applications.append({"id": len(self.applications) + 1, "user_email": user_email, "job_id": job_id,
                                  "company": company, "position": position, "status": "En attente"})
        return True

    def get_applications(self, user_email):
        return [a for a in self.applications if a["user_email"] == user_email]

    def get_monthly_stats_from_db(self, user_email):
        return []

    def ping_db(self):
        return self.up


@pytest.fixture
def fake_db(monkeypatch):
    db = FakeDB()
    cibles = {
        routes: ["get_user_by_email", "creer_utilisateur"],
        auth: ["get_user_by_email"],
        feature_ia: ["get_user_by_email", "get_all_jobs"],
        api: ["get_user_by_email", "update_user_profile", "get_all_users", "delete_user", "get_admin_jobs",
              "delete_job", "get_filtered_jobs", "get_stats", "add_application", "get_applications",
              "get_monthly_stats_from_db", "ping_db"],
    }
    for module, noms in cibles.items():
        for nom in noms:
            monkeypatch.setattr(module, nom, getattr(db, nom))
    return db


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    auth.login_limiter.reset()
    yield
    auth.login_limiter.reset()


@pytest.fixture
def client(fake_db):
    # Sans `with`, le cycle de vie (collecte, admin initial) n'est pas lancé : aucun appel réseau.
    return TestClient(api.app)


def bearer(email, role_id=1):
    return {"Authorization": f"Bearer {cree_acces_pour_token({'sub': email, 'role_id': role_id})}"}


@pytest.fixture
def alice_headers():
    return bearer("alice@example.com")


@pytest.fixture
def admin_headers():
    return bearer("admin@example.com", role_id=2)
