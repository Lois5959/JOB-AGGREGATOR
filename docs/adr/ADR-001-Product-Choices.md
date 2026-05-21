# ADR-001 — Choix Produit

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | Mai 2026 |
| **Décideurs** | Équipe Job Aggregator |

---

## Contexte

Les étudiants en école d'ingénierie et d'informatique cherchent activement des stages, alternances et premiers emplois dans le secteur tech. Ils utilisent aujourd'hui de multiples plateformes (LinkedIn, Indeed, Welcome to the Jungle, WeLoveDevs…) sans pouvoir avoir une vue consolidée du marché, ni bénéficier de recommandations adaptées à leur profil et à leur stack technique.

Ce projet a été conçu dans le cadre du partenariat Epitech / WeLoveDevs, qui donne accès à des données réelles du marché de l'emploi tech.

---

## Problème

> **"Un étudiant en informatique ne sait pas où il en est par rapport au marché : quelles stacks sont demandées, quels salaires sont pratiqués, et quelles offres correspondent vraiment à son profil."**

### Pain points identifiés

**Pain point principal — Absence de vision globale du marché**
Les plateformes généralistes (LinkedIn, Indeed) n'offrent pas d'analytics orientés tech : pas de distribution des salaires par stack, pas de tendances sur les technologies demandées, pas de comparaison entre types de contrat. L'étudiant navigue à l'aveugle.

**Pain point secondaire — Absence de recommandations pertinentes**
Les recommandations des grandes plateformes sont basées sur des signaux comportementaux (clics, candidatures) sans tenir compte du profil technique réel de l'utilisateur. Une offre "Développeur Java Senior 10 ans d'expérience" peut apparaître pour un étudiant en L3.

---

## Utilisateurs cibles

**Profil principal : étudiant en école d'ingénierie / informatique (Bac+3 à Bac+5)**

- Cherche un stage, une alternance ou un premier emploi dans le secteur tech
- A une stack technique en cours de construction (1 à 3 langages/frameworks maîtrisés)
- Manque de recul sur les standards du marché (salaires, technologies demandées)
- Utilise plusieurs plateformes en parallèle sans vue consolidée

**Profil secondaire : développeur junior en début de carrière (0-2 ans d'expérience)**

- Mêmes besoins de visibilité marché
- Plus autonome dans ses recherches, sensible aux données comparatives

---

## Décision

Construire une plateforme d'agrégation d'offres **orientée tech**, combinant trois axes de valeur :

### Axe 1 — Agrégation centralisée orientée dev
Collecter les offres depuis WeLoveDevs (source obligatoire) et les normaliser dans un modèle de données commun. L'utilisateur accède à un point d'entrée unique au lieu de multiplier les plateformes.

### Axe 2 — Dashboard analytics et tendances
Offrir une vision du marché que les plateformes généralistes ne proposent pas : distribution des salaires, technologies les plus demandées, répartition par type de contrat et localisation. Cela répond directement au pain point principal.

### Axe 3 — Feature AI de recommandation / extraction
Exploiter les données ingérées pour proposer des offres pertinentes selon le profil utilisateur, ou extraire automatiquement les compétences clés d'une offre. Cela répond au pain point secondaire sans dépendre d'un historique comportemental.

---

## Alternatives rejetées

**Plateforme généraliste (toutes industries)**
Rejetée car la valeur différenciante repose sur la spécialisation tech. Une cible généraliste diluerait les analytics et rendrait les recommandations moins pertinentes.

**Agrégation seule sans analytics ni AI**
Rejetée car elle ne résout que marginalement le problème : l'utilisateur aurait certes moins de plateformes à consulter, mais toujours pas de vision du marché ni de recommandations adaptées.

**Outil de veille pure (sans compte utilisateur)**
Rejetée car sans profil utilisateur il est impossible de personnaliser les recommandations ni de mesurer la valeur apportée.

---

## Proposition de valeur

| Plateforme | Données tech | Analytics marché | Recommandations profil | Agrégation |
|---|---|---|---|---|
| LinkedIn | Partiel | Non | Comportemental | Non |
| Indeed | Non | Non | Non | Non |
| Welcome to the Jungle | Oui | Non | Non | Non |
| **Job Aggregator** | **Oui** | **Oui** | **Oui (AI)** | **Oui** |

---

## Mesure du succès

| Hypothèse | Indicateur | Cible |
|---|---|---|
| Les analytics aident à mieux cibler | Taux d'utilisation du dashboard | > 60 % des sessions connectées |
| Les recommandations sont pertinentes | Taux de clic sur offres recommandées vs liste générale | Recommandées > liste générale |
| La plateforme centralise utilement | Nombre d'offres consultées par session | > 5 offres / session |

---

## Trade-offs

**Spécialisation tech** — La plateforme est peu utile pour des offres hors développement logiciel. C'est un choix assumé : mieux servir un segment restreint que mal servir tout le monde.

**Dépendance à WeLoveDevs** — L'intégration est obligatoire selon le cahier des charges. En cas de changement de l'API ou de coupure, la source de données principale est compromise. Mitigation : architecture d'ingestion modulaire permettant d'ajouter d'autres sources.

**AI légère contrainte** — Le modèle AI doit tenir dans 500 MB et répondre en moins de 5 secondes. Cela limite les approches (pas de LLM, pas de modèle de deep learning lourd) mais reste cohérent avec l'objectif d'une feature utile et déployable.
