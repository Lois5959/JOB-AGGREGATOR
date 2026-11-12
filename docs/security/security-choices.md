# Choix de sécurité — JobyFind

Chaque mesure est présentée avec son **pourquoi**, son **comment** (fichier concerné) et ses **limites**.
Tout ce qui est décrit ici est vérifié par des tests (`backend/tests/`) ou par la CI.

---

## 1. Secrets

**Pourquoi.** Un secret écrit dans le code finit dans l'historique Git et peut être réutilisé
par n'importe qui (OWASP A02).

**Comment.**
- Tous les secrets viennent de variables d'environnement, lues depuis un fichier `.env`
  qui n'est **jamais** versionné (`.gitignore`). Le dépôt fournit seulement `.env.example`.
- `JWT_SECRET` : clé de signature des jetons. Si elle est absente, l'API génère une clé
  aléatoire au démarrage (sans jamais l'afficher) et prévient dans les journaux : les sessions
  sont alors perdues à chaque redémarrage — pratique en démo, à éviter en production.
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` : créent le premier compte administrateur au démarrage.
  Aucun compte admin n'existe « par défaut » dans le code ou le SQL.

**Limites.** Les valeurs par défaut de `docker-compose.yml` (`change-me-…`) servent uniquement au
démarrage local et doivent être remplacées dans `.env` pour tout déploiement.

---

## 2. Mots de passe et jetons JWT

**Pourquoi.** Les routes sensibles doivent savoir *qui* appelle, sans stocker de session côté serveur.

**Comment** (`backend/auth.py`, `backend/routes.py`).
- Mots de passe hachés avec **bcrypt** (`passlib`) ; longueur imposée entre 8 et 128 caractères.
- Jetons **JWT HS256** signés avec `JWT_SECRET`, expiration configurable
  (`JWT_EXPIRE_MINUTES`, 30 min par défaut).
- Côté front, le jeton est envoyé dans l'en-tête `Authorization: Bearer …` par un client unique
  (`front-end/src/lib/api.ts`). Un `401` efface le jeton et renvoie vers l'écran de connexion.

**Limites.** Un jeton ne peut pas être révoqué avant son expiration (pas de liste noire).
Il est stocké dans `localStorage`, donc lisible par un script injecté : d'où l'importance
de la protection XSS (section 6) et de la CSP (section 7).

---

## 3. Contrôle d'accès

**Pourquoi.** Être connecté ne doit pas suffire pour lire les données d'un autre utilisateur
ou pour administrer la plateforme (OWASP A01).

**Comment** (`backend/auth.py`).

| Dépendance FastAPI | Règle |
|---|---|
| `get_current_user` | Jeton valide obligatoire, sinon `401`. |
| `ensure_self_or_admin` | L'email visé doit être celui du jeton (ou l'appelant est admin), sinon `403`. |
| `require_admin` | Le rôle est **relu en base** à chaque appel, sinon `403`. |

Conséquences concrètes, toutes testées :
- un utilisateur ne peut ni lire ni modifier le profil, les candidatures ou les recommandations d'un autre ;
- un jeton modifié à la main est rejeté (signature invalide) ; et même un jeton **correctement
  signé** qui annonce `role_id: 2` ne suffit pas, car le rôle est relu en base ;
- l'inscription crée toujours un compte « utilisateur » : impossible de s'inscrire admin ;
- un admin ne peut pas supprimer son propre compte (`400`).

Le front masque le menu Admin aux non-admins, mais ce n'est pas une mesure de sécurité :
tout est vérifié côté serveur.

---

## 4. Force brute sur la connexion — deux niveaux

**Pourquoi.** Sans limite, un attaquant peut essayer des milliers de mots de passe.

**Niveau 1 — dans l'API (toujours actif).** `LoginRateLimiter` (`backend/auth.py`) compte les
échecs par IP : après **5 échecs en 10 minutes**, `/api/login` répond `429` avec un en-tête
`Retry-After`. Une connexion réussie remet le compteur à zéro. Réglable avec
`LOGIN_MAX_ATTEMPTS` et `LOGIN_WINDOW_SECONDS`.

**Niveau 2 — fail2ban (profil `security`, Linux).** Chaque échec écrit une ligne dans
`/var/log/jobaggregator/app.log` (volume Docker partagé) :

```
203.0.113.7 - "POST /api/login HTTP/1.1" 401
```

fail2ban lit ce fichier et bannit l'IP au niveau du pare-feu (chaîne `DOCKER-USER`) :

```ini
# fail2ban/filter.d/jobaggregator.conf
failregex = ^<HOST> - "POST /api/login HTTP/1\.1" 401$

# fail2ban/jail.d/jobaggregator.local
maxretry = 5
findtime = 600
bantime  = 600
port     = 80,443,8000
chain    = DOCKER-USER
```

**IP réelle du client.** Nginx **remplace** l'en-tête `X-Forwarded-For` par l'adresse qu'il voit
(`$remote_addr`) au lieu de le compléter : un client ne peut donc pas envoyer une fausse IP
pour contourner la limite. Uvicorn est lancé avec `--proxy-headers` pour lire cette IP.

**Limites.** Le compteur du niveau 1 est en mémoire : il repart à zéro au redémarrage et n'est
pas partagé entre plusieurs instances (il faudrait Redis). fail2ban a besoin de
`network_mode: host` et de `NET_ADMIN` pour modifier iptables, et ne fonctionne pas sous
Docker Desktop (macOS / Windows). Des utilisateurs derrière la même IP (NAT d'entreprise)
partagent le même compteur.

---

## 5. Injections SQL et validation des entrées

**Pourquoi.** L'injection SQL reste l'une des failles les plus exploitées (OWASP A03).

**Comment.**
- Pas d'ORM : toutes les requêtes de `backend/database_api.py` sont **paramétrées**
  (`cursor.execute(query, params)`), aucune valeur n'est concaténée dans le SQL.
- Les corps de requête sont validés par **Pydantic** (email valide, longueurs maximales).
- Les fichiers de candidature sont limités aux extensions `.pdf`, `.doc`, `.docx`, `.odt`
  et à 5 Mo (`400` / `413`) ; Nginx refuse les requêtes de plus de 12 Mo.

**Limites.** Le contrôle des fichiers porte sur l'extension et la taille, pas sur le contenu.
Les fichiers ne sont pas conservés sur le serveur, ce qui limite le risque.

---

## 6. XSS (injection de script dans les pages)

**Pourquoi.** Les descriptions d'offres viennent d'une API externe : elles peuvent contenir du HTML.

**Comment.**
- À la collecte, `texte_brut()` (`backend/collector.py`) retire les balises `<script>` / `<style>`
  et tout le HTML, puis décode les entités : on stocke du **texte**.
- Côté front, la description est affichée comme du texte (pas de `dangerouslySetInnerHTML`).
- Deux protections valent mieux qu'une : même si une description HTML arrivait en base,
  React l'afficherait sans l'exécuter.

---

## 7. Nginx, réseau et conteneurs

**Pourquoi.** Moins il y a de choses exposées, moins il y a de choses à attaquer.

**Comment.**
- **Un seul port public** : Nginx sur `8082`. L'API (`8000`) et phpMyAdmin (`8081`) ne sont
  publiés que sur `127.0.0.1`.
- `backend_network` est déclaré `internal: true` : la base de données n'a aucun accès à Internet
  et n'est joignable que par l'API (et phpMyAdmin si le profil `tools` est lancé).
- En-têtes ajoutés par Nginx (`front-end/nginx.conf`) : `Content-Security-Policy` (scripts
  uniquement depuis le site, liste fermée de domaines pour la carte et le géocodage),
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`,
  `Permissions-Policy`, et `server_tokens off` (version de Nginx masquée).
- L'image de l'API tourne avec un **utilisateur non-root** (`appuser`, uid 10001).
- Chaque service a un **healthcheck** ; l'API ne démarre que quand MySQL est prêt, Nginx
  que quand l'API est prête.
- CORS : seules les origines listées dans `CORS_ORIGINS` sont acceptées, sans cookies.

**Limites.** La stack tourne en HTTP. En production, il faut ajouter TLS (Let's Encrypt)
devant Nginx et rediriger HTTP vers HTTPS. La CSP autorise `'unsafe-inline'` pour les styles,
car React et Leaflet utilisent des attributs `style`.

---

## Résumé

| Menace | Contrôle | Où |
|---|---|---|
| Secrets dans le dépôt | Variables d'environnement, `.env` ignoré par Git | `.env.example`, `.gitignore` |
| Mots de passe volés en base | bcrypt | `auth.py` |
| Jeton falsifié ou expiré | JWT HS256 signé + expiration | `auth.py` |
| Accès aux données d'un autre | `ensure_self_or_admin` | `auth.py`, `api.py` |
| Élévation de privilèges | Rôle relu en base, inscription toujours « utilisateur » | `auth.py`, `routes.py` |
| Force brute | Limite par IP (429) + fail2ban | `auth.py`, `fail2ban/` |
| Usurpation d'IP via en-tête | Nginx écrase `X-Forwarded-For` | `nginx.conf` |
| Injection SQL | Requêtes paramétrées + Pydantic | `database_api.py` |
| XSS | HTML retiré à la collecte + affichage en texte + CSP | `collector.py`, `Research.tsx`, `nginx.conf` |
| Base exposée | Réseau Docker interne, ports liés à `127.0.0.1` | `docker-compose.yml` |
| Conteneur compromis | Utilisateur non-root dans l'image de l'API | `backend/Dockerfile` |
