# ADR-002 — Choix Dashboard & Fonctionnalités Clés

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | Mai 2026 |
| **Décideurs** | Équipe Job Aggregator |

---

## Contexte

Le cahier des charges impose qu'au moins un output de la feature data et un output de la feature AI soient visibles sur le dashboard sans navigation supplémentaire. La plateforme **Jobify** doit aider un étudiant en informatique à piloter sa recherche d'emploi et à comprendre le marché tech, sans qu'il ait besoin de consulter plusieurs plateformes en parallèle.

---

## Vues implémentées et justification

### 1. Page d'accueil — Carte géographique des offres

**Capture :** `landing page` avec carte Leaflet/OpenStreetMap et barre de recherche double (poste + ville).

**Problème utilisateur adressé**
Un étudiant ne sait pas où se concentrent les offres tech en France. La carte lui donne immédiatement une vision géographique du marché sans avoir à lancer une recherche.

**Décision**
Intégrer une carte interactive (Leaflet + OpenStreetMap) sur la landing page, avec les offres géolocalisées représentées par des marqueurs. La barre de recherche principale (poste + localisation) est accessible sans connexion.

**Pourquoi Leaflet/OpenStreetMap plutôt que Google Maps**
OpenStreetMap est gratuit et sans quota d'API, ce qui évite toute dépendance à une clé facturable et s'aligne avec l'exigence de secret management.

**Trade-off**
La précision de géolocalisation dépend de la qualité des données d'adresse dans les offres WeLoveDevs. Des adresses vagues ("France", "Remote") ne peuvent pas être placées précisément sur la carte.

---

### 2. Tableau de bord utilisateur — Suivi des candidatures

**Capture :** `Tableau de bord` avec 4 compteurs (Envoyées: 12, En attente: 8, Acceptées: 2, Refusées: 2) + tableau des candidatures avec statut coloré + section "Offres favorites".

