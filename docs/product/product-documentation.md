# Documentation Produit — Analyse de Marché & Proposition de Valeur

---

## 1. Analyse de Marché

### Acteurs existants

| Plateforme | Positionnement | Forces | Faiblesses pour notre cible |
|---|---|---|---|
| **LinkedIn** | Réseau professionnel généraliste | Très grande base d'offres, réseau social | Pas de focus tech, recommandations comportementales, bruit important |
| **Indeed** | Agrégateur généraliste | Volume d'offres, SEO fort | Pas de filtres tech, pas d'analytics marché |
| **Welcome to the Jungle** | Marque employeur tech/startup | Contenu riche sur les entreprises, design soigné | Pas d'analytics marché, pas de recommandations par stack |
| **WeLoveDevs** | Emploi tech & développeurs | Données qualifiées, focus dev | Interface de recherche basique, pas de dashboard personnel |
| **Glassdoor** | Avis entreprises + offres | Transparence salariale | Peu d'offres françaises tech, pas de filtres stack |

### Tendances du marché

- **Tension sur les profils tech** : le marché de l'emploi développeur reste sous tension malgré les cycles de licenciements dans les grandes tech. Les profils juniors et les étudiants font face à une concurrence accrue pour les stages/alternances.
- **Opacité salariale** : malgré des lois sur la transparence salariale, la majorité des offres ne mentionnent pas de fourchette. Les candidats manquent de benchmark.
- **Fragmentation des plateformes** : un candidat actif consulte en moyenne 4 à 6 plateformes différentes lors de sa recherche.
- **Montée de l'IA dans le recrutement** : les ATS (Applicant Tracking Systems) filtrent de plus en plus les CVs automatiquement. Les candidats ont besoin de mieux cibler leurs candidatures.

---

## 2. Identification des Besoins Utilisateurs

### Persona principal : étudiant en école d'informatique (Bac+3 à Bac+5)

**Contexte :** Sacha, 21 ans, étudiant en 3ème année à Epitech. Il cherche son stage de fin d'études de 6 mois. Il maîtrise React, TypeScript et un peu de Node.js. Il ne sait pas si ses compétences sont dans les technologies actuellement demandées.

**Besoins identifiés :**

| Besoin | Priorité | Solution Jobify |
|---|---|---|
| Trouver des offres de stage tech centralisées | Haute | Agrégation WeLoveDevs + recherche unifiée |
| Savoir si ses compétences sont demandées | Haute | Feature AI de matching par stack |
| Comprendre les salaires pratiqués | Moyenne | Données salaire min/max sur chaque offre |
| Suivre ses candidatures | Moyenne | Dashboard candidatures avec statuts |
| Être alerté des nouvelles offres pertinentes | Moyenne | Notifications "nouvelle offre assortie" |
| Filtrer par type de contrat (stage vs CDI) | Haute | Filtres rapides par contract_type |
| Voir où se concentrent les offres en France | Faible | Carte géographique sur la landing page |

---

## 3. Proposition de Valeur

> **Jobify est la plateforme d'emploi tech pensée pour les étudiants et développeurs juniors : offres centralisées, vision du marché, et recommandations intelligentes basées sur votre stack technique.**

### Différenciation vs concurrents

| Critère | LinkedIn | WTTJ | WeLoveDevs | **Jobify** |
|---|---|---|---|---|
| Focus développeurs | Partiel | Oui | Oui | **Oui** |
| Données réelles marché | Non | Non | Non | **Oui (analytics)** |
| Matching par stack technique | Non | Non | Non | **Oui (AI)** |
| Suivi des candidatures | Partiel | Non | Non | **Oui** |
| Gratuit sans compte premium | Partiel | Oui | Oui | **Oui** |
| Carte géographique des offres | Non | Non | Non | **Oui** |

---

## 4. Wireframes / Maquettes des vues principales

Les captures d'écran ci-dessous documentent les vues implémentées. Elles valent comme wireframes de référence finals.

### Vue 1 — Landing Page
**Objectif :** Donner une vision immédiate du marché et permettre une recherche sans connexion.

Éléments clés : barre de recherche double (poste + ville), carte Leaflet des offres géolocalisées, navigation vers Inscription/Connexion.

---

### Vue 2 — Tableau de bord utilisateur
**Objectif :** Piloter sa recherche d'emploi en un coup d'œil.

Éléments clés : 4 compteurs de candidatures (envoyées / en attente / acceptées / refusées), tableau des candidatures avec statut coloré, section offres favorites.

---

### Vue 3 — Page Offres + Détail
**Objectif :** Trouver rapidement une offre pertinente et évaluer son adéquation.

Éléments clés : filtres par type de contrat, liste d'offres avec score de rating, panneau de détail avec encart **Analyse IA**, tags stack extraits automatiquement, bouton "Postuler maintenant".

---

### Vue 4 — Profil utilisateur
**Objectif :** Alimenter la feature de recommandation avec les compétences réelles.

Éléments clés : sélection multi-tags de langages/frameworks, sélecteur de niveau d'expérience (Junior / Intermédiaire / Senior).

---

### Vue 5 — Notifications
**Objectif :** Ramener l'utilisateur sur la plateforme avec des alertes contextuelles.

Éléments clés : 3 catégories (candidature retenue, nouvelle offre assortie, complétion de profil), horodatage relatif, suppression individuelle ou globale.

---

### Vue 6 — Panel Administration
**Objectif :** Modérer la plateforme (utilisateurs et offres).

Éléments clés : compteurs globaux (utilisateurs / connectés / offres), gestion des utilisateurs avec statut temps réel, gestion des offres avec suppression.

---

### Vue 7 — Paramètres / Accessibilité
**Objectif :** Permettre à chaque utilisateur d'adapter l'interface à ses besoins.

Éléments clés : mode sombre, mode daltonien, texte agrandi, lecteur vocal, sous-titres automatiques, langue du système.

---

## 5. Audit Accessibilité WCAG 2.1 Level AA

Le cahier des charges impose un audit documenté sur 3 flows : **inscription**, **recherche d'offre**, **détail d'offre**.

> ⚠️ **À compléter par l'équipe** : lancer Lighthouse (onglet Chrome DevTools → Lighthouse → Accessibility) sur chacun des 3 flows et copier les scores ici.

### Template de résultat à remplir

| Flow | Outil | Score | Date | Problèmes identifiés | Corrections appliquées |
|---|---|---|---|---|---|
| Inscription (`/register`) | Lighthouse | — / 100 | — | — | — |
| Recherche d'offre (`/offres`) | Lighthouse | — / 100 | — | — | — |
| Détail d'offre (`/offres/:id`) | Lighthouse | — / 100 | — | — | — |

**Éléments WCAG déjà couverts par les Paramètres d'accessibilité :**
- Mode daltonien (critère 1.4.1 — Usage of Color)
- Texte agrandi (critère 1.4.4 — Resize Text)
- Lecteur vocal (critère 1.3.1 — Info and Relationships)
- Sous-titres automatiques (critère 1.2.2 — Captions)
