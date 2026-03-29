---
version: 1
git:
  auto_push: true
  push_branches: true
  remote: origin
  main_branch: main
  isolation: branch
  merge_strategy: squash
  snapshots: true
  auto_pr: true
  pr_target_branch: main
auto_supervisor:
  soft_timeout_minutes: 12
  idle_timeout_minutes: 6
  hard_timeout_minutes: 20
context_selection: smart
verification_commands:
  - python -m pytest tests/test_runtime_cli.py tests/test_runtime_service.py tests/test_postgres_schema.py -q
verification_auto_fix: true
verification_max_retries: 1
custom_instructions:
  - Toujours travailler dans le dossier principal du projet, pas dans `.gsd/worktrees/`.
  - À la fin de chaque slice `Sxx`, commit et push les changements sur le dépôt GitHub.
---

# GSD Skill Preferences
