# ADR-005 — Choix AI

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | Mai 2026 (mis à jour en novembre 2026) |
| **Décideurs** | Équipe Job Aggregator |

---

## Contexte

Le cahier des charges impose une feature AI légère : modèle ≤ 500 MB sur disque, résultat en moins de 5 secondes par offre, pas de fine-tuning au démarrage, et aucune dépendance à une API externe non contrôlée.

---

## Problème adressé

Un étudiant renseigne ses compétences (ex : "React, TypeScript, Node.js") dans son profil. La plateforme doit lui retourner les offres les plus pertinentes sans qu'il ait à relire chaque description manuellement.

---

## Décision : similarité sémantique avec `paraphrase-multilingual-MiniLM-L12-v2`

### Modèle retenu

**`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`** via la bibliothèque `sentence-transformers`
(modifiable avec la variable `EMBEDDING_MODEL`).

| Critère | Valeur |
|---|---|
| Taille sur disque | ~470 MB |
| Temps d'inférence | < 1 seconde par offre (CPU) |
| Fine-tuning requis | Non |
| API externe | Non (exécution locale) |
| Langues | Multilingue (50+ langues, dont le français) |
| Type | Modèle encodeur (embeddings de 384 dimensions) |

Le modèle transforme un texte en vecteur numérique. Deux textes sémantiquement proches produisent des vecteurs proches. Le modèle multilingue a été préféré à `all-MiniLM-L6-v2` (~90 MB, anglais) car les offres WeLoveDevs et les profils sont majoritairement en **français**.

---

## Implémentation (`backend/feature_ia.py`)

1. **Texte du profil** : les compétences de l'utilisateur (répétées pour peser plus).
2. **Texte de l'offre** : titre et compétences (répétés), entreprise, début de la description.
3. **Similarité cosinus** entre le vecteur du profil et celui de chaque offre.
4. **Score lisible** : le cosinus (en pratique entre 0,15 et 0,75) est ramené à un pourcentage 0–100.
5. Tri des offres par score décroissant.

```python
user_embedding = model.encode(build_user_text(user_data), convert_to_tensor=True)
similarities = util.cos_sim(user_embedding, _job_embeddings(model, jobs))[0]
for i, job in enumerate(jobs):
    job["matching_score"] = normalize_score(float(similarities[i].item()))
return sorted(jobs, key=lambda j: j["matching_score"], reverse=True)
```

### Performances

- **Chargement paresseux** : le modèle n'est chargé qu'au premier besoin, protégé par un verrou
  (pas de double chargement si deux requêtes arrivent en même temps). Avec `WARMUP_MODEL=true`,
  il est préchargé en arrière-plan au démarrage, sans bloquer l'API.
- **Cache des vecteurs** : chaque offre est encodée **une seule fois**. Le cache est indexé par
  l'id de l'offre et l'empreinte SHA-1 de son texte : une offre modifiée est ré-encodée,
  les autres non. Les nouvelles offres sont encodées par lots (`batch_size=64`).
- **Volume Docker `hf_cache`** : le modèle téléchargé est conservé entre deux redémarrages.

### Repli

Si le profil n'a pas de compétences, ou si le modèle ne peut pas être chargé (pas de réseau au
premier lancement, mémoire insuffisante…), la route renvoie la liste normale des offres
**sans** `matching_score`. Le front affiche alors un message au lieu d'une page vide ou d'une erreur.

### Route d'accès

```
GET /api/recommendations/{email}      (jeton obligatoire, propriétaire ou admin)
```

### Tests

`backend/tests/test_recommandations.py` remplace le modèle par un faux modèle déterministe :
on vérifie l'ordre du classement et le fait qu'une offre déjà encodée ne l'est pas une seconde fois,
sans télécharger PyTorch ni le modèle en CI.

---

## Pourquoi la similarité cosinus

La similarité cosinus mesure l'angle entre deux vecteurs, indépendamment de leur norme. Elle est standard pour comparer des embeddings de phrases car elle capture la proximité sémantique plutôt que la correspondance exacte de mots-clés.

Exemple :
- Profil : *"React, TypeScript"*
- Offre A : *"Développeur Frontend React — maîtrise de TypeScript requise"* → score élevé
- Offre B : *"Data Scientist Python — machine learning"* → score faible

---

## Contraintes respectées

| Contrainte du cahier des charges | Respect |
|---|---|
| ≤ 500 MB sur disque | ✓ ~470 MB |
| < 5 secondes par offre | ✓ < 1 s par offre en CPU, et chaque offre n'est encodée qu'une fois |
| Pas de fine-tuning au démarrage | ✓ Modèle pré-entraîné utilisé tel quel |
| Pas d'API externe non contrôlée | ✓ Inférence 100 % locale |

---

## Installation

```
# backend/requirements-ml.txt
--extra-index-url https://download.pytorch.org/whl/cpu
torch
sentence-transformers
```

La version CPU de PyTorch est utilisée explicitement pour éviter d'embarquer les bibliothèques CUDA (plusieurs Go) inutilement dans le conteneur. Ces dépendances sont séparées de `requirements.txt` : les tests et la CI n'en ont pas besoin.

---

## Limitations connues

**Cache en mémoire** — Les vecteurs sont gardés dans la mémoire du processus : ils sont recalculés après un redémarrage et ne sont pas partagés entre plusieurs instances. À plus grande échelle, il faudrait les stocker (colonne `embedding` en base ou index vectoriel type FAISS / pgvector).

**Profil textuel simple** — Le matching repose uniquement sur le champ `competences` de l'utilisateur (texte libre). Un profil peu renseigné ou générique ("Python") produira des recommandations moins précises.

**Pas de feedback utilisateur** — Le modèle ne s'améliore pas avec l'usage. Les offres consultées ou les candidatures envoyées ne sont pas réintégrées dans le scoring. Un système de recommandation collaboratif nécessiterait un historique d'interactions.

**Taille du modèle** — ~470 MB, proche de la limite de 500 MB. Le premier démarrage est plus long (téléchargement), d'où le préchargement en arrière-plan et le volume de cache.

---

## Alternative rejetée

### `all-MiniLM-L6-v2`
Plus léger (~90 MB) et plus rapide, mais entraîné surtout sur de l'anglais : moins adapté à des offres et des profils majoritairement en français.

### TF-IDF + similarité cosinus (scikit-learn)
TF-IDF aurait été encore plus léger (< 10 MB, pas de PyTorch) et plus rapide. Il a été écarté car il repose sur la correspondance exacte de mots-clés : *"Frontend Developer"* et *"Développeur Frontend"* seraient perçus comme dissimilaires, alors qu'un modèle d'embeddings multilingue les rapproche. La compréhension sémantique est le critère différenciant pour une feature de recommandation crédible.

### API OpenAI / Anthropic pour la génération de résumés
**Rejeté explicitement par le cahier des charges** — l'utilisation d'une API de modèle non contrôlée est interdite. L'inférence locale avec `sentence-transformers` répond à cette contrainte.

---

## Évaluation

En l'absence de dataset labellisé (paires offre/profil avec pertinence annotée), l'évaluation est qualitative :

- Vérification manuelle : les offres en tête de liste pour un profil "React TypeScript" correspondent-elles à des offres frontend ?
- Comparaison des scores entre offres clairement hors-sujet (Data Science) et offres pertinentes (Frontend)
- Le score est exprimé en pourcentage (0–100) pour être lisible dans l'interface
