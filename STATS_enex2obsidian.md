# STATS — enex2obsidian

*Mesures générées le 2026-07-26. Commandes à exécuter depuis la racine du dépôt.*

## enex2obsidian

- **Date du premier commit** : 2026-06-29
  `git log --reverse --format='%ad' --date=short | head -1`
- **Date du dernier commit** : 2026-07-03
  `git log -1 --format='%ad' --date=short`
- **Nombre total de commits** : 49
  `git rev-list --count HEAD`
- **Nombre de jours calendaires distincts avec au moins un commit** : 5
  `git log --format='%ad' --date=short | sort -u | wc -l`
- **Durée calendaire entre premier et dernier commit** : 3 jours
  `git log --format='%at' | sort -n | awk 'NR==1{f=$1} END{printf "%d jours\n", ($1-f)/86400}'`
- **Plus longue interruption entre deux commits** : 1,07 jour
  `git log --format='%at' | sort -n | awk 'NR>1{g=$1-p; if(g>m)m=g} {p=$1} END{printf "%.2f jours\n", m/86400}'`
- **Nombre de fichiers de code, et lignes de code par langage** (hors `.venv`, `.git`, `__pycache__`) :
  - `.py` : 14 fichiers, 5454 lignes

  `find . -name '*.py' -not -path './.venv/*' -not -path './__pycache__/*' | wc -l`
  `find . -name '*.py' -not -path './.venv/*' -not -path './__pycache__/*' -print0 | xargs -0 cat | wc -l`
- **Nombre de fichiers markdown de documentation, et lignes totales** : 7 fichiers, 2552 lignes (documentation rédigée).
  Aucun contenu non documentaire en `.md` dans ce dépôt (les fixtures de test sont au format `.enex`, pas `.md`). Le chiffre inclut désormais les fichiers `STATS` et `FICHE_PASSATION` produits pour cet exercice.
  `find . -name '*.md' -not -path './.git/*' -not -path './.venv/*' -not -path './.pytest_cache/*' | wc -l`
  `find . -name '*.md' -not -path './.git/*' -not -path './.venv/*' -not -path './.pytest_cache/*' -print0 | xargs -0 cat | wc -l`
- **Nombre de tests, et commande utilisée pour les compter** : 123 fonctions `def test_` dans 3 fichiers `test_*.py` (`test_contract.py`, `test_limits.py`, `test_smoke.py`)
  `grep -rE '^\s*def test_' --include='*.py' --exclude-dir=.venv . | wc -l`
- **Part du code réservée aux tests** : 55,1 % (3004 lignes de test sur 5454 lignes `.py` au total ; 4 fichiers sous `tests/`)
  Lignes de test : `find . -name '*.py' \( -name 'test_*.py' -o -path '*/tests/*' \) -not -path './.venv/*' -not -path './__pycache__/*' -print0 | xargs -0 cat | wc -l`
  Total `.py` : `find . -name '*.py' -not -path './.venv/*' -not -path './__pycache__/*' -print0 | xargs -0 cat | wc -l`
- **Taille moyenne d'une fonction Python (hors test)** : 34,2 lignes (médiane 26 ; min 2, max 184) sur 56 fonctions dans 10 fichiers.
  Mesuré par script AST : `ast.FunctionDef` + `end_lineno - lineno + 1`, sur les `.py` hors `tests/` et `test_*.py`.
- **Le code est-il commenté / documenté ?** : oui, principalement par docstrings.
  - Docstrings : fonctions 50/56 (89 %), classes 12/13 (92 %), modules 10/10 (100 %).
  - Commentaires inline : 83 pour 2014 lignes de code (ratio 0,04).
- **Version courante déclarée, si elle figure quelque part** :
  - `SPECS.md` : Version 1.8 (2026-06-30) — `grep -m1 -i version SPECS.md`
  - `BACKLOG.md` : Version 1.1

---

## Publiabilité

Vérification de l'état courant **et** de l'historique git.

- **Secrets / clés d'API** : aucun. Aucun `.env` sur le disque ni dans l'historique. L'outil est déterministe et sans LLM (constitution règle 7), donc aucune clé d'API n'est requise. Aucun motif de clé trouvé (arbre courant + `git rev-list --all`). Point d'hygiène mineur : `.gitignore` ne contient pas de règle `.env` — sans risque actif ici, mais à ajouter par précaution.
- **Chemins personnels** : aucun dans les fichiers suivis (la configuration passe par `config.yml.example`).
- **Données personnelles réelles** : aucune. Seules deux fixtures de test synthétiques sont commitées (`tests/fixtures/testmigration.enex`, `tests/fixtures/malformed.enex`). Les ~1600 notes administratives réelles ne sont pas dans le dépôt.
- **Noms de clients / employeurs** : aucun.
- Le dépôt n'a pas encore de remote (`SPECS.md` : « Repo : à créer »).

**Conclusion : publiable.** Correction facultative de durcissement : ajouter `.env` à `.gitignore`.

---

## Autres mesures (critères de livraison)

- **Modules source** (.py hors test) : 10
- **Dépendances runtime** : 5 (lxml, markdownify, python-slugify, python-dateutil, pyyaml) + pytest
- **Ratio documentation / code** : 0,45 : 1 (2439 lignes `.md` pour 5454 lignes `.py`)
- **Annotations de type** : présentes (60 occurrences `->` / `from __future__ import annotations`)
- **Packaging installable** : absent
- **Intégration continue** : absente
- **Outillage lint / format / typecheck** : absent
- **LICENSE** : absent

