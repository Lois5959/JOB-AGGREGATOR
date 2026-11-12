# Schéma de la Base de Données — JobyFind

## Vue d'ensemble

Base de données relationnelle **MySQL 8.0**. Le schéma est initialisé automatiquement au premier démarrage du conteneur `db` via le fichier `db/init.sql` monté dans `/docker-entrypoint-initdb.d/`.

---

## Diagramme des tables

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────────┐
│    roles    │         │  utilisateurs    │         │    offres       │
│─────────────│         │──────────────────│         │─────────────────│
│ id (PK)     │◄────────│ id (PK)          │         │ id (PK)         │
│ name UNIQUE │    FK   │ nom              │         │ titre           │
└─────────────┘         │ email UNIQUE     │         │ entreprise_nom  │
                        │ password         │         │ description     │
                        │ competences      │         │ salaire_min     │
                        │ role_id (FK)     │         │ salaire_max     │
                        └──────────────────┘         │ location        │
                                 │                   │ date            │
                                 │                   │ contract_type   │
                        ┌────────▼─────────┐         │ source          │
                        │  candidatures    │         │ url             │
                        │──────────────────│         │ competences     │
                        │ id (PK)          │         │ UNIQUE(titre,   │
                        │ user_email       │         │  entreprise_nom)│
                        │ job_id           │         └─────────────────┘
                        │ company          │
                        │ position         │
                        │ date             │
                        │ status           │
                        │ color            │
                        └──────────────────┘
```

---

## Détail des tables

### `roles`

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | INT | PK, AUTO_INCREMENT | Identifiant unique |
| `name` | VARCHAR(255) | NOT NULL, UNIQUE | Nom du rôle |

**Données initiales :**

| id | name |
|---|---|
| 1 | utilisateur |
| 2 | admin |

---

### `utilisateurs`

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | INT | PK, AUTO_INCREMENT | Identifiant unique |
| `nom` | VARCHAR(255) | NOT NULL | Nom affiché |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | Email de connexion |
| `password` | TEXT | NOT NULL | Hash bcrypt du mot de passe |
| `competences` | TEXT | NULL | Stack technique (texte libre, ex: "React, TypeScript") |
| `role_id` | INT | NOT NULL, FK → roles(id) | Rôle de l'utilisateur |

**Contraintes d'intégrité :**
- `UNIQUE` sur `email` : empêche les doublons de compte
- `FOREIGN KEY (role_id) REFERENCES roles(id)` : garantit qu'aucun utilisateur n't a un rôle inexistant
- `password` stocké sous forme de hash bcrypt uniquement, jamais en clair

---

### `offres`

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | INT | PK, AUTO_INCREMENT | Identifiant unique |
| `titre` | TEXT | NOT NULL | Intitulé du poste |
| `entreprise_nom` | VARCHAR(255) | NOT NULL | Nom de l'entreprise |
| `description` | TEXT | NOT NULL | Description complète |
| `salaire_min` | INT | NULL | Salaire minimum (€/an) |
| `salaire_max` | INT | NULL | Salaire maximum (€/an) |
| `location` | TEXT | NULL | Lieu (ville ou "Remote") |
| `date` | DATE | NOT NULL | Date de publication |
| `contract_type` | TEXT | NULL | Type de contrat (CDI, Stage, Freelance…) |
| `source` | TEXT | NOT NULL | Origine de l'offre (ex: "WeLoveDevs") |
| `url` | VARCHAR(500) | NULL | Lien vers l'offre originale |
| `competences` | TEXT | NULL | Stack technique extraite |

**Contraintes d'intégrité :**
- `UNIQUE KEY idx_unique_offre (titre(100), entreprise_nom(100))` : empêche les doublons d'offres à l'insertion (couplé à `INSERT IGNORE`)
- `date NOT NULL` : chaque offre doit avoir une date de publication
- `source NOT NULL` : traçabilité de l'origine des données obligatoire

---

### `candidatures`

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | INT | PK, AUTO_INCREMENT | Identifiant unique |
| `user_email` | VARCHAR(255) | NOT NULL | Email de l'utilisateur |
| `job_id` | INT | NOT NULL | Référence à l'offre |
| `company` | VARCHAR(255) | NOT NULL | Nom de l'entreprise |
| `position` | VARCHAR(255) | NOT NULL | Intitulé du poste |
| `date` | DATE | NOT NULL | Date de candidature |
| `status` | VARCHAR(50) | DEFAULT 'En attente' | Statut (En attente / Acceptée / Refusée) |
| `color` | VARCHAR(20) | DEFAULT 'orange' | Couleur d'affichage du statut |

---

## Persistance

Les données MySQL sont stockées dans un volume Docker nommé `db_data`, monté sur `/var/lib/mysql` dans le conteneur. Ce volume **survit aux redémarrages** du conteneur (`restart: unless-stopped`) et aux `docker compose down` sans `-v`.

```yaml
# docker-compose.yml
volumes:
  db_data:

# service db
volumes:
  - db_data:/var/lib/mysql
  - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
```

---

## Initialisation automatique

Le fichier `db/init.sql` est exécuté automatiquement par MySQL au premier démarrage si la base est vide. Il utilise `CREATE TABLE IF NOT EXISTS` et `INSERT IGNORE` pour être idempotent (ré-exécutable sans erreur).
