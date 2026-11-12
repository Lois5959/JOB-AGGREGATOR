"""Recommandation d'offres par similarité sémantique entre le profil et les offres.

Le modèle (MiniLM multilingue, ~470 Mo) est chargé à la première utilisation, pas à
l'import : l'API démarre vite et les tests n'ont pas besoin de PyTorch.
Les vecteurs des offres sont mis en cache pour ne pas tout réencoder à chaque requête.
"""
import hashlib
import logging
import os
import threading

from database_api import get_all_jobs, get_user_by_email

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

_model = None
_model_lock = threading.Lock()
_cache_lock = threading.Lock()
_embedding_cache = {}  # id de l'offre -> (empreinte du texte, vecteur)


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                logger.info("Chargement du modèle %s...", MODEL_NAME)
                _model = SentenceTransformer(MODEL_NAME)
                logger.info("Modèle chargé.")
    return _model


def warmup():
    """Charge le modèle en arrière-plan au démarrage pour que la 1re requête soit rapide."""
    try:
        get_model()
    except Exception as e:
        logger.warning("Préchargement du modèle impossible : %s", e)


def build_job_text(job: dict) -> str:
    """Texte représentatif de l'offre ; titre et compétences sont répétés pour peser plus."""
    titre = job.get("titre") or ""
    entreprise = job.get("entreprise_nom") or ""
    competences = job.get("competences") or ""
    description = job.get("description") or ""
    return f"{titre} {titre} {competences} {competences} {entreprise} {description[:300]}"


def build_user_text(user_data: dict) -> str:
    """Texte représentatif du profil ; les compétences sont répétées pour peser plus."""
    competences = user_data.get("competences") or ""
    return f"{competences} {competences} {competences}"


def normalize_score(raw_score: float) -> float:
    """Ramène le cosinus (souvent entre 0,15 et 0,75) à un pourcentage lisible."""
    min_sim, max_sim = 0.15, 0.75
    clamped = max(min_sim, min(max_sim, raw_score))
    return round((clamped - min_sim) / (max_sim - min_sim) * 100, 1)


def _job_embeddings(model, jobs):
    """Encode uniquement les offres nouvelles ou modifiées depuis le dernier appel."""
    import torch

    textes = [build_job_text(job) for job in jobs]
    empreintes = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in textes]

    with _cache_lock:
        a_encoder = [i for i, job in enumerate(jobs)
                     if _embedding_cache.get(job["id"], (None,))[0] != empreintes[i]]
    if a_encoder:
        vecteurs = model.encode([textes[i] for i in a_encoder], convert_to_tensor=True,
                                batch_size=64, show_progress_bar=False)
        with _cache_lock:
            for idx, vecteur in zip(a_encoder, vecteurs):
                _embedding_cache[jobs[idx]["id"]] = (empreintes[idx], vecteur)

    with _cache_lock:
        return torch.stack([_embedding_cache[job["id"]][1] for job in jobs])


def get_matching_jobs(user_email: str):
    """Renvoie les offres triées par pertinence pour l'utilisateur.

    Sans compétences renseignées, ou si le modèle est indisponible, on renvoie les
    offres sans score plutôt qu'une page vide.
    """
    jobs = get_all_jobs()
    if not jobs:
        return []

    user_data = get_user_by_email(user_email)
    if not user_data or not (user_data.get("competences") or "").strip():
        return jobs

    try:
        from sentence_transformers import util

        model = get_model()
        user_embedding = model.encode(build_user_text(user_data), convert_to_tensor=True)
        similarities = util.cos_sim(user_embedding, _job_embeddings(model, jobs))[0]
    except Exception as e:
        logger.error("Recommandation indisponible, offres renvoyées sans score : %s", e)
        return jobs

    for i, job in enumerate(jobs):
        job["matching_score"] = normalize_score(float(similarities[i].item()))
    return sorted(jobs, key=lambda j: j["matching_score"], reverse=True)
