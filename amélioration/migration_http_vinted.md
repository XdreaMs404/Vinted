# Amélioration du Transport HTTP (Vinted Radar)

Ce document récapitule les modifications apportées au module de communication HTTP pour contourner les protections (WAF/TLS-fingerprinting) de Vinted et améliorer la robustesse globale du scraper.

## 1. Migration vers `curl_cffi` (TLS Impersonation)

L'utilisation de la librairie standard `requests` a été abandonnée au profit de `curl_cffi.requests.Session`.
*   **Pourquoi ?** Vinted utilise des protections basées sur l'empreinte TLS (JA3). `requests` est facilement identifiable.
*   **Solution :** Utilisation de l'argument `impersonate="chrome116"`. Le scraper se présente désormais avec la pile réseau exacte d'un navigateur Chrome moderne, ce qui réduit drastiquement les risques de blocage immédiat.

## 2. Gestion de Session Intelligente (Warm-up)

Une nouvelle logique de "préchauffage" (Warm-up) a été implémentée dans la classe `VintedHttpClient`.
*   **Fonctionnement :** Avant toute requête de données, le client effectue un "ping" sur la page d'accueil de Vinted (`https://www.vinted.fr/`).
*   **Cookie de session :** Cette étape permet de récupérer le cookie vital `_vinted_fr_session`. Ce cookie est ensuite automatiquement injecté dans toutes les requêtes suivantes via le "cookie jar" interne de la session.
*   **Acquisition paresseuse (Lazy) :** Le warm-up est déclenché automatiquement lors du premier appel à `get_text()` s'il n'a pas été fait manuellement.

## 3. Robustesse et Fiabilité (Production-Ready)

Plusieurs mécanismes de sécurité ont été ajoutés pour garantir la continuité du service :

*   **Retry avec Backoff :** La phase de warm-up dispose d'un système de tentatives (3 par défaut) avec un délai croissant en cas d'échec réseau passager.
*   **Gestion du 403 (Cookie expiré) :** Si Vinted répond par un code `403 Forbidden` (souvent signe d'un cookie expiré ou invalidé), le client invalide automatiquement sa session actuelle, relance un warm-up complet et retente la requête initiale.
*   **Thread-Safety :** L'accès au mécanisme de warm-up est protégé par un verrou (`threading.Lock`). Cela permet d'utiliser le même client dans un environnement multi-thread sans risquer de corrompre la session ou de lancer plusieurs warm-ups simultanés.
*   **Rate-Limiting (Throttling) :** Le délai de sécurité entre deux requêtes (`request_delay`) a été préservé et optimisé dans une méthode interne dédiée (`_throttled_get`).

## 4. Impact sur le Projet

*   **Fichier modifié :** `vinted_radar/http.py` (réécriture complète).
*   **Dépendances :** Mise à jour de `pyproject.toml` pour remplacer `requests` par `curl_cffi>=0.7`.
*   **Interface :** L'objet `FetchedPage` et l'interface `get_text()` restent identiques pour ne pas impacter les services de découverte (`discovery.py`) ou de rafraîchissement (`state_refresh.py`).

---
*Date : 19 Mars 2026*
