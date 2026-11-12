"""Contrôle d'accès côté serveur : jeton obligatoire, rôle admin, données personnelles."""
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

import auth
from tests.conftest import bearer


def test_health(client, fake_db):
    assert client.get("/api/health").json() == {"status": "ok", "database": "up"}
    fake_db.up = False
    assert client.get("/api/health").status_code == 503


def test_les_offres_sont_publiques(client):
    r = client.get("/api/dashboard/jobs", params={"location": "lille"})
    assert r.status_code == 200
    assert [j["titre"] for j in r.json()] == ["Ingénieur DevOps"]


ROUTES_ADMIN = [
    ("get", "/api/admin/users"),
    ("get", "/api/admin/jobs"),
    ("delete", "/api/admin/users/2"),
    ("delete", "/api/admin/jobs/1"),
    ("post", "/api/fetch"),
]


@pytest.mark.parametrize("methode, url", ROUTES_ADMIN)
def test_routes_admin_sans_jeton(client, methode, url):
    assert getattr(client, methode)(url).status_code == 401


@pytest.mark.parametrize("methode, url", ROUTES_ADMIN)
def test_routes_admin_refusees_a_un_utilisateur(client, alice_headers, methode, url):
    assert getattr(client, methode)(url, headers=alice_headers).status_code == 403


def test_un_jeton_qui_pretend_etre_admin_ne_suffit_pas(client):
    # Alice forge un jeton avec role_id=2 : le rôle est relu en base, donc refusé.
    assert client.get("/api/admin/users", headers=bearer("alice@example.com", role_id=2)).status_code == 403


def test_admin_liste_et_supprime(client, fake_db, admin_headers):
    assert len(client.get("/api/admin/users", headers=admin_headers).json()) == 3
    assert client.delete("/api/admin/users/2", headers=admin_headers).status_code == 200
    assert "bob@example.com" not in fake_db.users
    assert client.delete("/api/admin/users/99", headers=admin_headers).status_code == 404
    assert client.delete("/api/admin/jobs/1", headers=admin_headers).status_code == 200
    assert client.delete("/api/admin/jobs/1", headers=admin_headers).status_code == 404


def test_admin_ne_peut_pas_supprimer_son_propre_compte(client, fake_db, admin_headers):
    admin_id = fake_db.users["admin@example.com"]["id"]
    assert client.delete(f"/api/admin/users/{admin_id}", headers=admin_headers).status_code == 400


def test_collecte_manuelle_sans_cle(client, admin_headers, monkeypatch):
    monkeypatch.delenv("WELOVEDEVS_API_KEY", raising=False)
    assert client.post("/api/fetch", headers=admin_headers).status_code == 400


def test_jeton_invalide_ou_expire(client):
    assert client.get("/api/applications/alice@example.com",
                      headers={"Authorization": "Bearer pas-un-jwt"}).status_code == 401
    expire = jwt.encode({"sub": "alice@example.com", "role_id": 1,
                         "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                        auth.SECRET_KEY, algorithm=auth.ALGORITHM)
    assert client.get("/api/applications/alice@example.com",
                      headers={"Authorization": f"Bearer {expire}"}).status_code == 401


def test_profil_lisible_uniquement_par_son_proprietaire(client, alice_headers, admin_headers):
    r = client.get("/api/dashboard/user/alice@example.com", headers=alice_headers)
    assert r.status_code == 200
    assert r.json()["prenom"] == "Alice"
    assert client.get("/api/dashboard/user/bob@example.com", headers=alice_headers).status_code == 403
    assert client.get("/api/dashboard/user/bob@example.com", headers=admin_headers).status_code == 200
    assert client.get("/api/dashboard/user/alice@example.com").status_code == 401


def test_mise_a_jour_du_profil(client, fake_db, alice_headers):
    r = client.put("/api/dashboard/user/alice@example.com", headers=alice_headers, json={"competences": "Docker"})
    assert r.status_code == 200
    assert fake_db.users["alice@example.com"]["competences"] == "Docker"
    assert fake_db.users["alice@example.com"]["nom"] == "Alice Martin"  # champ absent = inchangé
    r = client.put("/api/dashboard/user/bob@example.com", headers=alice_headers, json={"nom": "Pirate"})
    assert r.status_code == 403


def candidature(email, nom_fichier="cv.pdf"):
    data = {"user_email": email, "job_id": "1", "company": "Nordwave", "position": "Ingénieur DevOps"}
    files = {"cv": (nom_fichier, b"%PDF-1.4 contenu", "application/pdf")}
    return data, files


def test_candidature(client, fake_db, alice_headers):
    data, files = candidature("alice@example.com")
    assert client.post("/api/applications", data=data, files=files, headers=alice_headers).status_code == 201
    r = client.get("/api/applications/alice@example.com", headers=alice_headers)
    assert [a["company"] for a in r.json()] == ["Nordwave"]


def test_candidature_au_nom_d_un_autre(client, alice_headers):
    data, files = candidature("bob@example.com")
    assert client.post("/api/applications", data=data, files=files, headers=alice_headers).status_code == 403


def test_candidature_format_refuse(client, alice_headers):
    data, files = candidature("alice@example.com", nom_fichier="virus.exe")
    assert client.post("/api/applications", data=data, files=files, headers=alice_headers).status_code == 400


def test_recommandations_sans_competences_renvoient_les_offres(client, alice_headers):
    # Alice n'a pas de compétences : pas de calcul IA, on renvoie les offres sans score.
    r = client.get("/api/recommendations/alice@example.com", headers=alice_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert all("matching_score" not in j for j in r.json())


def test_recommandations_d_un_autre_utilisateur(client, alice_headers):
    assert client.get("/api/recommendations/bob@example.com", headers=alice_headers).status_code == 403
