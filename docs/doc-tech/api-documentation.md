# Documentation de l'API — JobyFind

- **En local (Docker)** : l'API est servie derrière Nginx sur `http://localhost:8082/api/…`
  et directement sur `http://127.0.0.1:8000` (machine locale uniquement).
- **Documentation interactive** : `http://127.0.0.1:8000/docs` (Swagger généré par FastAPI).
- **Format** : JSON, sauf `POST /api/applications` (`multipart/form-data`).

---

## Authentification

Les routes protégées attendent un jeton JWT dans l'en-tête :

```
Authorization: Bearer <access_token>
```

Le jeton est obtenu avec `POST /api/login`. Il est signé en HS256 avec `JWT_SECRET`
et expire après `JWT_EXPIRE_MINUTES` (30 min par défaut).

### Niveaux d'accès

| Niveau | Règle |
|---|---|
| **Public** | Aucun jeton. |
| **Propriétaire** | Jeton valide **et** l'email de l'URL (ou du formulaire) est celui du jeton. Un admin passe aussi. |
| **Admin** | Jeton valide **et** `role_id = 2` relu **en base** à chaque appel : modifier le rôle dans le jeton ne sert à rien. |

| Code | Quand |
|---|---|
| `401` | Jeton absent, invalide ou expiré (en-tête `WWW-Authenticate: Bearer`). |
| `403` | Jeton valide mais ressource d'un autre utilisateur, ou route admin sans être admin. |

---

## Vue d'ensemble des routes

| Méthode | Route | Accès |
|---|---|---|
| `GET` | `/api/health` | Public |
| `POST` | `/api/register` | Public |
| `POST` | `/api/login` | Public (limité : 5 échecs / 10 min / IP) |
| `GET` | `/api/dashboard/stats` | Public |
| `GET` | `/api/dashboard/jobs` | Public |
| `GET` / `PUT` | `/api/dashboard/user/{email}` | Propriétaire |
| `GET` | `/api/dashboard/stats/monthly?email=` | Propriétaire |
| `GET` | `/api/recommendations/{email}` | Propriétaire |
| `POST` | `/api/applications` | Propriétaire |
| `GET` | `/api/applications/{email}` | Propriétaire |
| `POST` | `/api/fetch` | Admin |
| `GET` | `/api/admin/users` | Admin |
| `DELETE` | `/api/admin/users/{user_id}` | Admin |
| `GET` | `/api/admin/jobs` | Admin |
| `DELETE` | `/api/admin/jobs/{job_id}` | Admin |

---

## Santé

### `GET /api/health`

Vérifie que l'API répond **et** que la base est joignable. Utilisée par le `HEALTHCHECK` Docker.

| Code | Corps |
|---|---|
| `200` | `{"status": "ok", "database": "up"}` |
| `503` | `{"status": "degraded", "database": "down"}` |

---

## Authentification

### `POST /api/register`

```json
{
  "email": "camille@example.com",
  "password": "motdepasse-solide",
  "nom": "Camille Martin",
  "competences": "Docker, Linux, Python"
}
```

| Champ | Requis | Règle |
|---|---|---|
| `email` | ✓ | Email valide |
| `password` | ✓ | 8 à 128 caractères (haché en bcrypt) |
| `nom`, `prenom` | — | 120 caractères max |
| `competences` | — | Texte libre, séparé par des virgules |

| Code | Cas |
|---|---|
| `201` | Compte créé (rôle utilisateur) |
| `400` | Email déjà utilisé |
| `422` | Email invalide, mot de passe trop court… |

> On ne peut pas s'inscrire en admin : le premier admin est créé au démarrage
> à partir de `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

### `POST /api/login`

```json
{ "email": "camille@example.com", "password": "motdepasse-solide" }
```

Réponse `200` :

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs…",
  "token_type": "bearer",
  "email": "camille@example.com",
  "nom": "Camille Martin",
  "prenom": "Camille",
  "role_id": 1
}
```

| Code | Cas |
|---|---|
| `200` | Connexion réussie (le compteur d'échecs de l'IP est remis à zéro) |
| `401` | Email ou mot de passe incorrect (ligne écrite dans le journal lu par fail2ban) |
| `429` | Trop d'échecs depuis cette IP ; en-tête `Retry-After` en secondes |

---

## Offres (public)

### `GET /api/dashboard/stats`

```json
{ "total": 150, "cdi_count": 42 }
```

### `GET /api/dashboard/jobs`

| Paramètre | Description |
|---|---|
| `location` | Filtre « contient » sur la ville |
| `contract` | Filtre « contient » sur le type de contrat |

Renvoie au plus 1 000 offres, les plus récentes d'abord :

