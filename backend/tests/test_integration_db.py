"""Tests sur une vraie base MySQL (lancés en CI avec un service MySQL 8).

En local : RUN_DB_TESTS=1 DB_HOST=127.0.0.1 MYSQL_USER=... pytest -m integration
"""
import os
from datetime import date
from pathlib import Path

import pytest

import database_api as db

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="RUN_DB_TESTS=1 requis (base MySQL réelle)"),
]

SCHEMA = Path(__file__).resolve().parents[2] / "db" / "init.sql"


@pytest.fixture(autouse=True)
def base_propre():
    """Recrée le schéma depuis db/init.sql puis vide les tables avant chaque test."""
    with db.db_cursor() as (connection, cursor):
        for instruction in SCHEMA.read_text(encoding="utf-8").split(";"):
            lignes = [ligne for ligne in instruction.splitlines() if not ligne.strip().startswith("--")]
            if "\n".join(lignes).strip():
                cursor.execute("\n".join(lignes))
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in ("candidatures", "offres", "utilisateurs"):
            cursor.execute(f"TRUNCATE TABLE {table}")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        connection.commit()


def offre(titre, location="Lille", contrat="CDI"):
    return {"titre": titre, "entreprise_nom": "Nordwave", "description": "Description", "salaire_min": 0,
            "salaire_max": 0, "location": location, "date": "2026-01-15", "contract_type": contrat,
            "source": "Test", "competences": "Docker, Linux"}


def test_connexion():
    assert db.ping_db() is True


def test_insertion_ignore_les_doublons():
    assert db.inserer_database([offre("DevOps"), offre("SRE", location="Paris")]) == 2
    assert db.inserer_database([offre("DevOps")]) == 0
    assert db.count_offres() == 2
    assert db.get_all_jobs()[0]["competences"] == "Docker, Linux"


def test_filtres_et_statistiques():
    db.inserer_database([offre("DevOps"), offre("Stage Cloud", contrat="Stage"), offre("SRE", location="Paris")])
    assert {j["titre"] for j in db.get_filtered_jobs(location="lille")} == {"DevOps", "Stage Cloud"}
    assert [j["titre"] for j in db.get_filtered_jobs(contract="Stage")] == ["Stage Cloud"]
    assert db.get_stats() == {"total": 3, "cdi_count": 2}


def test_utilisateur_profil_et_role():
    assert db.creer_utilisateur("lea@example.com", "hash", "Python", nom="Léa Petit") is True
    assert db.creer_utilisateur("lea@example.com", "hash", "", nom="Doublon") is False
    assert db.update_user_profile("lea@example.com", competences="Docker") is True
    user = db.get_user_by_email("lea@example.com")
    assert (user["nom"], user["competences"], user["role_id"]) == ("Léa Petit", "Docker", 1)
    db.set_user_role("lea@example.com", db.ROLE_ADMIN)
    assert db.get_all_users() == [{"id": user["id"], "name": "Léa Petit", "email": "lea@example.com",
                                   "role": "admin"}]


def test_suppressions():
    db.inserer_database([offre("DevOps")])
    job_id = db.get_admin_jobs()[0]["id"]
    assert db.delete_job(job_id) is True
    assert db.delete_job(job_id) is False


def test_candidatures_et_stats_du_mois():
    db.add_application("lea@example.com", 1, "Nordwave", "DevOps")
    apps = db.get_applications("lea@example.com")
    assert apps[0]["status"] == "En attente" and apps[0]["date"] == date.today()
    stats = db.get_monthly_stats_from_db("lea@example.com")
    assert len(stats) == 6 and stats[-1]["envoyees"] == 1
