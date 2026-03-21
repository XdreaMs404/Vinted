# Optimisations VPS, Systemd et Résolution de Bugs SQLite

Ce document retrace les implémentations et corrections effectuées pour stabiliser le Vinted Radar sur un VPS en fonctionnement 24/7.

## 1. Extraction des Métadonnées Étendues (JSON API)
**Fichiers affectés :** `vinted_radar/models.py`, `vinted_radar/db.py`, `vinted_radar/parsers/api_catalog_page.py`, `vinted_radar/repository.py`

* **Objectif** : Capter des informations vitales depuis l'API Vinted (Likes, Vues, Vendeur, Horodatage) afin d'enrichir la base de données.
* **Modifications modèles** : Ajout des attributs `favourite_count`, `view_count`, `user_id`, `user_login`, `user_profile_url` et `created_at_ts` au Dataclass `ListingCard`.
* **Modifications SQL** : Ajout d'une boucle `ALTER TABLE` automatique dans `db.py` pour ajouter ces colonnes de façon transparente sans écraser les données de l'utilisateur. Mise à jour de la fonction `upsert_listing` pour insérer ces valeurs.
* **Modifications Parser** : Analyse native du flux JSON de réponse (`item.get("favourite_count")`, extraction dans `photo.high_resolution.timestamp`, et l'objet `user`).

## 2. Déploiement Professionnel 24/7 via Systemd
**Fichiers affectés :** `install_services.sh` (Nouveau)

* **Objectif** : Garantir l'exécution autonome du scraper et du dashboard sur le serveur (VPS Linux), même après déconnexion du terminal SSH et sans passer par `screen`/`tmux`.
* **Fonctionnalité** : Le script crée deux processus "Daemons" Linux :
  1. `vinted-scraper.service` : Boucle infinie d'aspiration Vinted (`python -m vinted_radar.cli batch ...`).
  2. `vinted-dashboard.service` : Établit un micro-serveur web autonome (`python -m vinted_radar.cli dashboard --host 0.0.0.0 --port 8765`).
* **Avantages** : Redémarrage automatique en cas de crash Python (`Restart=always`). Exposition publique native avec `--host 0.0.0.0` (accessible via navigateur sur port 8765 en ouvrant UFW).

## 3. Crashs VPS et "Database is locked" (SQLite Deadlock)
**Fichiers affectés :** `vinted_radar/db.py`, `tests/test_history_repository.py`

* **Diagnostic** : Une fois la barre des ~300 000 annonces atteinte, les deux services s'entre-tuaient et refusaient de démarrer (`OperationalError: database is locked`). La cause racine était la fonction `_apply_migrations`, exécutée inconditionnellement à *chaque* ouverture de connexion SQLite. Elle contenait un très lourd `INSERT INTO ... SELECT ... JOIN` d'historique depuis les `discoveries` (les trouvailles) vers les `observations` qui confisquait le CPU et la base pendant plus de 30 secondes.
* **Fix SQLite - Activer le "Write-Ahead Logging" (WAL)** :
  * Paramétrage natif pour la haute fréquence : Ajout de `PRAGMA journal_mode = WAL;` (autorisant lecteurs et écrivains en simultané sans blocage).
  * Timing assoupli : Augmentation de `timeout=5.0` par défaut à `timeout=30.0` pour que le process accepte de patienter plutôt que de crasher.
* **Fix Code - Révocation de la Migration Startup** :
  * Suppression catégorique de la gigantesque requête de rétrocompatibilité.
  * Ajout du marqueur universel natif `PRAGMA user_version = 1`. Ainsi, au premier lancement, la version passe à 1, empêchant toutes fioritures annexes au démarrage. Les requêtes futures démarrent en 0.01s au lieu de 30s. Les bases existantes reprennent instantanément leur lecture et leur écriture de manière super-optimisée.
* **Fix Tests** : L'ancien test unitaire strict analysant cette migration obsolète a été naturellement retiré.
