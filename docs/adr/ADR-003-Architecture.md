# ADR-003 — Choix Architecture

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | Mai 2026 |
| **Décideurs** | Équipe Job Aggregator |

---

## Contexte

Le projet nécessite une plateforme complète avec frontend interactif, backend API, base de données relationnelle, collecte de données externe, feature AI et sécurité intégrée. L'ensemble doit démarrer en une commande et être reproductible sur n'importe quelle machine.

---

## Stack retenue

### Frontend
**React + Vite** — SPA (Single Page Application) servie par Nginx.

Nginx fait office de reverse proxy : il sert les fichiers statiques du build React et proxifie les appels `/api/` vers le backend FastAPI sur le port 8000.

```nginx
location /api/ {
    proxy_pass http://backend:8000/;
    proxy_set_header X-Real-IP $remote_addr;
}
```

### Backend
**Python 3.12 + FastAPI + Uvicorn**

FastAPI a été retenu pour sa génération automatique de documentation OpenAPI, sa validation native des inputs via Pydantic, et sa compatibilité async native (nécessaire pour la collecte périodique en arrière-plan).

```python
# api.py — démarrage de la collecte automatique au lancement
@asynccontextmanager
async def lifespan(app: FastAPI):
    offres = await asyncio.to_thread(collect_everything)
    tache_fond = asyncio.create_task(fetch_en_arriere_plan(30))
    yield
    tache_fond.cancel()
```

### Base de données
**MySQL 8.0** — base relationnelle avec schéma explicite défini dans `db/init.sql`, monté automatiquement au premier démarrage via `docker-entrypoint-initdb.d`.

### Conteneurisation
**Docker + Docker Compose** — 3 services toujours lancés (`frontend`, `backend`, `db`) et 2 services facultatifs
activés par profil : `phpmyadmin` (`--profile tools`) et `fail2ban` (`--profile security`).
Chaque service a un healthcheck et ne démarre que lorsque ses dépendances sont saines (`depends_on: service_healthy`).

---

## Architecture des services

```
Internet
    │
[Nginx - frontend :8082]           seul port public
    │  /api/* → proxy
[FastAPI - backend :8000]          127.0.0.1 uniquement (Swagger /docs)
    │
    ├── [MySQL - db]               réseau backend_network (internal : pas d'accès Internet)
    ├── [phpMyAdmin :8081]         127.0.0.1 uniquement, profil « tools »
    └── [Fail2ban]                 network_mode: host, profil « security »
```

### Segmentation réseau Docker

| Réseau | Services |
|---|---|
| `frontend_network` | frontend ↔ backend |
| `backend_network` (`internal: true`) | backend ↔ db ↔ phpmyadmin |

Le frontend n'a jamais accès direct à la base de données. PhpMyAdmin est uniquement accessible en local (`127.0.0.1:8081`).

---

## Séparation des responsabilités (fichiers backend)

| Fichier | Rôle |
|---|---|
| `api.py` | Point d'entrée FastAPI : démarrage, routes dashboard / candidatures / admin |
| `collector.py` | Appels à l'API WeLoveDevs et normalisation des offres |
| `routes.py` | Routes d'authentification (`/api/register`, `/api/login`) |
| `auth.py` | JWT, hachage bcrypt, contrôle d'accès (propriétaire / admin), limite de tentatives |
| `database_api.py` | Couche d'accès aux données (MySQL) |
| `feature_ia.py` | Feature de recommandation par similarité sémantique |

---

## Alternatives rejetées

### Django REST Framework à la place de FastAPI
**Rejeté** — Django embarque un ORM, un système de templates et un admin qui ne seraient pas utilisés. FastAPI est plus léger, plus rapide à prototyper et produit une doc Swagger automatiquement. Le mode async natif de FastAPI est nécessaire pour la collecte en arrière-plan sans bloquer les requêtes.

### PostgreSQL à la place de MySQL
**Rejeté** — MySQL 8.0 couvre tous les besoins du projet (clés étrangères, contraintes d'intégrité, types de données). L'équipe avait une meilleure maîtrise de MySQL et phpMyAdmin simplifie l'inspection des données en développement.

### Architecture microservices (service collecte séparé)
**Rejeté** — La collecte périodique est gérée via `asyncio.create_task` directement dans le processus FastAPI. Une architecture microservices (worker Celery + Redis par exemple) aurait été plus robuste mais disproportionnée pour le volume de données et la taille de l'équipe.

---

## Trade-offs

**FastAPI async + collecte intégrée** — Simple à déployer mais si la collecte échoue ou bloque, elle impacte le même processus que l'API. En production, un worker séparé (Celery, ARQ) serait préférable.

**MySQL connector sans ORM** — Les requêtes SQL sont écrites manuellement dans `database_api.py`. Plus de contrôle mais plus de risque d'erreurs ; la protection contre les injections repose sur la paramétrisation systématique des requêtes (`cursor.execute(query, params)`).

**Image `python:3.12-slim`** — Réduit la taille de l'image mais nécessite l'installation de toutes les dépendances au build, dont `torch` (CPU-only) qui est lourd. Le flag `--no-cache-dir` et l'index PyTorch CPU (`requirements-ml.txt`) limitent l'impact.
