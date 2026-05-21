# Documentation API Backend — Jobify

**Base URL :** `http://localhost:8000`
**Framework :** FastAPI + Uvicorn
**Format :** JSON (Content-Type: application/json)
**Documentation interactive :** `http://localhost:8000/docs` (Swagger UI généré automatiquement)

---

## Authentification

Les routes protégées utilisent un token JWT Bearer transmis dans le header :

```
Authorization: Bearer <access_token>
```

Le token est obtenu via `POST /api/login` et expire après **30 minutes**.

---

## Routes d'authentification

### `POST /api/register`

Crée un nouveau compte utilisateur.

**Corps de la requête :**

```json
{
  "email": "user@example.com",
  "password": "motdepasse123",
  "nom": "Sacha Bouron",
  "competences": "React, TypeScript, Node.js"
}
```

| Champ | Type | Requis | Description |
|---|---|---|---|
| `email` | EmailStr | ✓ | Email valide (validé par Pydantic) |
| `password` | string | ✓ | Mot de passe en clair (haché côté serveur) |
| `nom` | string | — | Nom affiché (défaut : "Utilisateur") |
| `competences` | string | — | Stack technique libre |

**Réponses :**

| Code | Cas |
|---|---|
| `201 Created` | Compte créé avec succès |
| `400 Bad Request` | Email déjà utilisé |
| `422 Unprocessable Entity` | Email invalide ou champ requis manquant |
| `500 Internal Server Error` | Erreur base de données |

---

### `POST /api/login`

Authentifie un utilisateur et retourne un token JWT.

**Corps de la requête :**

```json
{
  "email": "user@example.com",
  "password": "motdepasse123"
}
```

**Réponse 200 :**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "email": "user@example.com",
  "nom": "Sacha Bouron"
}
```

| Code | Cas |
|---|---|
| `200 OK` | Authentification réussie |
| `401 Unauthorized` | Email ou mot de passe incorrect |

---

## Routes Dashboard

### `GET /api/dashboard/stats`

Retourne les compteurs globaux pour l'en-tête du dashboard.

**Réponse 200 :**

```json
{
  "total": 150,
  "cdi_count": 42
}
```

---

### `GET /api/dashboard/jobs`

Retourne la liste des offres avec filtres optionnels.

**Paramètres de requête :**

| Paramètre | Type | Description |
|---|---|---|
| `location` | string (optionnel) | Filtre par ville (LIKE %location%) |
| `contract` | string (optionnel) | Filtre par type de contrat (LIKE %contract%) |

**Exemple :** `GET /api/dashboard/jobs?location=Paris&contract=CDI`

**Réponse 200 :**

```json
[
  {
    "id": 1,
    "titre": "Senior Frontend Developer",
    "entreprise_nom": "TechVision",
    "description": "...",
    "salaire_min": 55000,
    "salaire_max": 70000,
    "location": "Paris",
    "date": "2024-05-12",
    "contract_type": "CDI",
    "competences": "React, TypeScript",
    "url": "https://welovedevs.com/..."
  }
]
```

---

### `GET /api/dashboard/user/{email}`

Retourne les informations de profil d'un utilisateur.

**Paramètre de chemin :** `email` — adresse email de l'utilisateur

**Réponse 200 :**

```json
{
  "email": "user@example.com",
  "nom": "Sacha Bouron",
  "competences": "React, TypeScript, Node.js",
  "role_id": 1
}
```

**Réponse si non trouvé :**

```json
{ "error": "Utilisateur non trouvé" }
```

---

### `PUT /api/dashboard/user/{email}`

Met à jour le profil d'un utilisateur (nom et compétences).

**Corps de la requête :**

```json
{
  "nom": "Sacha Bouron",
  "competences": "React, TypeScript, Python"
}
```

| Code | Cas |
|---|---|
| `200 OK` | Profil mis à jour |
| `500 Internal Server Error` | Erreur base de données |

---

## Routes IA / Recommandations

### `GET /api/recommendations/{email}`

Retourne toutes les offres triées par score de matching avec le profil de l'utilisateur.

Le scoring utilise la similarité cosinus entre l'embedding des compétences de l'utilisateur et l'embedding `titre + entreprise + description` de chaque offre (modèle `all-MiniLM-L6-v2`).

**Paramètre de chemin :** `email` — adresse email de l'utilisateur

**Réponse 200 :**

```json
[
  {
    "id": 1,
    "titre": "Senior Frontend Developer",
    "entreprise_nom": "TechVision",
    "matching_score": 87.43,
    ...
  },
  {
    "id": 5,
    "titre": "Data Scientist",
    "matching_score": 12.11,
    ...
  }
]
```

**Réponse si profil vide :**

```json
{ "error": "Compétences non renseignées ou utilisateur introuvable" }
```

---

## Routes Candidatures

### `POST /api/applications`

Enregistre une nouvelle candidature.

**Corps de la requête :**

```json
{
  "user_email": "user@example.com",
  "job_id": 42,
  "company": "TechVision",
  "position": "Senior Frontend Developer"
}
```

| Code | Cas |
|---|---|
| `200 OK` | Candidature enregistrée |
| `500 Internal Server Error` | Erreur base de données |

---

### `GET /api/applications/{email}`

Retourne toutes les candidatures d'un utilisateur, triées par ID décroissant.

**Réponse 200 :**

```json
[
  {
    "id": 3,
    "user_email": "user@example.com",
    "job_id": 42,
    "company": "TechVision",
    "position": "Senior Frontend Developer",
    "date": "2024-05-12",
    "status": "En attente",
    "color": "orange"
  }
]
```

---

## Routes Administration (rôle admin requis)

### `GET /api/admin/users`

Retourne tous les utilisateurs avec leur rôle.

**Réponse 200 :**

```json
[
  {
    "id": 1,
    "name": "Sacha Bouron",
    "email": "sacha.bouron@icloud.com",
    "role": "admin"
  }
]
```

---

### `DELETE /api/admin/users/{user_id}`

Supprime définitivement un utilisateur.

| Code | Cas |
|---|---|
| `200 OK` | Utilisateur supprimé |
| `500 Internal Server Error` | Échec de la suppression |

---

### `GET /api/admin/jobs`

Retourne toutes les offres au format tableau d'administration.

**Réponse 200 :**

```json
[
  {
    "id": 1,
    "title": "Développeur Fullstack",
    "company": "TechCorp",
    "city": "Paris"
  }
]
```

---

### `DELETE /api/admin/jobs/{job_id}`

Supprime définitivement une offre d'emploi.

| Code | Cas |
|---|---|
| `200 OK` | Offre supprimée |
| `500 Internal Server Error` | Échec de la suppression |

---

## Route de collecte manuelle

### `POST /api/fetch`

Déclenche manuellement une collecte depuis l'API WeLoveDevs (20 pages × 50 offres max).

**Réponse 200 :**

```json
{ "message": "1000 offres collectées" }
```

ou si aucune donnée :

```json
{ "message": "Aucune nouvelle offre trouvée." }
```

---

## Codes HTTP utilisés

| Code | Signification |
|---|---|
| `200 OK` | Succès |
| `201 Created` | Ressource créée |
| `400 Bad Request` | Données invalides ou conflit (ex: email existant) |
| `401 Unauthorized` | Credentials incorrects |
| `422 Unprocessable Entity` | Validation Pydantic échouée |
| `500 Internal Server Error` | Erreur serveur ou base de données |
