"""Collecte des offres WeLoveDevs et normalisation avant stockage."""
import html
import logging
import os
import re
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("WELOVEDEVS_API_URL", "https://epi-api.welovedevs.com/v1")
LIEU_INCONNU = "Lieu non renseigné"
ENTREPRISE_INCONNUE = "Entreprise non renseignée"
DUMMY_KEYS = {"", "dummy_key", "changeme"}


def get_api_key() -> str:
    return os.getenv("WELOVEDEVS_API_KEY", "").strip()


def collecte_activee() -> bool:
    """La collecte n'a de sens qu'avec une vraie clé d'API WeLoveDevs."""
    return get_api_key() not in DUMMY_KEYS


def fetch_offers(page=1, limit=50):
    """Récupère une page d'offres. L'API limite à 1 requête par seconde."""
    headers = {"X-API-Key": get_api_key(), "Content-Type": "application/json"}
    try:
        r = requests.get(BASE_URL, headers=headers, params={"page": page, "limit": limit}, timeout=10)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning("Erreur lors de la récupération de la page %s : %s", page, e)
        return None
    finally:
        time.sleep(1)


def parse_publish_date(value):
    """Convertit la date de publication en 'AAAA-MM-JJ'.

    L'API peut renvoyer un timestamp en secondes, millisecondes ou microsecondes,
    ou une date ISO. On déduit l'unité de l'ordre de grandeur du nombre.
    """
    if value in (None, ""):
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                return None
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    if ts > 1e14:
        ts /= 1_000_000
    elif ts > 1e11:
        ts /= 1_000
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return None


def texte_brut(valeur) -> str:
    """Retire les balises HTML et décode les entités : la description est affichée comme du texte."""
    if not valeur:
        return ""
    texte = re.sub(r"<(script|style)\b.*?</\1\s*>", " ", str(valeur), flags=re.IGNORECASE | re.DOTALL)
    texte = re.sub(r"<br\s*/?>|</p\s*>|</li\s*>", "\n", texte, flags=re.IGNORECASE)
    texte = html.unescape(re.sub(r"<[^>]+>", " ", texte))
    lignes = (re.sub(r"[ \t\u00a0]+", " ", ligne).strip() for ligne in texte.splitlines())
    return "\n".join(ligne for ligne in lignes if ligne)


def extract_location(raw_places) -> str:
    if not raw_places:
        return LIEU_INCONNU

    if isinstance(raw_places, list):
        first = raw_places[0]
        if isinstance(first, dict):
            city = first.get("name") or first.get("label") or first.get("city") or ""
            return str(city).strip() or LIEU_INCONNU
        return str(first).strip() or LIEU_INCONNU

    if isinstance(raw_places, str):
        return raw_places.split(',')[0].strip() or LIEU_INCONNU

    return LIEU_INCONNU


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def normalize(raw):
    """Transforme une offre brute de l'API en ligne prête pour la table `offres`.

    Renvoie None si l'offre n'a pas les champs obligatoires (titre, date, description).
    """
    if not isinstance(raw, dict):
        return None

    titre = (raw.get("title") or "").strip()
    description = texte_brut(raw.get("descriptionPreview"))
    date_finale = parse_publish_date(raw.get("publishDate"))
    if not titre or not description or date_finale is None:
        return None

    salaire = _as_dict(raw.get("Salary") or raw.get("salary"))
    job = _as_dict(raw.get("Job") or raw.get("job"))
    entreprise_nom = (_as_dict(raw.get("smallCompany")).get("companyName") or "").strip() or ENTREPRISE_INCONNUE

    raw_contract = job.get("contractTypes")
    if isinstance(raw_contract, list):
        contract_final = ", ".join(str(c) for c in raw_contract if c) or "Non communiqué"
    else:
        contract_final = raw_contract or "Non communiqué"

    raw_skills = raw.get("skillsList")
    if isinstance(raw_skills, list):
        noms = [s.get("name") if isinstance(s, dict) else s for s in raw_skills]
        skills_final = ", ".join(str(n) for n in noms if n)
    else:
        skills_final = str(raw_skills) if raw_skills else ""

    return {
        "titre": titre,
        "entreprise_nom": entreprise_nom,
        "salaire_min": _as_int(salaire.get("min")),
        "salaire_max": _as_int(salaire.get("max")),
        "description": description,
        "location": extract_location(raw.get("formattedPlaces")),
        "date": date_finale,
        "contract_type": contract_final,
        "salary_per_year": salaire.get("maxPerYear") or "Salaire non renseigné",
        "competences": skills_final,
        "source": "WeLoveDevs",
    }


def process_page(data_brute):
    if not isinstance(data_brute, dict):
        return []
    offres = (normalize(offre) for offre in data_brute.get("values", []))
    return [o for o in offres if o]


def collect_everything(max_pages=20):
    toutes_les_offres = []
    for num_page in range(1, max_pages + 1):
        paquet_brut = fetch_offers(page=num_page, limit=50)
        if not paquet_brut:
            break
        toutes_les_offres.extend(process_page(paquet_brut))
    return toutes_les_offres
