# Refactoring Asynchrone (Vinted Radar)

Ce document récapitule l'ensemble des changements architecturaux appliqués pour accélérer la récolte de données de Vinted Radar via l'asynchronisme.

## 1. Client HTTP Asynchrone (`http.py`)
Afin de parser les millions d'items plus rapidement sans bloquer l'exécution, nous avons ajouté une interface asynchrone complète à côté de l'interface synchrone existante :
- **Intégration de `curl_cffi.requests.AsyncSession`** : permet de lancer des requêtes de manière asynchrone tout en gardant l'impersonation TLS (évite les blocages WAF comme Cloudflare).
- **Nouvelles méthodes** : `warm_up_async()`, `get_text_async()` et `close_async()`.
- **Thread-Safety coopérative** : utilisation de `asyncio.Lock` lors du warm-up pour s'assurer qu'une seule coroutine ne demande le cookie de session à la fois.
- **Rétrocompatibilité** : L'interface synchrone (`get_text`) a été conservée pour ne pas casser le `state_refresh.py` ou le CLI qui l'utilisent encore.

## 2. Découverte Concurrente (`discovery.py`)
La boucle principale de découverte a été transformée pour tirer parti des entrées/sorties asynchrones.
- **`run_async()`** : Le moteur principal est devenu asynchrone. L'ancienne méthode `run()` a été transformée en simple wrapper (via `asyncio.run()`) pour garantir la compatibilité ascendante avec les autres services.
- **Parallélisation via `asyncio.gather()`** : La boucle classique séquentielle sur les catalogues feuilles a été remplacée. Désormais, chaque catalogue feuille (`_scan_catalog()`) tourne comme une coroutine indépendante. 
- **Contrôle de Concurrence (`Semaphore`)** : Un `asyncio.Semaphore(15)` a été mis en place pour s'assurer qu'il n'y ait jamais plus de 15 requêtes Vinted en vol en même temps.
- **Pagination Séquentielle** : Au sein d'un même catalogue, la pagination reste séquentielle (la page N+1 est requêtée après la page N), car on dépend des métadonnées de pagination. Mais 15 catégories différentes peuvent paginer en parallèle.

## 3. Adaptation des Tests
Pour que la suite de tests (88 tests) reste 100% verte, les bouchons (`FakeHttpClient`) ont été adaptés.
- Ajout des méthodes natives `get_text_async` aux bouchons.
- **Migration vers l'API JSON** : Les anciens tests (`test_history_repository.py` et `test_history_cli.py`) reposaient sur des fixtures HTML entières. Ils ont été réécrits pour utiliser les structures de données (JSON) de la nouvelle API v2 de Vinted.

## 4. Améliorations Qualité post-Refacto
Une fois la base en place, 4 améliorations structurelles ont été appliquées suite à un audit :
1. **Suppression du Throttle Async global** : Maintenir un `last_request_at` global entre 15 coroutines ne fonctionnait pas. Le `Semaphore(15)` est le seul mécanisme pertinent et suffisant pour limiter le taux de requêtes.
2. **Nettoyage des ressources** : Appel de `await self.http_client.close_async()` dans un bloc `finally` pour garantir la libération des *file descriptors*. Un fallback `getattr` est utilisé pour que les tests sans vraie session HTTP n'échouent pas.
3. **Optimisation des Dataclasses** : Remplacement d'un hack `__post_init__` sur un field `Optional[set]` par un constructeur natif `field(default_factory=set)` dans le `_CatalogScanResult`.
4. **Clean Code** : Réorganisation propre des imports et de l'instanciation des loggers Python.
