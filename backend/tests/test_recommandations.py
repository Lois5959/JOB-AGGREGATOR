"""Logique de recommandation avec un faux modèle (sans télécharger PyTorch ni le modèle)."""
import sys
import types

import pytest

import feature_ia


class FakeTensor(list):
    def item(self):
        return self[0]


class FakeModel:
    """Vecteur = présence des mots-clés ; la similarité est un simple produit scalaire."""
    MOTS = ["docker", "python", "linux"]

    def __init__(self):
        self.textes_encodes = []

    def _vecteur(self, texte):
        texte = texte.lower()
        return [1.0 if mot in texte else 0.0 for mot in self.MOTS]

    def encode(self, textes, **_):
        if isinstance(textes, str):
            return self._vecteur(textes)
        self.textes_encodes.extend(textes)
        return [self._vecteur(t) for t in textes]


@pytest.fixture
def faux_modele(monkeypatch):
    def cos_sim(a, matrice):
        return [[FakeTensor([sum(x * y for x, y in zip(a, v)) / 2]) for v in matrice]]

    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(stack=list))
    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(util=types.SimpleNamespace(
        cos_sim=cos_sim)))
    modele = FakeModel()
    monkeypatch.setattr(feature_ia, "_model", modele)
    monkeypatch.setattr(feature_ia, "_embedding_cache", {})
    return modele


def test_offres_triees_par_pertinence(faux_modele, fake_db):
    # Bob a la compétence « Python » : l'offre Python doit passer devant l'offre Docker.
    resultats = feature_ia.get_matching_jobs("bob@example.com")
    assert [j["titre"] for j in resultats] == ["Développeur Python", "Ingénieur DevOps"]
    assert resultats[0]["matching_score"] > resultats[1]["matching_score"]


def test_les_offres_deja_encodees_ne_sont_pas_recalculees(faux_modele, fake_db):
    feature_ia.get_matching_jobs("bob@example.com")
    assert len(faux_modele.textes_encodes) == 2

    fake_db.jobs.append({"id": 3, "titre": "Admin Linux", "entreprise_nom": "Hexapole", "location": "Paris",
                         "contract_type": "CDI", "description": "Linux", "competences": "Linux"})
    feature_ia.get_matching_jobs("bob@example.com")
    assert len(faux_modele.textes_encodes) == 3  # seule la nouvelle offre a été encodée


def test_sans_offres(faux_modele, fake_db):
    fake_db.jobs.clear()
    assert feature_ia.get_matching_jobs("bob@example.com") == []
