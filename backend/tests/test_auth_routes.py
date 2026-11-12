"""Routes d'inscription et de connexion, dont la protection contre la force brute."""
from jose import jwt

import auth
import routes
from tests.conftest import MOT_DE_PASSE


def test_inscription_puis_doublon(client, fake_db):
    nouveau = {"email": "carla@example.com", "password": "un-mot-de-passe", "nom": "Carla", "competences": "Docker"}
    r = client.post("/api/register", json=nouveau)
    assert r.status_code == 201
    assert fake_db.users["carla@example.com"]["role_id"] == 1
    assert fake_db.users["carla@example.com"]["password"] != "un-mot-de-passe"  # stocké haché

    r = client.post("/api/register", json=nouveau)
    assert r.status_code == 400


def test_inscription_refuse_un_mot_de_passe_trop_court(client):
    r = client.post("/api/register", json={"email": "court@example.com", "password": "1234"})
    assert r.status_code == 422


def test_inscription_refuse_un_email_invalide(client):
    r = client.post("/api/register", json={"email": "pas-un-email", "password": "un-mot-de-passe"})
    assert r.status_code == 422


def test_connexion_renvoie_un_jeton_valide(client):
    r = client.post("/api/login", json={"email": "bob@example.com", "password": MOT_DE_PASSE})
    assert r.status_code == 200
    corps = r.json()
    assert corps["prenom"] == "Bob" and corps["role_id"] == 1
    payload = jwt.decode(corps["access_token"], auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert payload["sub"] == "bob@example.com"
    assert "exp" in payload


def test_connexion_mauvais_mot_de_passe(client):
    r = client.post("/api/login", json={"email": "bob@example.com", "password": "faux"})
    assert r.status_code == 401


def test_connexion_compte_inconnu(client):
    r = client.post("/api/login", json={"email": "inconnu@example.com", "password": MOT_DE_PASSE})
    assert r.status_code == 401


def test_force_brute_bloquee_apres_5_echecs(client):
    for _ in range(5):
        assert client.post("/api/login", json={"email": "bob@example.com", "password": "faux"}).status_code == 401

    r = client.post("/api/login", json={"email": "bob@example.com", "password": MOT_DE_PASSE})
    assert r.status_code == 429  # même le bon mot de passe est refusé pendant le blocage
    assert int(r.headers["Retry-After"]) > 0


def test_une_connexion_reussie_remet_le_compteur_a_zero(client):
    for _ in range(4):
        client.post("/api/login", json={"email": "bob@example.com", "password": "faux"})
    assert client.post("/api/login", json={"email": "bob@example.com", "password": MOT_DE_PASSE}).status_code == 200
    for _ in range(4):
        assert client.post("/api/login", json={"email": "bob@example.com", "password": "faux"}).status_code == 401


def test_les_echecs_sont_journalises_pour_fail2ban(client, monkeypatch):
    lignes = []
    monkeypatch.setattr(routes.auth_logger, "info", lambda fmt, *args: lignes.append(fmt % args))
    client.post("/api/login", json={"email": "bob@example.com", "password": "faux"})
    assert lignes == ['testclient - "POST /api/login HTTP/1.1" 401']
