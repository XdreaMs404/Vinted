# Migration vers l'API JSON Vinted (Discovery Service)

Ce document récapitule la transition du scraper de l'analyse HTML vers l'utilisation directe de l'API JSON de Vinted pour la découverte des annonces.

## 1. Nouvelle Stratégie de Collecte

Le service de découverte (`discovery.py`) a été réarchitecturé pour cibler l'endpoint API `https://www.vinted.fr/api/v2/catalog/items`.

*   **Format des données :** Passage d'un parsing HTML lourd (BeautifulSoup) à un traitement JSON natif.
*   **Performance :** Augmentation du nombre d'articles par page (`per_page=96` contre 24 en HTML), ce qui divise par 4 le nombre de requêtes nécessaires pour la même couverture.
*   **Interface unifiée :** Le nouveau module `vinted_radar/parsers/api_catalog_page.py` convertit les réponses JSON vers les mêmes dataclasses (`ListingCard`, `CatalogPage`), garantissant une compatibilité totale avec le reste du système (Base de données, Scoring, Dashboard).

## 2. Orchestration et Pagination

La logique de navigation a été simplifiée et rendue plus déterministe.

*   **URLs Dynamiques :** Utilisation d'un helper `_build_api_catalog_url` qui injecte systématiquement les `catalog_ids`, `page` et `per_page`.
*   **Contrôle de Flux :** La boucle de pagination utilise désormais les compteurs réels renvoyés par Vinted (`current_page` et `total_pages`). Le scraper s'arrête proprement dès qu'il atteint la fin du catalogue, même si la limite de pages configurée est plus élevée.
*   **Guarde de Sécurité :** Ajout d'un arrêt anticipé si une page est retournée vide, évitant des requêtes inutiles sur des catalogues peu profonds.

## 3. Robustesse et Observabilité

Des mécanismes de diagnostic avancés ont été intégrés directement dans le flux de découverte :

*   **Logging Détaillé :** Chaque étape de la collecte est tracée (ID du catalogue, titre, progression de la pagination, nombre d'articles trouvés).
*   **Gestion des Erreurs JSON :** En cas de réponse malformée (ex: blocage WAF renvoyant du HTML), le scraper capture l'erreur, loggue les 200 premiers caractères du corps de la réponse pour analyse, et marque le scan comme "failed" sans faire planter le cycle complet.
*   **Protection contre les récurrences :** Les exceptions sont isolées par catalogue, permettant au radar de continuer sur les catégories suivantes même si une catégorie spécifique rencontre un problème technique.

## 4. Validation

*   **Tests Unitaires :** Refonte complète de `tests/test_discovery_service.py` pour simuler des payloads API complexes.
*   **Couverture :** Ajout de tests spécifiques pour l'arrêt de pagination, le multi-page, les erreurs de décodage JSON et les pages vides.

---
*Date : 19 Mars 2026*
*Auteur : Antigravity (AI Assistant)*
