# ADR-006 — Choix CI/CD

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | Mai 2026 (mis à jour en novembre 2026) |
| **Décideurs** | Équipe Job Aggregator |

---

## Contexte

Le cahier des charges impose GitHub Actions comme système CI, avec exécution automatique sur les pull requests et les pushs sur `main`. Le pipeline doit inclure a minima : build checks, lint/quality checks, et tests automatisés couvrant deux routes backend et une fonction de normalisation.

---

## Décision

Un seul workflow, `.github/workflows/ci.yml`, déclenché sur chaque `push` vers `main` / `develop`
et sur chaque pull request vers `main`. Il contient **quatre jobs** : les trois premiers tournent
en parallèle, le dernier ne démarre que si le backend et le frontend sont verts.

```
backend ──────┐
integration   ├──► docker
frontend ─────┘
```

---

## Ce qui est automatisé

### Job 1 — `backend` : lint + tests unitaires

```yaml
- run: flake8 .                                   # config dans backend/.flake8
- run: pytest --cov=. --cov-report=term-missing   # tests + couverture
```

Les tests unitaires remplacent la base par une fausse base en mémoire (`tests/conftest.py`) :
ils sont rapides et ne dépendent d'aucun service.

**Routes testées (exigence : 2 minimum)** — en pratique toutes les routes sensibles :

| Route | Ce qui est vérifié |
|---|---|
| `POST /api/register` | 201, email déjà pris → 400, email invalide / mot de passe trop court → 422 |
| `POST /api/login` | 200 + jeton, mauvais mot de passe → 401, 6ᵉ échec → 429, ligne fail2ban écrite |
| Routes admin | sans jeton → 401, utilisateur → 403, rôle falsifié dans le jeton → 403 |
| Routes « propriétaire » | accès au profil / aux candidatures d'un autre utilisateur → 403 |
| `GET /api/recommendations/{email}` | classement correct (faux modèle), cache, repli quand le profil n'a pas de compétences |

**Fonctions de normalisation testées (exigence : 1 minimum)** — `collector.py` :
`normalize()`, `parse_publish_date()` (secondes, millisecondes, microsecondes, ISO),
`extract_location()`, `texte_brut()` (suppression du HTML et des scripts).

### Job 2 — `integration` : tests sur un vrai MySQL 8

Un conteneur `mysql:8.0` est lancé comme *service* GitHub Actions. Les tests marqués
`@pytest.mark.integration` recréent le schéma depuis `db/init.sql` puis vérifient les vraies
requêtes SQL (insertion sans doublon, filtres, statistiques mensuelles, suppression…).

### Job 3 — `frontend` : lint + types + build

```yaml
- run: npm ci
- run: npm run lint        # ESLint (règles React Hooks incluses)
- run: npm run typecheck   # tsc -b
- run: npm run build       # build de production Vite
```

### Job 4 — `docker` : la stack complète démarre

```yaml
- run: docker compose config --quiet
- run: docker compose up -d --build --wait --wait-timeout 300
```

`--wait` attend que **tous les healthchecks** soient verts (MySQL, API, Nginx). Ensuite, des tests
de fumée passent par Nginx comme un vrai utilisateur : santé, liste des offres, inscription,
connexion, route protégée avec le jeton, route admin refusée (403). En cas d'échec, les journaux
des conteneurs sont affichés ; la stack est toujours arrêtée à la fin (`down -v`).

---

## Déclencheurs

```yaml
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

permissions:
  contents: read          # le workflow ne peut rien modifier dans le dépôt

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true   # un nouveau push annule l'exécution précédente
```

---

## Comment le pipeline protège la qualité

| Risque | Protection |
|---|---|
| Dockerfile ou compose cassé | Job `docker` : la stack doit démarrer et être saine |
| Régression sur l'auth (register/login) | Tests pytest sur les deux routes |
| Faille de contrôle d'accès | Tests 401 / 403 sur les routes admin et « propriétaire » |
| Requête SQL invalide | Job `integration` sur MySQL 8 |
| Normalisation WeLoveDevs corrompue | Tests unitaires de `collector.py` |
| Erreur de typage / hook React mal utilisé | `tsc` + ESLint |
| Code illisible / imports fantômes | flake8 |

---

## Alternative rejetée

### GitLab CI à la place de GitHub Actions
Rejeté — le dépôt est hébergé sur GitHub. GitHub Actions est natif, gratuit pour les dépôts publics, et ne nécessite pas d'infrastructure supplémentaire (runner auto-hébergé). L'intégration avec les PR GitHub est plus fluide.

### Pre-commit hooks seuls (sans CI)
Rejeté — les hooks locaux peuvent être contournés (`--no-verify`) ou ne pas être installés sur toutes les machines de l'équipe. La CI est le filet de sécurité centralisé qui s'applique indépendamment de l'environnement local.

---

## Trade-offs

**Pas de déploiement automatique (CD)** — Le pipeline s'arrête à la validation. Un déploiement
automatisé nécessiterait un serveur cible et des secrets de déploiement, hors du cadre du projet.

**Le modèle d'IA n'est pas téléchargé en CI** — Les tests de recommandation utilisent un faux modèle
(`tests/test_recommandations.py`) : on teste la logique de classement et de cache sans télécharger
PyTorch ni le modèle. Le job `docker` installe bien PyTorch (version CPU) dans l'image, mais avec
`WARMUP_MODEL=false` pour ne pas télécharger le modèle au démarrage.

**Pas de tests end-to-end navigateur** — Les tests de fumée du job `docker` passent par l'API.
Des tests Playwright seraient la prochaine étape.
