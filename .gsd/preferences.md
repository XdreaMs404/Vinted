---
version: 1
git:
  auto_push: true
  remote: origin
  main_branch: main
  isolation: none
  merge_strategy: squash
custom_instructions:
  - Toujours travailler dans le dossier principal du projet, pas dans `.gsd/worktrees/`.
  - À la fin de chaque slice `Sxx`, commit et push les changements sur le dépôt GitHub.
---

# GSD Skill Preferences