```json
[
  {
    "id": 12,
    "titre": "Ingénieur DevOps",
    "entreprise_nom": "Nordwave",
    "description": "Texte brut, sans HTML",
    "salaire_min": 40000,
    "salaire_max": 48000,
    "location": "Lille",
    "date": "2026-10-28",
    "contract_type": "CDI",
    "competences": "Docker, Kubernetes, Linux",
    "url": null,
    "source": "WeLoveDevs"
  }
]
```

---

## Profil (propriétaire)

### `GET /api/dashboard/user/{email}`

```json
{
  "email": "camille@example.com",
  "nom": "Camille Martin",
  "prenom": "Camille",
  "competences": "Docker, Linux, Python",
  "role_id": 1
}
```

`404` si l'utilisateur n'existe pas.

### `PUT /api/dashboard/user/{email}`

```json
{ "nom": "Camille Martin", "competences": "Docker, Linux, Python, Terraform" }
```

Un champ absent n'est pas modifié. Le rôle ne peut **pas** être changé par cette route.

### `GET /api/dashboard/stats/monthly?email=…`

Candidatures des 6 derniers mois (le passage d'une année à l'autre est géré) :

```json
[
  { "mois": "Juin", "envoyees": 0, "acceptees": 0, "refusees": 0 },
  { "mois": "Nov.", "envoyees": 3, "acceptees": 1, "refusees": 0 }
]
```

---

## Recommandations (propriétaire)

### `GET /api/recommendations/{email}`

Classe les offres selon la proximité entre les compétences du profil et le texte de l'offre
(titre, description, compétences), avec le modèle `paraphrase-multilingual-MiniLM-L12-v2`
(modifiable avec `EMBEDDING_MODEL`).

- Chaque offre reçoit un `matching_score` entre 0 et 100, triées du plus pertinent au moins pertinent.
- Les vecteurs des offres sont gardés en cache : une offre n'est encodée qu'une fois.
- **Repli** : si le profil n'a pas de compétences, ou si le modèle n'est pas disponible, la route
  renvoie la liste normale des offres **sans** `matching_score` (le front affiche alors un message).

---

## Candidatures (propriétaire)

### `POST /api/applications` — `multipart/form-data`

| Champ | Requis | Règle |
|---|---|---|
| `user_email` | ✓ | Doit être l'email du jeton (sauf admin) |
| `job_id` | ✓ | Entier |
| `company`, `position` | ✓ | 255 caractères max |
| `cv` | ✓ | `.pdf`, `.doc`, `.docx` ou `.odt`, 5 Mo max |
| `motivation_letter` | — | Mêmes règles que le CV |
| `message` | — | Texte libre |

| Code | Cas |
|---|---|
| `201` | Candidature enregistrée (statut « En attente ») |
| `400` | Format de fichier refusé |
| `413` | Fichier trop lourd |

> Les fichiers sont contrôlés mais pas stockés : seule la candidature est enregistrée en base.

### `GET /api/applications/{email}`

Liste des candidatures de l'utilisateur, la plus récente d'abord
(`id`, `user_email`, `job_id`, `company`, `position`, `date`, `status`, `color`).

---

## Administration (admin)

### `POST /api/fetch`

Lance une collecte WeLoveDevs immédiate. `400` si `WELOVEDEVS_API_KEY` n'est pas renseignée.
Sans action manuelle, la collecte tourne toute seule toutes les `COLLECT_INTERVAL_MINUTES`.

### `GET /api/admin/users`

```json
[{ "id": 1, "name": "Administrateur", "email": "admin@example.com", "role": "admin" }]
```

### `DELETE /api/admin/users/{user_id}`

| Code | Cas |
|---|---|
| `200` | Utilisateur supprimé |
| `400` | Tentative de supprimer son propre compte |
| `404` | Utilisateur introuvable |

### `GET /api/admin/jobs`

```json
[{ "id": 12, "title": "Ingénieur DevOps", "company": "Nordwave", "city": "Lille" }]
```

### `DELETE /api/admin/jobs/{job_id}`

`200` si l'offre est supprimée, `404` si elle n'existe pas.

---

## Codes HTTP utilisés

| Code | Signification |
|---|---|
| `200` / `201` | Succès / ressource créée |
| `400` | Requête refusée (email déjà pris, fichier invalide, auto-suppression…) |
| `401` | Non authentifié ou identifiants incorrects |
| `403` | Authentifié mais pas autorisé |
| `404` | Ressource introuvable |
| `413` | Fichier trop lourd |
| `422` | Validation Pydantic échouée |
| `429` | Trop de tentatives de connexion |
| `500` / `503` | Erreur serveur / base indisponible |
