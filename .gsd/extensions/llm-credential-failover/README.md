# llm-credential-failover

Extension GSD globale pour gérer plusieurs credentials LLM par provider, y compris plusieurs comptes OAuth pour un même provider.

## Ce que ça ajoute

- répéter un login OAuth sur le même provider **ajoute un nouveau compte** au lieu d'écraser l'ancien
- la rotation de credential sur erreur de **rate limit / quota / usage cap** fonctionne aussi avec **plusieurs comptes OAuth**
- le refresh d'un token OAuth expiré se fait sur **le bon compte sélectionné**
- le backoff credential/provider est **persisté entre redémarrages** dans `~/.gsd/agent/llm-credential-backoff.json`
- `/gsd setup llm` ouvre maintenant un **assistant de configuration LLM** plus propre
- commande dédiée : `/llm-accounts`
- `/llm-accounts list` ouvre maintenant un **tableau OpenAI/Codex** qui montre le **compte actif dans la session**, les **limites 5h et hebdo restantes**, le **plan**, les **credits** s'ils existent, et le **backoff** credential/provider
- le tableau `/llm-accounts list` rafraîchit les limites OpenAI via `GET https://chatgpt.com/backend-api/wham/usage` pour chaque credential `openai-codex`, sans dépendre d'un patch dans le cœur de GSD
- le flow OAuth interactif pour les providers à callback local réutilise maintenant une UI de login robuste avec **callback navigateur + collage manuel en parallèle**
- sous Windows, l'ouverture du navigateur passe par **PowerShell Start-Process** pour préserver l'URL OAuth complète (les URLs avec `&` sont fragiles via `cmd /c start`)
- après login, l'extension dit explicitement si un **nouveau compte a été ajouté** ou si tu as simplement **reconnecté le même compte existant**
- pour `openai-codex`, l'identité stable est maintenant basée sur l'**utilisateur OAuth réel** (`chatgpt_account_user_id` / `chatgpt_user_id` / `sub`) et non plus seulement sur `chatgpt_account_id`, ce qui permet plusieurs utilisateurs d'un même compte/team ChatGPT

## Pourquoi ça survit à `gsd update`

L'extension vit dans `~/.gsd/agent/extensions/llm-credential-failover/`.
Elle ne modifie pas le code npm installé de GSD.

## Commandes

```text
/gsd setup llm
/llm-accounts setup
/llm-accounts login openai-codex
/llm-accounts list
/llm-accounts list openai-codex
/llm-accounts remove openai-codex 2
/llm-accounts clear-backoff openai-codex all
```

## Tableau `/llm-accounts list` pour OpenAI / Codex

Quand `openai-codex` est configuré, `/llm-accounts list` bascule sur une vue dédiée :

- **ligne par compte** avec email masqué, état (`ACTIVE`, `NEXT`, `READY`, `BACKOFF`, `LIMIT`, `ERROR`)
- **compte actif dans la session courante** ou **prochain compte sticky** si la session n'a pas encore consommé de tour OpenAI
- **reste 5h** et **reste hebdo** par compte
- **panneau de détail** pour le compte sélectionné : plan, suffixe user/workspace, expiration OAuth, backoff, credits, code review limits, buckets supplémentaires
- **raccourcis clavier** : `↑/↓` pour naviguer, `r` pour rafraîchir, `Esc` pour fermer

En mode non interactif, la même commande retombe sur un **rapport texte** avec les mêmes informations principales.

## Ajouter plusieurs OAuth Codex précisément

### Méthode recommandée

1. Lance `/gsd setup llm`
2. Choisis `Add an OAuth account`
3. Choisis `openai-codex`
4. Termine le login dans le navigateur
5. Pour le **deuxième compte**, utilise de préférence un **autre profil navigateur** ou une **fenêtre privée**
6. Recommence autant de fois que nécessaire

### Méthode directe

```text
/llm-accounts login openai-codex
```

Répète cette commande pour chaque compte supplémentaire.

## Si tu vois `State mismatch`

En pratique, cela veut presque toujours dire une de ces deux choses :

- tu as validé un **ancien onglet OAuth** au lieu du plus récent
- sur Windows, l'URL ouverte automatiquement avait été tronquée / mal interprétée par un lanceur naïf

Le flow de cette extension ouvre désormais le navigateur de façon sûre sur Windows, mais si le message apparaît quand même :

1. ferme les anciens onglets/login Codex
2. relance une seule tentative de login
3. utilise uniquement l'URL la plus récente
4. si tu ajoutes un autre compte, fais-le dans un autre profil navigateur / une fenêtre privée

## Pourquoi un login peut finir sans ajouter de nouveau credential

Si l'inventaire reste à `1 credential`, le cas le plus probable est simple :

- tu as reconnecté **le même compte OpenAI/Codex** que celui déjà stocké

L'extension le détecte maintenant et l'annonce explicitement après le login.

## Notes importantes

- `/logout` continue à supprimer **tout** le provider. Pour supprimer un seul compte, utilise `/llm-accounts remove`.
- la rotation se fait au niveau runtime pour les tours normaux et pour `/gsd auto`
- le backoff persistant est stocké ici : `~/.gsd/agent/llm-credential-backoff.json`
