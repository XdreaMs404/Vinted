# Remise en route propre après corruption SQLite

## État des fichiers

- `data/vinted-radar.db` → source corrompue, à garder comme artefact de diagnostic uniquement.
- `data/vinted-radar.recovered.db` → copie de secours saine mais partielle (opérateur/runtime/catalogues/probes).
- `data/vinted-radar.clean.db` → nouvelle base de travail pour relancer le radar marché.

## Ce qu'il ne faut plus faire

- ne plus lancer de commandes marché sur `data/vinted-radar.db`
- ne plus synchroniser directement vers le nom final vivant sans snapshot + health check
- ne pas confondre la base récupérée partielle avec une vraie base marché complète

## Procédure recommandée

### 1. Vérifier la copie de secours

```bash
python -m vinted_radar.cli db-health --db data/vinted-radar.recovered.db
python -m vinted_radar.cli runtime-status --db data/vinted-radar.recovered.db
```

But: confirmer que l'opérateur dispose bien d'une copie saine pour l'historique runtime et les probes.

### 2. Repartir sur une base neuve

Premier cycle batch de vérification :

```bash
python -m vinted_radar.cli batch \
  --db data/vinted-radar.clean.db \
  --page-limit 1 \
  --max-leaf-categories 6 \
  --state-refresh-limit 10
```

Puis contrôle santé :

```bash
python -m vinted_radar.cli db-health --db data/vinted-radar.clean.db
python -m vinted_radar.cli runtime-status --db data/vinted-radar.clean.db
```

### 3. Basculer en continu quand le smoke batch est bon

```bash
python -m vinted_radar.cli continuous \
  --db data/vinted-radar.clean.db \
  --page-limit 1 \
  --max-leaf-categories 4 \
  --state-refresh-limit 6 \
  --interval-seconds 1800 \
  --dashboard \
  --host 127.0.0.1 \
  --port 8765
```

## Surfaces à utiliser ensuite

- résumé marché / ranking proof : `http://127.0.0.1:8765/`
- explorer paginé SQL : `http://127.0.0.1:8765/explorer`
- runtime JSON : `http://127.0.0.1:8765/api/runtime`
- health JSON : `http://127.0.0.1:8765/health`

## Règle opératoire de sync à garder

### Sync sûre VPS → local

```bash
python scripts/sync_db_safe.py \
  --remote-host root@46.225.113.129 \
  --remote-db /root/Vinted/data/vinted-radar.db \
  --destination data/vinted-radar.clean.db \
  --integrity
```

Cette procédure :
1. crée un snapshot SQLite cohérent sur le VPS
2. copie vers un fichier local temporaire
3. vérifie la santé locale
4. ne promeut le fichier que s'il est sain

## Récupération d'urgence si une source redevient corrompue

```bash
python scripts/recover_partial_db.py \
  --source data/vinted-radar.db \
  --destination data/vinted-radar.recovered.db \
  --report data/vinted-radar.recovered.report.json \
  --force
```

## Limite actuelle à garder en tête

L'explorer SQL séparé évite de charger tout le corpus juste pour parcourir des listings, mais le dashboard résumé principal continue à dépendre du chargement/scoring complet du corpus. C'est un vrai pas M002, pas la fin du chantier.