**Problème utilisateur adressé**
Un étudiant qui postule sur plusieurs offres perd rapidement le fil de ses candidatures (date d'envoi, réponse reçue, offre relancée ou non). Il n'existe pas de suivi centralisé sur les plateformes généralistes.

**Décision**
Implémenter un tableau de bord personnel affichant :
- Des compteurs de statut en temps réel (envoyées, en attente, acceptées, refusées)
- Un tableau des candidatures triable et filtrable avec accès rapide au détail
- Une section "Offres favorites" pour retrouver les offres épinglées

**Quelle décision utilisateur ce widget supporte-t-il ?**
"Est-ce que je dois relancer cette entreprise ?" → le statut "En attente" depuis X jours répond directement.

**Trade-off**
Le suivi des candidatures est manuel (l'utilisateur met à jour lui-même le statut). Une intégration automatique avec les plateformes de recrutement nécessiterait des APIs privées non disponibles dans ce contexte.

---

### 3. Page Offres — Recherche, filtres et Analyse IA

**Capture :** `Offres` avec liste d'offres filtrables (Tous / CDI / Stage / Freelance) + panneau de détail avec encart **"Analyse IA"** et tags de stack technique.

**Problème utilisateur adressé**
Les descriptions d'offres sont longues et hétérogènes. Un étudiant perd du temps à lire chaque offre pour déterminer si elle correspond à son profil technique.

**Décision — Filtres par type de contrat**
Filtres rapides (Tous / CDI / Stage / Freelance) accessibles en un clic sans rechargement de page. Répond au besoin des étudiants qui cherchent spécifiquement des stages ou alternances.

**Décision — Encart "Analyse IA"**
Un résumé généré automatiquement apparaît dans le panneau de détail de chaque offre. Exemple observé : *"Poste senior avec focus sur l'architecture frontend moderne. Stack technique alignée avec votre profil."*

L'IA extrait et résume les points clés de l'offre (niveau requis, focus technique, adéquation profil) pour éviter à l'utilisateur de lire l'intégralité de la description.

**Décision — Tags stack technique**
Les technologies requises (React, TypeScript, Next.js, Tailwind CSS, GraphQL) sont extraites automatiquement de la description et affichées sous forme de tags. Cela permet une lecture rapide et alimente la logique de recommandation basée sur le profil utilisateur.

**Quelle décision utilisateur ce widget supporte-t-il ?**
"Est-ce que cette offre correspond à ma stack ?" → les tags et l'analyse IA répondent en 5 secondes sans lire la description complète.

**Trade-off**
La qualité de l'analyse IA dépend de la richesse de la description source. Les offres avec des descriptions très courtes produiront des analyses moins pertinentes.

---

### 4. Page Profil — Stack technique et niveau d'expérience

**Capture :** `Profil` avec sélection multi-tags de langages/frameworks (React, TypeScript, Node.js, Python, Java, C++, PHP, Vue.js, Angular, Swift) et sélecteur de niveau (Junior 0-2 ans).

**Problème utilisateur adressé**
Sans profil technique renseigné, il est impossible de personnaliser les recommandations d'offres. Les plateformes généralistes ne proposent pas de sélection de stack structurée.

**Décision**
Implémenter un profil utilisateur avec sélection de technologies par tags (UI rapide, pas de champ texte libre) et niveau d'expérience. Ces données alimentent directement la feature AI de recommandation et l'adéquation affichée dans l'analyse IA des offres.

**Trade-off**
La liste de technologies est prédéfinie, ce qui simplifie le matching mais peut exclure des technologies moins courantes. Un champ texte libre aurait été plus flexible mais aurait complexifié la normalisation pour le matching.

---

### 5. Notifications — Alertes contextuelles

**Capture :** `Notifications` avec 3 types d'alertes : candidature retenue (vert), nouvelle offre assortie (bleu), complétion de profil (orange).

**Problème utilisateur adressé**
Un étudiant en recherche active ne revient pas consulter la plateforme tous les jours. Les notifications proactives le ramènent au bon moment.

**Décision**
Trois catégories de notifications :
- **Candidature retenue** — alerte sur changement de statut
- **Nouvelle offre assortie** — alerte quand une offre correspond au profil (output direct de la feature AI)
- **Complétion de profil** — onboarding progressif pour améliorer la qualité des recommandations

**Quelle décision utilisateur ce widget supporte-t-il ?**
"Est-ce qu'il y a des nouveautés qui me concernent ?" → sans avoir à naviguer dans les offres.

**Trade-off**
Les notifications "nouvelle offre assortie" nécessitent que le profil soit suffisamment renseigné. Un utilisateur avec un profil vide ne recevra pas de notifications pertinentes, d'où la notification d'onboarding.

---

### 6. Panel Administration — Gestion utilisateurs et offres

**Capture :** `Panel Administration` avec compteurs globaux (3 utilisateurs, 2 connectés, 2 offres) + table de gestion des utilisateurs (nom, email, statut en ligne) + table de gestion des offres d'emploi.

**Problème adressé**
Le cahier des charges impose une interface d'administration pour la modération. Sans cela, il est impossible de gérer les utilisateurs problématiques ou de supprimer des offres non conformes.

**Décision**
Interface admin accessible uniquement au rôle `admin` (enforcement server-side via JWT + vérification de rôle). Fonctionnalités : suppression d'utilisateurs, suppression d'offres, vue du statut de connexion en temps réel.

**Trade-off**
L'interface actuelle ne permet pas la modification d'offres (seulement la suppression). Une feature d'édition complète aurait demandé plus de temps de développement et n'était pas strictement requise.

---

### 7. Paramètres — Accessibilité

**Capture :** `Paramètres` avec Mode Sombre, Mode Daltonien, Texte Agrandi, Lecteur Vocal, Sous-titres automatiques, Langue du système.

**Problème adressé**
Le cahier des charges impose WCAG 2.1 Level AA sur au moins 3 flows. Les paramètres d'accessibilité permettent d'aller au-delà de l'exigence minimale en donnant le contrôle à l'utilisateur.

**Décision**
Page Paramètres dédiée avec 4 catégories : Apparence (mode sombre), Vision (daltonisme, texte agrandi), Accessibilité Audio (lecteur vocal, sous-titres), Langue.

**Trade-off**
Certaines fonctionnalités (lecteur vocal natif) s'appuient sur les APIs du navigateur et peuvent varier selon l'environnement. L'implémentation est une surcouche aux fonctionnalités système, pas un remplacement.

---

## Résumé des widgets et décisions supportées

| Vue | Widget | Décision utilisateur supportée |
|---|---|---|
| Accueil | Carte géographique | "Où sont les offres ?" |
| Tableau de bord | Compteurs + tableau candidatures | "Où en sont mes candidatures ?" |
| Offres | Analyse IA + tags stack | "Cette offre me correspond-elle ?" |
| Offres | Filtres contrat | "Quels types de contrat chercher ?" |
| Profil | Sélection stack + niveau | "Comment affiner mes recommandations ?" |
| Notifications | Alertes contextuelles | "Y a-t-il des nouveautés pour moi ?" |
| Admin | Gestion utilisateurs/offres | "La plateforme est-elle saine ?" |
| Paramètres | Accessibilité | "Puis-je adapter l'interface à mes besoins ?" |
