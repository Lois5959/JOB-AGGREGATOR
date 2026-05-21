# Documentation Sécurité — Job Aggregator
## Vue d'ensemble
Ce document décrit les choix de sécurité appliqués au projet Job Aggregator, conformément aux exigences du cahier des charges Epitech. Chaque mesure est présentée avec son Pourquoi, son Comment et ses Trade-offs.

1. Gestion des secrets
## Pourquoi : 
Les credentials en dur dans le code source sont une vulnérabilité critique (OWASP A02). Un secret exposé dans un dépôt Git peut être exploité immédiatement.

## Comment : 
Les secrets sont injectés via des variables d'environnement au démarrage des conteneurs. Le docker-compose.yml utilise la syntaxe ${VAR:-valeur_defaut} pour définir les valeurs de fallback en développement uniquement.

yaml# docker-compose.yml
environment:
  MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-testroot}
  MYSQL_DATABASE: ${MYSQL_DATABASE:-testdb}
  MYSQL_USER: ${MYSQL_USER:-testuser}
  MYSQL_PASSWORD: ${MYSQL_PASSWORD:-testpassword}
  WELOVEDEVS_API_KEY: ${WELOVEDEVS_API_KEY:-dummy_key}

## Trade-off : 
Les valeurs par défaut facilitent le démarrage local mais ne doivent jamais être utilisées en production. La documentation de déploiement doit l'expliciter clairement.

# 2. Authentification et sécurité des tokens (JWT)
## Pourquoi : 
Les routes sensibles doivent être protégées contre les accès non autorisés. L'authentification par token stateless convient bien à une API REST.

## Comment : 
L'authentification est implémentée dans auth.py avec trois composantes :

Hachage des mots de passe avec bcrypt via passlib, avec truncate_error=False pour éviter les silences sur les mots de passe trop longs.
Génération de tokens JWT signés avec HMAC-SHA256 (HS256), incluant une expiration de 30 minutes.
Vérification du mot de passe soumis contre le haché stocké en base.

python# auth.py
pwd_contenue = CryptContext(schemes=["bcrypt"], deprecated="auto", truncate_error=False)
SECRET_KEY = "***SECRET-RETIRE***"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

## Trade-off : 
La SECRET_KEY est actuellement définie en dur dans le fichier source — elle doit être déplacée vers une variable d'environnement avant tout déploiement en production. Les tokens JWT ne peuvent pas être révoqués avant expiration sans mécanisme de blacklist supplémentaire.

# 3. Mitigation des attaques par force brute (Fail2ban)
## Pourquoi : 
Sans protection, un attaquant peut tenter un nombre illimité de combinaisons login/mot de passe sur le endpoint /login.

## Comment : 
Fail2ban est déployé comme service Docker et surveille les logs applicatifs. La configuration est composée de trois fichiers :
jail.local — définit la jail pour l'application :

ini[jobaggregator]
enabled  = true
port     = 8000
filter   = jobaggregator
logpath  = /var/log/jobaggregator/app.log
maxretry = 5
bantime  = 600

→ Après 5 tentatives échouées, l'IP est bannie pendant 10 minutes.
jobaggregator.conf — définit le pattern de détection :

ini[Definition]
failregex = ^<HOST> -.*"POST /login.*" 401

ignoreregex =
→ Chaque réponse 401 sur POST /login incrémente le compteur de l'IP source.
docker-compose.yml — monte les logs et la config dans le conteneur Fail2ban :
yamlfail2ban:
  image: crazymax/fail2ban:latest
  network_mode: "host"
  cap_add:
    - NET_ADMIN
    - NET_RAW
  volumes:
    - ./backend/logs:/var/log/jobaggregator
    - ./etc/fail2ban:/etc/fail2ban

## Trade-off : 
network_mode: host est nécessaire pour que Fail2ban puisse manipuler iptables, mais supprime l'isolation réseau du conteneur. Les IPs légitimes derrière un proxy partagé (NAT d'entreprise) pourraient être bloquées collectivement. Un findtime plus long ou un maxretry plus élevé pourrait être envisagé selon le contexte.

# 4. Reverse proxy et isolation réseau (Nginx)
## Pourquoi : 
Exposer le backend directement sur Internet augmente la surface d'attaque. Un reverse proxy permet de centraliser le routage, masquer la topologie interne et faciliter l'ajout de TLS.

## Comment : 
Nginx sert le frontend statique et proxifie les appels /api/ vers le backend, en transmettant l'IP réelle du client pour que Fail2ban puisse l'identifier.

nginx# nginx.conf
location /api/ {
    proxy_pass http://backend:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
Le réseau Docker est segmenté en deux sous-réseaux :

frontend_network : frontend ↔ backend
backend_network : backend ↔ db ↔ phpmyadmin

PhpMyAdmin est exclusivement accessible depuis 127.0.0.1:8081, jamais exposé sur l'interface publique.
yamlphpmyadmin:
  ports:
    - "127.0.0.1:8081:80"  # Accès local uniquement

## Trade-off : 
La configuration actuelle tourne en HTTP. En production, il faudrait ajouter TLS (Let's Encrypt / Certbot) et forcer la redirection HTTP → HTTPS.

# 5. Contrôle d'accès par rôles (RBAC)
## Pourquoi : 
Tous les utilisateurs ne doivent pas avoir accès aux fonctionnalités d'administration (modération des offres, gestion des utilisateurs).

## Comment : 
Le modèle de données inclut un champ role sur la table users (valeurs : user, admin). Les routes sensibles vérifient le rôle côté serveur via un middleware d'autorisation appliqué après la validation du token JWT. Le contrôle est strictement server-side ; le frontend n'affiche que les éléments autorisés mais cette restriction n'est pas considérée comme une mesure de sécurité en elle-même.

## Trade-off : 
Un système RBAC plus granulaire (permissions par ressource) aurait été plus flexible, mais ajoute de la complexité de gestion. Le modèle à deux rôles couvre les besoins du projet.

# 6. Protection contre les injections
## Pourquoi : 
Les injections SQL (OWASP A03) sont l'une des vulnérabilités les plus exploitées sur les applications web.

## Comment :
L'ORM utilisé (SQLAlchemy / équivalent) paramètre automatiquement toutes les requêtes, éliminant le risque d'injection par concaténation de chaînes. Les inputs utilisateur sont également validés via un schéma Pydantic avant tout traitement ou persistance.

## Trade-off : 
La validation applicative ne remplace pas les contraintes d'intégrité au niveau de la base de données (clés étrangères, contraintes NOT NULL), qui sont également définies dans le schéma SQL.

# Résumé des menaces couvertes
## Menace                                   Contrôle appliqué 
Secrets exposés                          Variables d'environnement + .gitignore
Mots de passe en clair                   Hachage bcrypt
Tokens falsifiés                         JWT signé HS256 + expiration 30 min
Force brute sur /login                   Fail2ban (5 tentatives → ban 10 min)
Accès non autorisé aux routes            JWT + vérification de rôle server-side
Exposition de la base de données         Réseau Docker isolé + phpMyAdmin local uniquement
Injection SQL                            ORM paramétré + validation Pydantic
Surface d'attaque du backend             Reverse proxy Nginx