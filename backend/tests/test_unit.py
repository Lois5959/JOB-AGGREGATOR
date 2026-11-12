"""Fonctions pures : statistiques mensuelles, score IA, limiteur de tentatives."""
from datetime import date, datetime

from auth import LoginRateLimiter
from database_api import build_monthly_stats
from feature_ia import build_job_text, normalize_score


def test_stats_mensuelles_six_mois_avec_changement_d_annee():
    candidatures = [
        {"date": date(2026, 2, 3), "status": "En attente"},
        {"date": date(2026, 2, 20), "status": "Accepté"},
        {"date": "2025-12-15", "status": "Refusé"},
        {"date": datetime(2026, 1, 5, 10, 0), "status": "Refusé"},
        {"date": date(2025, 2, 10), "status": "Accepté"},  # il y a un an : hors fenêtre
        {"date": "date illisible", "status": "Accepté"},
    ]
    stats = build_monthly_stats(candidatures, today=date(2026, 2, 28))
    assert [s["mois"] for s in stats] == ["Sept.", "Oct.", "Nov.", "Déc.", "Janv.", "Févr."]
    assert stats[-1] == {"mois": "Févr.", "envoyees": 2, "acceptees": 1, "refusees": 0}
    assert stats[-2] == {"mois": "Janv.", "envoyees": 1, "acceptees": 0, "refusees": 1}
    assert stats[-3] == {"mois": "Déc.", "envoyees": 1, "acceptees": 0, "refusees": 1}
    assert sum(s["envoyees"] for s in stats) == 4


def test_normalize_score_borne_entre_0_et_100():
    assert normalize_score(0.0) == 0.0
    assert normalize_score(0.45) == 50.0
    assert normalize_score(0.99) == 100.0


def test_build_job_text_tolere_les_champs_vides():
    texte = build_job_text({"titre": "DevOps", "competences": None, "description": None})
    assert texte.startswith("DevOps DevOps")


def test_limiteur_bloque_puis_libere(monkeypatch):
    horloge = [1000.0]
    monkeypatch.setattr("auth.time.monotonic", lambda: horloge[0])
    limiteur = LoginRateLimiter(max_attempts=3, window_seconds=60)
    for _ in range(3):
        limiteur.record_failure("1.2.3.4")
    assert limiteur.retry_after("1.2.3.4") == 60
    assert limiteur.retry_after("5.6.7.8") == 0  # les autres IP ne sont pas touchées
    horloge[0] += 61
    assert limiteur.retry_after("1.2.3.4") == 0
