# ADR-005 — Choix AI

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | Mai 2026 |
| **Décideurs** | Équipe Job Aggregator |

---

## Contexte

Le cahier des charges impose une feature AI légère : modèle ≤ 500 MB sur disque, résultat en moins de 5 secondes par offre, pas de fine-tuning au démarrage, et aucune dépendance à une API externe non contrôlée.

---

## Problème adressé

Un étudiant renseigne ses compétences (ex : "React, TypeScript, Node.js") dans son profil. La plateforme doit lui retourner les offres les plus pertinentes sans qu'il ait à relire chaque description manuellement.

---

## Décision : similarité sémantique avec `all-MiniLM-L6-v2`

### Modèle retenu

**`sentence-transformers/all-MiniLM-L6-v2`** via la bibliothèque `sentence-transformers`.

| Critère | Valeur |
|---|---|
| Taille sur disque | ~90 MB |
| Temps d'inférence | < 1 seconde par offre (CPU) |
| Fine-tuning requis | Non |
| API externe | Non (exécution locale) |
| Type | Modèle de langage encodeur (embeddings) |

Le modèle transforme un texte en vecteur numérique de 384 dimensions. Deux textes sémantiquement proches produisent des vecteurs proches dans cet espace.

---

## Implémentation

```python
# feature_ia.py
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def get_matching_jobs(user_email):
    # 1. Récupération des compétences utilisateur
    user_skills = user_data["competences"]  # ex: "React, TypeScript, Node.js"
    user_embedding = model.encode(user_skills, convert_to_tensor=True)

    # 2. Pour chaque offre en base
    for job in all_jobs:
        job_text = f"{job['titre']} {job['description']}"
        job_embedding = model.encode(job_text, convert_to_tensor=True)

        # 3. Similarité cosinus entre profil et offre
        similarity = util.cos_sim(user_embedding, job_embedding)
        score = round(float(similarity.item()) * 100, 2)
        job["matching_score"] = score

    # 4. Tri par score décroissant
    return sorted(results, key=lambda x: x["matching_score"], reverse=True)
```

### Route d'accès

```
GET /recommendations/{email}
```

Retourne la liste complète des offres triées par score de matching décroissant pour l'utilisateur identifié par son email.

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
| ≤ 500 MB sur disque | ✓ ~90 MB |
| < 5 secondes par offre | ✓ < 1s par offre en CPU |
| Pas de fine-tuning au démarrage | ✓ Modèle pré-entraîné utilisé tel quel |
| Pas d'API externe non contrôlée | ✓ Inférence 100% locale |

---

## Installation

```
# requirements.txt
sentence-transformers
torch --index-url https://download.pytorch.org/whl/cpu
```

La version CPU-only de PyTorch est utilisée explicitement pour éviter d'embarquer les drivers CUDA (~2 GB) inutilement dans le conteneur.

---

## Limitations connues

**Encodage à la volée** — Chaque appel à `/recommendations/{email}` encode toutes les offres en base. Sur un petit volume (< 500 offres), c'est acceptable. À grande échelle, les embeddings des offres devraient être précalculés et stockés (colonne `embedding BLOB` en base ou index vectoriel type FAISS).

**Profil textuel simple** — Le matching repose uniquement sur le champ `competences` de l'utilisateur (texte libre). Un profil peu renseigné ou générique ("Python") produira des recommandations moins précises.

**Pas de feedback utilisateur** — Le modèle ne s'améliore pas avec l'usage. Les offres consultées ou les candidatures envoyées ne sont pas réintégrées dans le scoring. Un système de recommandation collaboratif nécessiterait un historique d'interactions.

**Langue** — `all-MiniLM-L6-v2` est entraîné majoritairement sur de l'anglais. Les descriptions en français sont gérées mais avec une précision légèrement inférieure aux textes anglais.

---

## Alternative rejetée

### TF-IDF + similarité cosinus (scikit-learn)
TF-IDF aurait été encore plus léger (< 10 MB, pas de PyTorch) et plus rapide. Il a été écarté car il repose sur la correspondance exacte de mots-clés : *"Frontend Developer"* et *"Développeur Frontend"* seraient perçus comme dissimilaires, alors que `all-MiniLM-L6-v2` les rapproche sémantiquement. La compréhension sémantique est le critère différenciant pour une feature de recommandation crédible.

### API OpenAI / Anthropic pour la génération de résumés
**Rejeté explicitement par le cahier des charges** — l'utilisation d'une API de modèle non contrôlée est interdite. L'inférence locale avec `sentence-transformers` répond à cette contrainte.

---

## Évaluation

En l'absence de dataset labellisé (paires offre/profil avec pertinence annotée), l'évaluation est qualitative :

- Vérification manuelle : les offres en tête de liste pour un profil "React TypeScript" correspondent-elles à des offres frontend ?
- Comparaison des scores entre offres clairement hors-sujet (Data Science) et offres pertinentes (Frontend)
- Le score est exprimé en pourcentage (0–100) pour être lisible dans l'interface
