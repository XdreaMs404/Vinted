# Review approfondie — Vinted Radar

**Date**: 2026-03-22  
**Périmètre**: dépôt complet, dossier `amélioration/`, artefacts `.gsd/`, code principal (`http`, `discovery`, `db`, `repository`, `runtime`, `dashboard`, `cli`), scripts racine récents.

## Résumé exécutif

Le projet a nettement progressé sur trois axes :

1. **performance d’acquisition** via l’API JSON Vinted + async + `curl_cffi`
2. **richesse de données** via les métadonnées étendues (likes, vues, seller, timestamp image)
3. **opérabilité** via la boucle runtime et le déploiement VPS

En revanche, la review a mis en évidence quatre points de vigilance structurants :

- drift architectural vers une API privée non documentée
- bug de câblage proxy dans le runtime CLI
- script systemd trop agressif (root, exposition publique, boucle batch)
- dette de scalabilité côté dashboard / scoring / runtime snapshot

## Ce qui est bien

- séparation de responsabilités encore claire (`http` / `services` / `repository` / `dashboard`)
- socle de tests sérieux pour un projet de scraping/produit local
- pattern sain entre HTML dashboard et endpoints JSON de diagnostic
- enrichissement du modèle cohérent avec les attentes M002
- WAL SQLite et allègement des migrations startup pertinents

## Problèmes relevés pendant la review

### 1. Architecture d’acquisition
La découverte repose maintenant sur `https://www.vinted.fr/api/v2/catalog/items`, ce qui entre en tension avec les décisions initiales de ne pas dépendre centralement d’API privées non documentées.

**Statut**: non corrigé dans ce pass. C’est un choix produit/architecture à expliciter, pas juste un patch.

### 2. Proxy non câblé correctement dans le runtime
Le flag `--proxy` existait sur `batch`, mais il n’était pas transmis au runtime. `continuous` n’exposait pas non plus ce flag.

**Statut**: corrigé.

### 3. Script systemd trop agressif
Le script lançait les services en `root`, exposait le dashboard en `0.0.0.0`, et utilisait `batch` + `Restart=always` comme pseudo-boucle continue.

**Statut**: corrigé.

### 4. Drift documentaire
Les docs du dossier `amélioration/` annonçaient un fallback HTML automatique et la suppression totale du throttle async, alors que le code réel ne correspondait pas exactement à cela.

**Statut**: corrigé.

### 5. Scalabilité produit
Le dashboard et certaines surfaces runtime/scoring recalculent encore trop largement en mémoire. À l’échelle M002 (gros corpus + explorer complet), cela deviendra un vrai goulot.

**Statut**: non corrigé dans ce pass. Demande une évolution de conception, pas juste une retouche.

### 6. Base `data/vinted-radar.db` actuellement problématique
Pendant la review, cette base était inaccessible depuis le CLI/runtime (`OperationalError: unable to open database file`), alors que d’autres DB du dossier `data/` s’ouvraient normalement.

**Statut**: non corrigé dans ce pass. À investiguer côté lock/process/ACL/état du fichier.

## Corrections appliquées dans ce pass

### A. Proxy plumbing réparé
**Fichiers**:
- `vinted_radar/services/runtime.py`
- `vinted_radar/cli.py`
- `tests/test_runtime_service.py`
- `tests/test_runtime_cli.py`

**Changements**:
- ajout de `proxies` dans `RadarRuntimeOptions`
- transmission de `proxies` depuis `batch` et `continuous`
- passage effectif de `proxies` au `discovery_service_factory`
- ajout / mise à jour des tests pour vérifier le câblage

### B. Observabilité runtime légèrement durcie
**Fichier**:
- `vinted_radar/services/runtime.py`

**Changement**:
- `_runtime_snapshot()` logue maintenant explicitement l’exception au lieu d’échouer totalement en silence

### C. Installateur systemd assaini
**Fichier**:
- `install_services.sh`

**Changements**:
- service scraper basé sur `continuous` au lieu de `batch`
- utilisateur/groupe du projet par défaut au lieu de `root` forcé
- dashboard lié à `127.0.0.1` par défaut
- `Restart=on-failure`
- variables d’environnement pour personnaliser intervalle, port, DB, utilisateur
- `NoNewPrivileges=true` et `PrivateTmp=true`

### D. Docs d’amélioration réalignées
**Fichiers**:
- `amélioration/resume_changements.md`
- `amélioration/refactoring_async.md`
- `amélioration/systemd_et_optimisations_sqlite.md`

**Changements**:
- suppression de l’affirmation erronée sur le fallback HTML automatique
- mise à jour du statut du correctif cookies async
- clarification du rôle respectif du `Semaphore` et du `request_delay`
- documentation systemd alignée avec le nouveau script

## Points encore ouverts après corrections

### Priorité haute
1. **Décider explicitement de la posture d’acquisition**
   - API privée assumée ?
   - ou retour à une stratégie hybride avec fallback HTML réel ?

2. **Traiter la scalabilité du dashboard / scoring**
   - pagination/tri/filtres SQL côté serveur
   - éviter le recalcul global du corpus sur chaque payload

3. **Diagnostiquer `data/vinted-radar.db`**
   - lock externe ?
   - problème d’ACL ?
   - fichier dégradé ?

### Priorité moyenne
4. **Nettoyage repo**
   - scripts de debug racine
   - payloads live commités (`item.json`, sorties de tests, etc.)
   - arbre `src/vinted_radar/` probablement obsolète

5. **Couverture de tests sur les champs enrichis**
   - `favourite_count`
   - `view_count`
   - `user_id`
   - `user_login`
   - `user_profile_url`
   - `created_at_ts`

## Vérification

Commandes exécutées après corrections :

```bash
python -m pytest -q
bash -n install_services.sh
```

Résultat :
- **88 tests passent**
- **script shell syntaxiquement valide**

## Fichiers modifiés pendant ce pass

- `vinted_radar/cli.py`
- `vinted_radar/services/runtime.py`
- `tests/test_runtime_cli.py`
- `tests/test_runtime_service.py`
- `install_services.sh`
- `amélioration/resume_changements.md`
- `amélioration/refactoring_async.md`
- `amélioration/systemd_et_optimisations_sqlite.md`

## Conclusion

Le projet est plus solide qu’avant la review, surtout sur l’opérabilité runtime et le déploiement. Les problèmes restants sont désormais surtout des sujets de direction technique : acquisition, scalabilité, et hygiène long terme du repo.