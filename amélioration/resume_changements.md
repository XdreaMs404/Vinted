# Résumé des Implémentations et Optimisations

Ce document récapitule l'ensemble des modifications architecturales, techniques et fonctionnelles apportées récemment au projet **Vinted Radar**.

## 1. Migration vers l'API JSON Vinted
* **Objectif :** Remplacer le scraping HTML classique (fragile et coûteux en bande passante) par des appels directs à l'API interne de Vinted.
* **Changements :**
  * Création d'un nouveau parser (`vinted_radar/parsers/api_catalog_page.py`) traitant directement les réponses JSON.
  * Adaptation du service de découverte (`discovery.py`) pour interroger les endpoints `/api/v2/...`.
  * **Avantage majeur :** Augmentation du nombre d'articles récupérés par requête (passage de 24 à 96 articles par page).
  * Implémentation d'un système de *fallback* (repli) vers le parsing HTML classique en cas d'échec de l'API.

## 2. Refonte Asynchrone (Concurrence)
* **Objectif :** Accélérer massivement la vitesse de scan des catalogues en parallélisant les requêtes HTTP.
* **Changements :**
  * Migration du module `vinted_radar/http.py` pour utiliser `curl_cffi.requests.AsyncSession` (support de TLS-impersonation en asynchrone).
  * Refonte de la méthode `.run()` dans la phase de découverte pour utiliser `asyncio.gather`.
  * Mise en place d'un contrôle de concurrence strict via `asyncio.Semaphore` pour limiter le nombre de requêtes simultanées en vol et éviter de saturer la connexion.

## 3. Optimisation pour VPS (Stealth Mode)
* **Objectif :** Rendre le scraper plus furtif et économe en ressources pour tourner 24h/24 sur un serveur VPS.
* **Changements :**
  * Implémentation d'un système de *rate-limiting* (limitation de taux) asynchrone robuste avec `asyncio.sleep` pour imiter un comportement de navigation humain.
  * Ajout d'une option de ligne de commande `--concurrency` pour ajuster finement le niveau de parallélisme selon la puissance du VPS.
  * Ajustement des paramètres par défaut : augmentation des délais entre les requêtes et réduction de la concurrence de base pour privilégier la sécurité (anti-ban) sur la vitesse pure lors d'une exécution continue.

## 4. Documentation et Déploiement
* **Objectif :** Faciliter le déploiement sur une machine distante.
* **Changements :**
  * Rédaction d'un guide complet d'installation spécifique aux VPS Linux (Ubuntu 24.04).
  * Ajout des instructions pour la gestion des paquets PPA (ex: `deadsnakes` pour Python 3.13) afin de pallier l'absence de versions récentes de Python dans les dépôts par défaut d'Ubuntu.

## 5. Résolution de Bugs en cours (HTTP Client)
* **Status :** Investigation sur la gestion des cookies asynchrones.
* **Contexte :** Une erreur a été identifiée (`AttributeError: 'str' object has no attribute 'name'`) lors de la phase de *warm-up* asynchrone. L'itération sur les cookies de la session asynchrone de `curl_cffi` renvoie des chaînes de caractères brutes (Morsels) au lieu d'objets `Cookie`. Un correctif est en cours d'élaboration sur le fichier `vinted_radar/http.py`.
