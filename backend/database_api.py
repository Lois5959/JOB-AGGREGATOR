"""Accès à la base MySQL. Toutes les requêtes sont paramétrées (aucune concaténation)."""
import logging
import os
from contextlib import contextmanager
from datetime import date, datetime

import mysql.connector
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ROLE_UTILISATEUR = 1
ROLE_ADMIN = 2
MAX_OFFRES = 1000

MOIS = {1: 'Janv.', 2: 'Févr.', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
        7: 'Juil.', 8: 'Août', 9: 'Sept.', 10: 'Oct.', 11: 'Nov.', 12: 'Déc.'}


def get_db_connection():
    """Centralise la configuration de la connexion MySQL (lue dans l'environnement)."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        connection_timeout=5,
    )


@contextmanager
def db_cursor(dictionary=False):
    """Ouvre une connexion et un curseur, puis les ferme toujours, même en cas d'erreur."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=dictionary)
    try:
        yield connection, cursor
    finally:
        cursor.close()
        connection.close()


def ping_db() -> bool:
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT 1")
            cursor.fetchall()
        return True
    except Exception as e:
        logger.warning("Base de données injoignable : %s", e)
        return False


# =====================================================================
#                              OFFRES
# =====================================================================

def inserer_database(offres_clean):
    """Insère les offres collectées. Les doublons (titre + entreprise) sont ignorés."""
    insert_query = """
        INSERT IGNORE INTO offres
            (titre, entreprise_nom, description, salaire_min, salaire_max,
             location, date, contract_type, source, competences)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    inserees = 0
    try:
        with db_cursor() as (connection, cursor):
            for offre in offres_clean:
                try:
                    cursor.execute(insert_query, (
                        str(offre.get("titre", "")),
                        str(offre.get("entreprise_nom", "")),
                        str(offre.get("description", "")),
                        int(offre.get("salaire_min") or 0),
                        int(offre.get("salaire_max") or 0),
                        str(offre.get("location", "")),
                        str(offre.get("date", "")),
                        str(offre.get("contract_type", "")),
                        str(offre.get("source", "")),
                        offre.get("competences") or None,
                    ))
                    inserees += cursor.rowcount
                except mysql.connector.Error as e:
                    logger.warning("Offre ignorée (%s) : %s", offre.get("titre"), e)
            connection.commit()
        logger.info("%s nouvelles offres insérées (%s reçues).", inserees, len(offres_clean))
    except Exception as e:
        logger.error("Erreur globale lors de l'insertion : %s", e)
    return inserees


def count_offres() -> int:
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT COUNT(*) FROM offres")
            return int(cursor.fetchone()[0])
    except Exception as e:
        logger.error("Erreur comptage offres : %s", e)
        return 0


def get_all_jobs():
    """Récupère toutes les offres (utilisé par le moteur de recommandation)."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute("SELECT * FROM offres ORDER BY date DESC, id DESC LIMIT %s", (MAX_OFFRES,))
            return cursor.fetchall()
    except Exception as e:
        logger.error("Erreur récupération jobs : %s", e)
        return []


def get_filtered_jobs(location: str = None, contract: str = None):
    """Récupère les offres filtrées pour le dashboard."""
    query = """
        SELECT id, titre, entreprise_nom, description,
               salaire_min, salaire_max, location, date,
               contract_type, competences, url, source
        FROM offres
        WHERE 1=1
    """
    params = []
    if location and location.strip() and location not in ("undefined", "null"):
        query += " AND location LIKE %s"
        params.append(f"%{location.strip()}%")
    if contract and contract.strip() and contract not in ("undefined", "null"):
        query += " AND contract_type LIKE %s"
        params.append(f"%{contract.strip()}%")
    query += " ORDER BY date DESC, id DESC LIMIT %s"
    params.append(MAX_OFFRES)

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(query, tuple(params))
            return cursor.fetchall()
    except Exception as e:
        logger.error("Erreur SQL filtre : %s", e)
        return []


def get_stats():
    """Calcule les compteurs du dashboard."""
    query = """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN contract_type LIKE '%CDI%' THEN 1 ELSE 0 END) AS cdi_count
        FROM offres
    """
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(query)
            stats = cursor.fetchone() or {}
        return {"total": int(stats.get("total") or 0), "cdi_count": int(stats.get("cdi_count") or 0)}
    except Exception as e:
        logger.error("Erreur stats : %s", e)
        return {"total": 0, "cdi_count": 0}


# =====================================================================
#                            UTILISATEURS
# =====================================================================

def creer_utilisateur(email, hashed_password, competences, nom="Utilisateur", role_id=ROLE_UTILISATEUR):
    nom_text = nom.strip() if (nom and nom.strip()) else "Utilisateur"
    try:
        with db_cursor() as (connection, cursor):
            cursor.execute(
                "INSERT INTO utilisateurs (email, password, competences, role_id, nom) VALUES (%s, %s, %s, %s, %s)",
                (email, hashed_password, competences or "", role_id, nom_text),
            )
            connection.commit()
        return True
    except Exception as e:
        logger.error("Erreur lors de la création du compte : %s", e)
        return False


