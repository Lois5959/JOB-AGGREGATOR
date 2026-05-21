# ADR-004 — Choix Data

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | Mai 2026 |
| **Décideurs** | Équipe Job Aggregator |

---

## Contexte

Le cahier des charges impose l'intégration de WeLoveDevs comme source de données obligatoire, avec un rate limit de 1 requête/seconde/étudiant. Les offres doivent être normalisées avant stockage et la collecte doit pouvoir être déclenchée manuellement.

---

## Source de données

**WeLoveDevs API** (`https://epi-api.welovedevs.com/v1`)

- Authentification via header `X-API-Key` (clé injectée par variable d'environnement `WELOVEDEVS_API_KEY`)
- Requêtes paginées : `page` + `limit` (10 offres par page, 5 pages max par collecte)
- Délai de 1 seconde entre chaque requête via `time.sleep(1)` pour respecter le rate limit

```python
# api.py
def fetch_offers(page=2, limit=50):
    r = requests.get(BASE_URL, headers=HEADERS, params={"page": page, "limit": limit}, timeout=10)
    ...
    finally:
        time.sleep(1)  # Respect du rate limit 1 req/s
```

---

## Flux d'ingestion

```
WeLoveDevs API
      │
      ▼
fetch_offers(page, limit)     ← requête HTTP paginée + sleep(1)
      │
      ▼
process_page(data_brute)      ← extraction de la liste "values"
      │
      ▼
normalize(raw)                ← transformation et validation par champ
      │
      ▼  (offres invalides filtrées : None retourné)
inserer_database(offres)      ← INSERT IGNORE INTO offres (...)
      │
      ▼
MySQL — table offres
```

### Déclenchement de la collecte

Trois modes coexistent :

| Mode | Déclencheur | Implémentation |
|---|---|---|
| **Au démarrage** | Lancement du conteneur backend | `lifespan()` dans `api.py` |
| **Automatique** | Toutes les 30 minutes | `asyncio.create_task(fetch_en_arriere_plan(30))` |
| **Manuel** | `POST /api/fetch` | Route HTTP accessible depuis l'interface admin |

---

## Normalisation des données

La fonction `normalize()` dans `api.py` transforme chaque offre brute WeLoveDevs en un format commun avant insertion.

### Champs normalisés

| Champ stocké | Source brute | Transformation |
|---|---|---|
| `titre` | `raw["title"]` | Direct |
| `entreprise_id` | `raw["companyId"]` | Direct |
| `description` | `raw["descriptionPreview"]` | Direct |
| `salaire_min` | `raw["salary"]["min"]` | Défaut à 0 si absent |
| `salaire_max` | `raw["salary"]["max"]` | Défaut à 0 si absent |
| `location` | `raw["formattedPlaces"]` | Défaut à "Lieu non renseigné" |
| `date` | `raw["publishDate"]` (timestamp µs) | Conversion : `datetime.fromtimestamp(ts / 1_000_000)` → `YYYY-MM-DD` |
| `contract_type` | `raw["job"]["contractTypes"]` (liste) | `", ".join(list)` ou valeur directe |
| `source` | — | Valeur fixe `"WeLoveDevs"` |

### Filtrage des offres invalides

Une offre est rejetée (retourne `None`) si l'un des champs obligatoires est absent :

```python
if titre is None or date_finale is None or entreprise_id is None or description is None:
    return None
```

### Gestion des doublons

L'instruction `INSERT IGNORE INTO offres` évite les insertions en double en base. Les doublons sont silencieusement ignorés sans erreur.

---

## Schéma de la base de données

```sql
CREATE TABLE offres (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    titre         TEXT NOT NULL,
    entreprise_id TEXT NOT NULL,
    description   TEXT NOT NULL,
    salaire_min   INT,
    salaire_max   INT,
    location      TEXT,
    date          DATE NOT NULL,
    contract_type TEXT,
    source        TEXT NOT NULL
);
```

Le champ `source` permet d'identifier l'origine de chaque offre, utile si une deuxième source est ajoutée ultérieurement.

---

## Requêtes de consultation

Deux routes exposent les données normalisées :

**`GET /api/dashboard/jobs`** — liste filtrée par `location` et/ou `contract` via `LIKE %param%`

**`GET /api/dashboard/stats`** — compteurs agrégés (total d'offres, nombre de CDI)

```sql
SELECT COUNT(*) as total,
       SUM(CASE WHEN contract_type LIKE '%CDI%' THEN 1 ELSE 0 END) as cdi_count
FROM offres
```

---

## Alternative rejetée

### Scraping web (LinkedIn, Indeed) en complément de WeLoveDevs
**Rejeté** — Le scraping viole les CGU de ces plateformes et est juridiquement risqué. Les APIs officielles sont soit inaccessibles, soit payantes. WeLoveDevs couvre les besoins en données tech réelles dans le cadre du partenariat Epitech.

---

## Trade-offs

**`time.sleep(1)` bloquant** — Le respect du rate limit est géré par un sleep synchrone dans un thread séparé (`asyncio.to_thread`). Simple et fiable, mais n'implémente pas de backoff exponentiel en cas d'erreur 429. Une bibliothèque comme `tenacity` permettrait une gestion plus robuste.

**`INSERT IGNORE`** — Évite les doublons sans clé d'unicité explicite sur le contenu. Si WeLoveDevs modifie une offre existante (titre, salaire), la version en base ne sera pas mise à jour. Une stratégie `UPSERT` (INSERT ... ON DUPLICATE KEY UPDATE) serait plus précise mais nécessiterait une clé unique fiable côté source.

**Pagination fixe (5 pages × 10 offres)** — La collecte est bornée à 50 offres par cycle. Suffisant pour un projet école mais limitant en production réelle. Le paramètre `max_pages` dans `collect_everything()` est configurable sans modification du code.
