# Diagnostic — `data/vinted-radar.db` inaccessible en local

**Date**: 2026-03-22  
**Symptôme**: `python -m vinted_radar.cli runtime-status --db data/vinted-radar.db --format json` échoue avec `OperationalError: unable to open database file`.

## Evidence

### Reproduction

Commandes qui échouent :

```bash
python -m vinted_radar.cli runtime-status --db data/vinted-radar.db --format json
python -m vinted_radar.cli coverage --db data/vinted-radar.db --format json
python - <<'PY'
import sqlite3
sqlite3.connect('data/vinted-radar.db', timeout=1)
PY
```

Résultat observé :

- `OperationalError: unable to open database file`
- en lecture binaire directe, `PermissionError` sur ce fichier précis

### Contre-exemples utiles

Les autres bases du dossier `data/` s’ouvrent normalement :

- `data/vinted-radar-s06.db`
- `data/m001-closeout.db`

Donc le problème n’est pas SQLite en général, ni le code d’ouverture du projet.

### Évidence process

Un processus actif a été trouvé avec la ligne de commande suivante :

```text
scp.exe root@46.225.113.129:/root/Vinted/data/vinted-radar.db .\data\vinted-radar.db
```

### Évidence de fichier en cours d’écriture

La taille de `data/vinted-radar.db` augmentait encore pendant l’investigation :

```text
0 37884264448
1 37907103744
2 37928763392
```

Le `LastWriteTime` évoluait en parallèle.

## Investigation

Hypothèses testées :

1. **DB corrompue**  
   → peu compatible avec le fait que la taille du fichier continue d’augmenter pendant les essais.

2. **ACL / permission locale cassée**  
   → possible au premier regard, mais contredite par la présence d’un `scp.exe` en écriture active sur ce même chemin.

3. **Lock exclusif par un process externe**  
   → confirmé par :
   - le process `scp.exe` actif
   - la commande exacte ciblant `data/vinted-radar.db`
   - la croissance continue de la taille du fichier
   - l’impossibilité d’ouvrir le fichier pendant ce transfert

## Root Cause

La base locale `data/vinted-radar.db` n’est pas cassée côté application ; elle est **en cours de copie depuis le VPS vers exactement le même chemin local** via `scp.exe`.

Pendant ce transfert, Windows expose le fichier cible dans un état qui empêche l’ouverture SQLite et même certaines lectures directes.

En pratique :
- le CLI du projet échoue parce qu’il tente d’ouvrir un fichier encore en écriture exclusive / incomplète
- l’erreur `unable to open database file` est un effet secondaire du transfert en cours, pas un bug direct du repository ou du runtime

## Recommended Fix

### Opérationnel immédiat
- **Attendre la fin du `scp.exe`** avant d’utiliser `data/vinted-radar.db`
- ou **arrêter explicitement ce transfert** si ce fichier doit être consulté tout de suite

### Fix durable recommandé
Ne plus synchroniser directement vers le nom de base “vivant”. Copier d’abord vers un fichier temporaire, puis renommer atomiquement à la fin.

Exemple de stratégie :

1. copier vers `data/vinted-radar.syncing.db`
2. vérifier que `scp` est terminé
3. renommer vers `data/vinted-radar.db`

Bénéfices :
- le CLI ne voit jamais un fichier partiellement copié
- pas d’état intermédiaire ambigu
- lecture locale plus fiable

## Verification Plan

Après fin ou arrêt du transfert :

```bash
python - <<'PY'
import sqlite3
sqlite3.connect('data/vinted-radar.db', timeout=1).close()
print('open_ok')
PY

python -m vinted_radar.cli runtime-status --db data/vinted-radar.db --format json
python -m vinted_radar.cli coverage --db data/vinted-radar.db --format json
```

Succès attendu :
- ouverture SQLite OK
- commandes CLI runtime/couverture exécutables sans `OperationalError`

## Risk Assessment

**Confiance**: élevée  
**Risque principal**: faible côté code, moyen côté usage opérateur

Le risque n’est pas une régression logicielle du projet, mais une mauvaise ergonomie de synchronisation de la base locale depuis le VPS. Tant que le fichier de destination final sert aussi de cible de copie, le problème peut réapparaître.