"""Normalisation des offres WeLoveDevs (exigence : au moins une fonction de normalisation testée)."""
import pytest

from collector import (
    ENTREPRISE_INCONNUE, LIEU_INCONNU, collecte_activee, extract_location, normalize, parse_publish_date,
    process_page, texte_brut,
)


def offre_brute(**surcharges):
    offre = {
        "title": "  Ingénieur DevOps  ",
        "descriptionPreview": "Automatiser les déploiements.",
        "publishDate": 1_767_225_600_000,  # 2026-01-01 en millisecondes
        "smallCompany": {"companyName": "Nordwave"},
        "salary": {"min": 40000, "max": 48000, "maxPerYear": 48000},
        "job": {"contractTypes": ["CDI", "Télétravail partiel"]},
        "skillsList": [{"name": "Docker"}, {"name": "Kubernetes"}, "Linux", {"name": None}],
        "formattedPlaces": [{"name": "Lille"}, {"name": "Paris"}],
    }
    offre.update(surcharges)
    return offre


def test_normalize_offre_complete():
    offre = normalize(offre_brute())
    assert offre == {
        "titre": "Ingénieur DevOps",
        "entreprise_nom": "Nordwave",
        "salaire_min": 40000,
        "salaire_max": 48000,
        "description": "Automatiser les déploiements.",
        "location": "Lille",
        "date": "2026-01-01",
        "contract_type": "CDI, Télétravail partiel",
        "salary_per_year": 48000,
        "competences": "Docker, Kubernetes, Linux",
        "source": "WeLoveDevs",
    }


@pytest.mark.parametrize("champ", ["title", "descriptionPreview", "publishDate"])
def test_normalize_rejette_une_offre_incomplete(champ):
    assert normalize(offre_brute(**{champ: None})) is None


def test_normalize_valeurs_par_defaut():
    offre = normalize(offre_brute(smallCompany=None, salary="inconnu", job=None, skillsList=None,
                                  formattedPlaces=[]))
    assert offre["entreprise_nom"] == ENTREPRISE_INCONNUE
    assert offre["salaire_min"] == 0 and offre["salaire_max"] == 0
    assert offre["contract_type"] == "Non communiqué"
    assert offre["competences"] == ""
    assert offre["location"] == LIEU_INCONNU


def test_normalize_ignore_ce_qui_n_est_pas_un_dict():
    assert normalize(None) is None
    assert normalize("texte") is None


@pytest.mark.parametrize("valeur, attendu", [
    (1_767_225_600, "2026-01-01"),            # secondes
    (1_767_225_600_000, "2026-01-01"),        # millisecondes
    (1_767_225_600_000_000, "2026-01-01"),    # microsecondes
    ("2026-01-01T09:30:00Z", "2026-01-01"),   # ISO 8601
    ("1767225600000", "2026-01-01"),          # nombre transmis en texte
    ("pas une date", None),
    (None, None),
])
def test_parse_publish_date(valeur, attendu):
    assert parse_publish_date(valeur) == attendu


@pytest.mark.parametrize("valeur, attendu", [
    ([{"name": "Lille"}], "Lille"),
    ([{"label": " Paris "}], "Paris"),
    ([{"city": "Lyon"}], "Lyon"),
    (["Nantes"], "Nantes"),
    ("Bordeaux, France", "Bordeaux"),
    ([{}], LIEU_INCONNU),
    ([], LIEU_INCONNU),
    (None, LIEU_INCONNU),
    (42, LIEU_INCONNU),
])
def test_extract_location(valeur, attendu):
    assert extract_location(valeur) == attendu


def test_process_page_ne_garde_que_les_offres_valides():
    page = {"values": [offre_brute(), offre_brute(title=None), "n'importe quoi"]}
    assert [o["titre"] for o in process_page(page)] == ["Ingénieur DevOps"]
    assert process_page(None) == []


@pytest.mark.parametrize("cle, attendu", [("", False), ("dummy_key", False), ("vraie-cle", True)])
def test_collecte_activee_selon_la_cle(monkeypatch, cle, attendu):
    monkeypatch.setenv("WELOVEDEVS_API_KEY", cle)
    assert collecte_activee() is attendu


def test_texte_brut_retire_le_html_et_les_scripts():
    brut = '<p>Poste <b>DevOps</b> &amp; Cloud</p><script>alert("xss")</script><ul><li>Docker</li><li>Linux</li></ul>'
    assert texte_brut(brut) == "Poste DevOps & Cloud\nDocker\nLinux"


def test_normalize_nettoie_la_description():
    offre = normalize(offre_brute(descriptionPreview='<img src=x onerror="alert(1)">Bonjour'))
    assert offre["description"] == "Bonjour"
    assert normalize(offre_brute(descriptionPreview="<p> </p>")) is None