def get_user_by_email(email):
    """Récupère un utilisateur par son email (authentification, profil)."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute("SELECT * FROM utilisateurs WHERE email = %s", (email,))
            return cursor.fetchone()
    except Exception as e:
        logger.error("Erreur recherche utilisateur : %s", e)
        return None


def update_user_profile(email, nom=None, competences=None):
    """Met à jour le nom et/ou les compétences. Un champ absent (None) reste inchangé."""
    try:
        with db_cursor() as (connection, cursor):
            cursor.execute(
                "UPDATE utilisateurs SET nom = COALESCE(%s, nom), competences = COALESCE(%s, competences) "
                "WHERE email = %s",
                (nom, competences, email),
            )
            connection.commit()
        return True
    except Exception as e:
        logger.error("Erreur lors de la mise à jour du profil : %s", e)
        return False


def set_user_role(email, role_id):
    try:
        with db_cursor() as (connection, cursor):
            cursor.execute("UPDATE utilisateurs SET role_id = %s WHERE email = %s", (role_id, email))
            connection.commit()
        return True
    except Exception as e:
        logger.error("Erreur lors du changement de rôle : %s", e)
        return False


# =====================================================================
#                          PANEL ADMINISTRATION
# =====================================================================

def get_all_users():
    """Récupère tous les utilisateurs avec le nom de leur rôle (sans les mots de passe)."""
    query = """
        SELECT u.id, u.nom AS name, u.email, r.name AS role
        FROM utilisateurs u
        JOIN roles r ON u.role_id = r.id
        ORDER BY u.id
    """
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(query)
            return cursor.fetchall()
    except Exception as e:
        logger.error("Erreur récupération des utilisateurs : %s", e)
        return []


def get_admin_jobs():
    """Récupère les offres formatées pour le tableau d'administration."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                "SELECT id, titre AS title, entreprise_nom AS company, location AS city "
                "FROM offres ORDER BY date DESC, id DESC LIMIT %s",
                (MAX_OFFRES,),
            )
            return cursor.fetchall()
    except Exception as e:
        logger.error("Erreur récupération des offres admin : %s", e)
        return []


def delete_user(user_id: int):
    """Supprime un utilisateur. True : supprimé, False : introuvable, None : erreur."""
    try:
        with db_cursor() as (connection, cursor):
            cursor.execute("DELETE FROM utilisateurs WHERE id = %s", (user_id,))
            connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error("Erreur lors de la suppression de l'utilisateur %s : %s", user_id, e)
        return None


def delete_job(job_id: int):
    """Supprime une offre. True : supprimée, False : introuvable, None : erreur."""
    try:
        with db_cursor() as (connection, cursor):
            cursor.execute("DELETE FROM offres WHERE id = %s", (job_id,))
            connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error("Erreur lors de la suppression de l'offre %s : %s", job_id, e)
        return None


# =====================================================================
#                             CANDIDATURES
# =====================================================================

def add_application(user_email, job_id, company, position):
    """Enregistre une nouvelle candidature."""
    try:
        with db_cursor() as (connection, cursor):
            cursor.execute(
                "INSERT INTO candidatures (user_email, job_id, company, position, date, status, color) "
                "VALUES (%s, %s, %s, %s, %s, 'En attente', 'orange')",
                (user_email, job_id, company, position, date.today().isoformat()),
            )
            connection.commit()
        return True
    except Exception as e:
        logger.error("Erreur ajout candidature : %s", e)
        return False


def get_applications(user_email):
    """Récupère les candidatures d'un utilisateur, de la plus récente à la plus ancienne."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute("SELECT * FROM candidatures WHERE user_email = %s ORDER BY id DESC", (user_email,))
            return cursor.fetchall()
    except Exception as e:
        logger.error("Erreur récupération candidatures : %s", e)
        return []


def _as_date(value):
    """MySQL renvoie un objet date ; on accepte aussi une chaîne 'AAAA-MM-JJ'."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    return None


def build_monthly_stats(applications, today=None):
    """Regroupe les candidatures des 6 derniers mois (mois courant inclus)."""
    today = today or date.today()
    mois_cles = []
    annee, mois = today.year, today.month
    for _ in range(6):
        mois_cles.append((annee, mois))
        annee, mois = (annee - 1, 12) if mois == 1 else (annee, mois - 1)
    mois_cles.reverse()

    stats = {cle: {"mois": MOIS[cle[1]], "envoyees": 0, "acceptees": 0, "refusees": 0} for cle in mois_cles}
    for app in applications:
        try:
            d = _as_date(app.get("date"))
        except ValueError:
            continue
        if d is None or (d.year, d.month) not in stats:
            continue
        ligne = stats[(d.year, d.month)]
        ligne["envoyees"] += 1
        if app.get("status") == "Accepté":
            ligne["acceptees"] += 1
        elif app.get("status") == "Refusé":
            ligne["refusees"] += 1
    return list(stats.values())


def get_monthly_stats_from_db(user_email):
    """Statistiques des 6 derniers mois pour le graphique du dashboard."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute("SELECT date, status FROM candidatures WHERE user_email = %s", (user_email,))
            apps = cursor.fetchall()
    except Exception as e:
        logger.error("Erreur stats mensuelles : %s", e)
        apps = []
    return build_monthly_stats(apps)
