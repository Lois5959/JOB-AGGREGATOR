# ADR-006 — Choix CI/CD

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | Mai 2026 |
| **Décideurs** | Équipe Job Aggregator |

---

## Contexte

Le cahier des charges impose GitHub Actions comme système CI, avec exécution automatique sur les pull requests et les pushs sur `main`. Le pipeline doit inclure a minima : build checks, lint/quality checks, et tests automatisés couvrant deux routes backend et une fonction de normalisation.

---

## Décision

Mettre en place un pipeline GitHub Actions en deux jobs distincts : **build** et **test**, déclenchés sur `push` (main) et `pull_request`.

---

## Ce qui est automatisé

### Job 1 — Build Docker

Vérifie que les images Docker se construisent sans erreur à partir des `Dockerfile` existants.

```yaml
- name: Build frontend image
  run: docker build ./front-end

- name: Build backend image
  run: docker build ./backend
```

**Pourquoi ce check ?**
Un `Dockerfile` cassé (dépendance introuvable, instruction invalide) serait détecté immédiatement, avant que n'importe quel développeur tente de lancer le projet localement ou en production.

---

### Job 2 — Tests backend (pytest)

Lance les tests unitaires et d'intégration du backend dans un environnement Python isolé.

**Routes testées (exigence : 2 minimum) :**

| Route | Méthode | Test |
|---|---|---|
| `/api/register` | POST | Inscription valide → 201, email déjà utilisé → 400 |
| `/api/login` | POST | Credentials valides → 200 + token, mauvais mdp → 401 |

**Fonction de normalisation testée (exigence : 1 minimum) :**

| Fonction | Fichier | Test |
|---|---|---|
| `normalize()` | `api.py` | Offre complète → dict normalisé, champ `titre` absent → `None` |
| `extract_location()` | `api.py` | Liste de dicts → ville extraite, string → première partie avant virgule |

```yaml
- name: Install dependencies
  run: pip install -r backend/requirements.txt

- name: Run tests
  run: pytest backend/tests/ -v
```

---

### Job 3 — Lint (flake8)

Vérifie la qualité syntaxique et le style du code Python.

```yaml
- name: Lint with flake8
  run: flake8 backend/ --max-line-length=120 --exclude=__pycache__
```

**Pourquoi flake8 ?**
Détecte les imports inutilisés, les variables non définies, et les violations de style PEP8. Intégré nativement dans les environnements Python sans configuration lourde.

---

## Déclencheurs

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

Chaque PR vers `main` doit passer tous les jobs avant de pouvoir être mergée. Cela empêche l'introduction de régressions silencieuses.

---

## Comment le pipeline protège la qualité

| Risque | Protection |
|---|---|
| Dockerfile cassé après modification | Job build échoue immédiatement |
| Régression sur l'auth (register/login) | Tests pytest sur les deux routes |
| Normalisation WeLoveDevs corrompue | Test unitaire sur `normalize()` |
| Code illisible / imports fantômes | Flake8 bloque la PR |
| Merge accidentel sans review | CI obligatoire avant merge sur main |

---

## Alternative rejetée

### GitLab CI à la place de GitHub Actions
Rejeté — le dépôt est hébergé sur GitHub. GitHub Actions est natif, gratuit pour les dépôts publics, et ne nécessite pas d'infrastructure supplémentaire (runner auto-hébergé). L'intégration avec les PR GitHub est plus fluide.

### Pre-commit hooks seuls (sans CI)
Rejeté — les hooks locaux peuvent être contournés (`--no-verify`) ou ne pas être installés sur toutes les machines de l'équipe. La CI est le filet de sécurité centralisé qui s'applique indépendamment de l'environnement local.

---

## Trade-offs

**Pas de déploiement automatique (CD)** — Le pipeline s'arrête à la validation. Un déploiement automatisé en production nécessiterait un environnement cible stable (serveur, secrets de déploiement) qui dépasse le cadre du projet.

**Tests d'intégration limités** — Les tests des routes API nécessitent une base de données. Pour les garder rapides en CI, les tests utilisent des mocks ou une base SQLite en mémoire à la place de MySQL. Les tests end-to-end (Playwright, Cypress) ne sont pas inclus dans ce pipeline.

**`torch` dans les dépendances** — L'installation de PyTorch CPU en CI est longue (~2 min). L'usage du cache pip de GitHub Actions (`actions/cache`) réduit ce temps sur les exécutions suivantes.
