import React, { useState, useEffect, useRef } from 'react';
import './Research.css';
import {
  Search, MapPin, DollarSign, Clock, Sparkles,
  Building2, Share2, Bookmark, ArrowRight, X, ArrowLeft
} from "lucide-react";
import { apiFetch, errorMessage, formatSalary, initials } from '../lib/api';
import type { Job, NavigateFn, Translation, UserData } from '../lib/types';

const CV_FORMATS = ".pdf,.doc,.docx,.odt";

const formatDate = (date?: string | null) =>
  date ? new Date(date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) : "récemment";

interface ResearchProps {
  onNavigate: NavigateFn;
  t: Translation;
  savedJobs: number[];
  setSavedJobs: React.Dispatch<React.SetStateAction<number[]>>;
  userData: UserData;
  homeFilters: { role: string; city: string };
  setHomeFilters: (filters: { role: string; city: string }) => void;
  selectedJobId?: number | null;
}

const Research: React.FC<ResearchProps> = ({
  onNavigate, t, savedJobs, setSavedJobs, userData, homeFilters, setHomeFilters, selectedJobId
}) => {
  const [backendJobs, setBackendJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  // Les filtres saisis sur l'accueil pré-remplissent la recherche.
  const [searchQuery, setSearchQuery] = useState(() => homeFilters?.role || "");
  const [locationQuery, setLocationQuery] = useState(() => homeFilters?.city || "");
  const [filterType, setFilterType] = useState("all");

  const [showApplyModal, setShowApplyModal] = useState(false);
  const [coverLetter, setCoverLetter] = useState("");
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [motivationFile, setMotivationFile] = useState<File | null>(null);
  const [isApplying, setIsApplying] = useState(false);
  const [isMobileDetailsOpen, setIsMobileDetailsOpen] = useState(() => selectedJobId != null);

  const jobCardRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const listContainerRef = useRef<HTMLDivElement | null>(null);

  // Connecté : offres triées par l'IA selon le profil. Sinon : toutes les offres.
  useEffect(() => {
    const url = userData?.email
      ? `/api/recommendations/${encodeURIComponent(userData.email)}`
      : '/api/dashboard/jobs';

    apiFetch(url)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setBackendJobs(data);
          setSelectedJob(data.find((j: Job) => j.id === selectedJobId) ?? data[0] ?? null);
        }
      })
      .catch(err => console.error("ERREUR API :", err));
  }, [userData?.email, selectedJobId]);

  // Offre ouverte depuis la carte de l'accueil : on la fait défiler et clignoter.
  useEffect(() => {
    if (!selectedJobId || backendJobs.length === 0) return;
    const timer = setTimeout(() => {
      const card = jobCardRefs.current[selectedJobId];
      if (card && listContainerRef.current) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('highlight-flash');
        setTimeout(() => card.classList.remove('highlight-flash'), 1500);
      }
    }, 100);
    return () => clearTimeout(timer);
  }, [selectedJobId, backendJobs]);

  // Les filtres de l'accueil ont été repris : on les vide pour la prochaine visite.
  useEffect(() => {
    if (homeFilters?.role || homeFilters?.city) setHomeFilters({ role: '', city: '' });
  }, [homeFilters, setHomeFilters]);

  const toggleSaveJob = (id: number) => {
    setSavedJobs(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const handleSelectJob = (job: Job) => {
    setSelectedJob(job);
    setIsMobileDetailsOpen(true);
  };

  // Action pour quitter le détail sur mobile et revenir à la liste
  const handleCloseMobileDetails = () => {
    setIsMobileDetailsOpen(false);
    setSelectedJob(null); // On reset l'offre active pour débloquer la vue mobile
  };

  const submitApplication = async () => {
    if (!userData?.email) {
      alert("Vous devez être connecté pour postuler !");
      onNavigate('login');
      return;
    }

    if (!cvFile || !selectedJob) {
      alert("Veuillez sélectionner votre CV avant d'envoyer.");
      return;
    }

    setIsApplying(true);
    try {
      const formData = new FormData();
      formData.append("user_email", userData.email);
      formData.append("job_id", String(selectedJob.id));
      formData.append("company", selectedJob.entreprise_nom);
      formData.append("position", selectedJob.titre);
      formData.append("message", coverLetter);
      formData.append("cv", cvFile);
      if (motivationFile) {
        formData.append("motivation_letter", motivationFile);
      }

      const response = await apiFetch("/api/applications", {
        method: "POST",
        body: formData
      });

      if (response.ok) {
        alert("Candidature envoyée avec succès ! Retrouvez-la dans votre Tableau de bord.");
        setShowApplyModal(false);
        setCoverLetter("");
        setCvFile(null);
        setMotivationFile(null);
      } else {
        alert(await errorMessage(response, "Une erreur est survenue lors de l'envoi."));
      }
    } catch (error) {
      console.error(error);
      alert("Impossible de joindre le serveur.");
    } finally {
      setIsApplying(false);
    }
  };

  const filteredJobs = backendJobs.filter(job => {
    const titre = job.titre || "";
    const entreprise = job.entreprise_nom || "";
    const typeContrat = job.contract_type || "";
    const lieu = job.location || "";
    const matchesSearch = titre.toLowerCase().includes(searchQuery.toLowerCase()) || entreprise.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesLocation = lieu.toLowerCase().includes(locationQuery.toLowerCase());
    const matchesFilter = filterType === "all" || typeContrat.includes(filterType);
    return matchesSearch && matchesLocation && matchesFilter;
  });

  return (
    <div className="research-page">
      <section className={`jobs-list-container ${isMobileDetailsOpen ? 'mobile-hidden' : ''}`}>
        <header className="list-header">
          <div className="header-top">
            <h1>{t.jobs || "Offres"}</h1>
            <span className="count">{filteredJobs.length} {t.offersCountLabel || "offres"}</span>
          </div>

          <div className="search-bar-row-wrapper">
            <div className="search-box-wrapper">
              <Search className="s-icon" size={18} />
              <input type="text" placeholder={t.searchPlaceholderJob || "Poste, entreprise..."} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
            </div>
            <div className="search-box-wrapper">
              <MapPin className="s-icon" size={18} />
              <input type="text" placeholder={t.searchPlaceholderCity || "Ville, région..."} value={locationQuery} onChange={(e) => setLocationQuery(e.target.value)} />
            </div>
          </div>

          <div className="filter-chips">
            {["all", "CDI", "Stage", "Freelance"].map(t_chip => (
              <button key={t_chip} className={`chip ${filterType === t_chip ? 'active' : ''}`} onClick={() => setFilterType(t_chip)}>
                {t_chip === "all" ? (t.filterAll || "Tous") : t_chip}
              </button>
            ))}
          </div>
        </header>

        <div ref={listContainerRef} className="scrollable-list">
          {filteredJobs.map(job => (
            <div key={job.id} ref={el => { jobCardRefs.current[job.id] = el; }} className={`job-card-mini ${selectedJob && selectedJob.id === job.id ? 'active' : ''}`} onClick={() => handleSelectJob(job)}>
              <div className="card-head">
                <div className="c-logo">{initials(job.entreprise_nom)}</div>
                <div className="c-info">
                  <h4>{job.titre}</h4>
                  <p>{job.entreprise_nom}</p>
                </div>
                <Bookmark size={18} className={`save-icon ${savedJobs.includes(job.id) ? 'saved' : ''}`} onClick={(e) => { e.stopPropagation(); toggleSaveJob(job.id); }} />
              </div>
              <div className="card-tags">
                <span><MapPin size={12} /> {job.location}</span>
                <span><DollarSign size={12} /> {formatSalary(job.salaire_min, job.salaire_max)}</span>
              </div>
              {typeof job.matching_score === 'number' && (
                <div className="ai-mini-match">
                  <Sparkles size={14} />
                  <span>{Math.round(job.matching_score)}% {t.aiMatchLabel || "de compatibilité"}</span>
                </div>
              )}
              <div className="card-foot">
                <span className="badge-type">{job.contract_type || "Non spécifié"}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className={`job-details-panel ${isMobileDetailsOpen ? 'mobile-visible' : ''}`}>
        {selectedJob ? (
          <>
            {/* BARRE DE NAVIGATION RETOUR SUR MOBILE */}
            <div className="mobile-back-nav">
              <button className="btn-back" onClick={handleCloseMobileDetails}>
                <ArrowLeft size={20} /> Retour aux offres
              </button>
            </div>

            <div className="details-header">
              <div className="d-company-row">
                <div className="d-logo">
                  <span>{initials(selectedJob.entreprise_nom)}</span>
                </div>
                <div className="d-title">
                  <h2>{selectedJob.titre}</h2>
                  <p><Building2 size={16} /> {selectedJob.entreprise_nom}</p>
                </div>
                <div className="d-actions">
                  <button className="btn-circle"><Share2 size={18} /></button>
                  <button className={`btn-circle ${savedJobs.includes(selectedJob.id) ? 'saved' : ''}`} onClick={(e) => { e.stopPropagation(); toggleSaveJob(selectedJob.id); }}>
                    <Bookmark size={18} fill={savedJobs.includes(selectedJob.id) ? "currentColor" : "none"} />
                  </button>
                </div>
              </div>
            </div>

            <div className="details-content">
              <div className="ai-summary-box">
                <div className="ai-title"><Sparkles size={16} /> {t.aiAnalysisTitle || "Recommandation IA"}</div>
                <p>Cette offre provient de {selectedJob.source || "WeLoveDevs"}.</p>

                {typeof selectedJob.matching_score === 'number' ? (
                  <div className="ai-match-container">
                    <div className="ai-match-header">
                      <span><Sparkles size={16} />{t.skillsMatch || "Correspondance des compétences"}</span>
                      <span>{Math.round(selectedJob.matching_score)}%</span>
                    </div>
                    <div className="ai-match-bar-bg">
                      <div className="ai-match-bar-fill" style={{ width: `${Math.round(selectedJob.matching_score)}%` }} />
                    </div>
                  </div>
                ) : (
                  <p>
                    {!userData?.email
                      ? "Connectez-vous et renseignez vos compétences dans votre profil pour voir votre compatibilité avec cette offre."
                      : !userData.competences
                        ? "Ajoutez vos compétences dans votre profil pour voir votre compatibilité avec cette offre."
                        : "Le score de compatibilité n'est pas disponible pour le moment."}
                  </p>
                )}
              </div>

              <div className="info-grid">
                <div className="info-item"><MapPin size={16}/> <span>{selectedJob.location}</span></div>
                <div className="info-item"><DollarSign size={16}/><span>{formatSalary(selectedJob.salaire_min, selectedJob.salaire_max)}</span></div>
                <div className="info-item"><Clock size={16}/> <span>Publiée le {formatDate(selectedJob.date)}</span></div>
              </div>

              <div className="desc-section">
                <h3>{t.descriptionLabel || "Description"}</h3>
                {selectedJob.description ? (<p style={{ whiteSpace: 'pre-line' }}>{selectedJob.description}</p>) : (<p>Aucune description disponible pour ce poste.</p>)}
              </div>

              {selectedJob.competences && (
                <div className="skills-section">
                  <h3>{t.languagesLabel || "Compétences"}</h3>
                  <div className="skills-wrap">
                    {selectedJob.competences.split(',').map(c => c.trim()).filter(Boolean).map(c => (
                      <span key={c} className="skill-tag">{c}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <footer className="details-footer">
              <button className="btn-apply" onClick={() => setShowApplyModal(true)}>
                {t.applyBtn || "Postuler maintenant"} <ArrowRight size={18} />
              </button>
            </footer>

            {showApplyModal && (
              <div className="apply-modal-backdrop" onClick={() => setShowApplyModal(false)}>
                <div className="apply-modal-card" onClick={(e) => e.stopPropagation()}>
                  <div className="modal-header">
                    <h2>Postuler à cette offre</h2>
                    <button onClick={() => setShowApplyModal(false)} className="btn-close-modal">
                      <X size={24} />
                    </button>
                  </div>

                  <div className="modal-job-summary">
                    <strong>{selectedJob.titre}</strong>
                    <span>chez {selectedJob.entreprise_nom}</span>
                  </div>

                  <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <label style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-dark)' }}>Curriculum Vitae (CV) *</label>
                        <input 
                          type="file" 
                          accept={CV_FORMATS}
                          onChange={(e) => setCvFile(e.target.files ? e.target.files[0] : null)}
                          style={{ fontSize: '0.85rem', padding: '6px', border: '1px solid var(--border-color)', borderRadius: '6px', background: 'var(--bg-light)', color: 'var(--text-dark)' }}
                        />
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <label style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-dark)' }}>Lettre de motivation</label>
                        <input 
                          type="file" 
                          accept={CV_FORMATS}
                          onChange={(e) => setMotivationFile(e.target.files ? e.target.files[0] : null)}
                          style={{ fontSize: '0.85rem', padding: '6px', border: '1px solid var(--border-color)', borderRadius: '6px', background: 'var(--bg-light)', color: 'var(--text-dark)' }}
                        />
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <label>Message d'accompagnement (optionnel)</label>
                      <textarea
                        value={coverLetter}
                        onChange={(e) => setCoverLetter(e.target.value)}
                        placeholder="Expliquez brièvement pourquoi ce poste vous intéresse..."
                        style={{ height: '80px' }}
                      />
                    </div>
                  </div>

                  <div className="modal-actions">
                    <button onClick={() => setShowApplyModal(false)} className="btn-modal-cancel">
                      Annuler
                    </button>
                    <button onClick={submitApplication} disabled={isApplying} className="btn-modal-confirm">
                      {isApplying ? "Envoi en cours..." : "Confirmer ma candidature"}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="empty-panel-prompt">
            {t.selectJobPrompt || "Sélectionnez une offre pour voir les détails"}
          </div>
        )}
      </section>
    </div>
  );
};

export default Research;