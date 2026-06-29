# Prompt Claude Code — Étape 1/14 : Bootstrap

**Version** : 1.0
**Date** : 2026-06-29
**Projet** : evernote-to-obsidian

---

## À copier-coller dans Claude Code

---

Lis SPECS.md V1.1 et CLAUDE.md V1.0 à la racine du repo avant tout. Ces deux documents sont la référence — toute décision d'implémentation doit s'y appuyer.

## Tâche

Étape 1/14 de la séquence d'implémentation définie dans CLAUDE.md : Bootstrap.

Crée l'intégralité de la structure du repo telle que définie dans SPECS.md Bloc 2 "Structure du repo", avec tous les fichiers Python vides (juste leur docstring de module + signatures de fonctions avec docstrings et `pass`), les fichiers de configuration template, le requirements.txt, et le .gitignore.

Aucune logique métier ne doit être écrite à cette étape. Le but est de valider l'architecture complète en amont — repérer toute incohérence de structure avant qu'une ligne de code ne la masque.

## Livrables attendus

### 1. Fichiers Python avec docstrings uniquement

Pour chaque module listé dans SPECS.md Bloc 2 (`enex2obsidian.py` + tous les fichiers de `src/`) :

- Docstring de module en tête expliquant le rôle du module en 2-3 lignes
- Signature de chaque fonction publique anticipée, avec docstring décrivant : ce qu'elle prend en entrée, ce qu'elle retourne, ce qu'elle fait (en 1-3 lignes), et les cas d'erreur qu'elle peut signaler
- Corps de fonction = `pass` ou `raise NotImplementedError("Étape N de la séquence")`

Pour chaque fichier de tests (`tests/test_contract.py`, `tests/test_smoke.py`, `tests/test_limits.py`) :

- Docstring de module
- Squelettes de fonctions de test correspondant aux cas listés dans SPECS.md Bloc 5 (CT-01 à CT-18 pour test_contract.py, LI-01 à LI-10 pour test_limits.py, un test_smoke() pour test_smoke.py)
- Chaque fonction : docstring + `pytest.skip("Étape 9/12 de la séquence")` (ou l'étape appropriée selon CLAUDE.md)

### 2. Fichiers de configuration

- `config.yml.example` : exactement le contenu donné dans SPECS.md Bloc 2 "Configuration utilisateur"
- `carnets-a-migrer.txt.example` : exactement le contenu donné dans SPECS.md Bloc 2

Pas de `.env.example` — ce projet n'utilise aucune variable d'environnement sensible (pas d'API, pas de clé).

### 3. requirements.txt

Liste exacte issue de SPECS.md Bloc 2 "Stack". Versions épinglées avec `~=` pour autoriser les patches mineurs :

```
lxml~=5.0
markdownify~=0.11
python-slugify~=8.0
python-dateutil~=2.8
pyyaml~=6.0
pytest~=8.0
```

`pytest` ajouté car nécessaire pour les tests (pas une dépendance runtime mais incluse vu la pratique YT Extractor).

### 4. .gitignore

Doit exclure au minimum :
- `.venv/`
- `__pycache__/`
- `*.pyc`
- `config.yml` (le `.example` reste versionné, le vrai non)
- `carnets-a-migrer.txt` (idem, le `.example` reste versionné)
- `output/` (en cas de tests locaux)
- `*.enex` (sécurité : empêche le commit accidentel d'un carnet de référence contenant des données personnelles)
- `logs/`
- `.DS_Store`

### 5. README.md minimal

Une version stub en anglais avec uniquement :
- Titre du projet
- Une phrase de description (inspirée de SPECS.md Bloc 1 "Objectif")
- Section "Status" indiquant "Initial bootstrap — implementation in progress"
- Lien vers SPECS.md pour le détail

Pas de section installation/usage — sera rédigée à l'étape 14 quand le pipeline sera fonctionnel.

Pas de README.fr.md à ce stade — créé en étape 14.

## Ce qu'il ne faut PAS faire

- Aucune logique métier dans les fonctions (tout en `pass` ou `NotImplementedError`)
- Aucune dépendance entre modules (les imports `from src.X import Y` seront ajoutés à l'étape où le module Y est implémenté)
- Aucun test fonctionnel (les squelettes de tests sont là pour valider la structure, pas pour passer)
- Pas de fichier d'exemple `.enex` versionné (cf. constitution sécurité)
- Pas de `setup.sh` à ce stade (peut être ajouté plus tard si pertinent)

## Critères de validation

Avant de considérer l'étape terminée, vérifier :

1. L'arborescence produite correspond exactement à SPECS.md Bloc 2 "Structure du repo"
2. Chaque fichier Python a sa docstring de module non vide
3. Chaque fonction publique anticipée a une docstring décrivant entrée/sortie/comportement
4. `pip install -r requirements.txt` fonctionne dans un venv propre
5. `pytest --collect-only` détecte tous les tests prévus (CT-01 à CT-18, LI-01 à LI-10, test_smoke) et les marque comme skipped
6. `python enex2obsidian.py --help` lève `NotImplementedError` proprement (pas de crash avant d'arriver à l'appel)
7. Le `.gitignore` est en place avant le premier commit

## Format de commit attendu

Un seul commit pour cette étape :

```
feat: bootstrap — repository structure with empty modules and docstrings

- Full directory tree per SPECS.md Bloc 2
- Module and function docstrings for all anticipated public functions
- Test skeletons CT-01 to CT-18, LI-01 to LI-10, smoke test (all skipped)
- Configuration templates: config.yml.example, carnets-a-migrer.txt.example
- requirements.txt with pinned versions
- .gitignore excluding sensitive files (.enex, config.yml, carnets-a-migrer.txt, .venv, logs)
- Minimal README.md stub

No business logic. No cross-module imports. Step 1/14 of implementation sequence.
```

## Signal d'alarme

Si en lisant SPECS.md ou CLAUDE.md tu identifies une incohérence, ambiguïté, ou un cas non couvert qui bloquerait le bootstrap :

> 🚨 SPEC MANQUANTE : [description précise]

Stoppe et attends une instruction explicite. N'invente pas, ne complète pas, ne pars pas sur une interprétation.

---

## Notes pour l'humain (à ne pas envoyer à Claude Code)

**Après exécution de ce prompt**

- Vérifier visuellement l'arborescence (`tree -L 2` à la racine du repo)
- Lancer `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` pour valider la stack
- Lancer `pytest --collect-only` pour vérifier que les tests sont bien détectés et tous skipped
- Faire le premier commit avec le message proposé
- Passer au prompt étape 2 : `src/filename_normalizer.py`

**Si Claude Code dérive (ajoute de la logique non demandée, importe entre modules, etc.)**

Remonter le problème dans Claude.ai pour arbitrage, ne pas corriger directement dans le code. C'est exactement le pattern de gouvernance décrit dans METHODE_SPECS_CO-CONSTRUCTION.md.

**Temps estimé**

15-30 minutes côté Claude Code. Si ça prend plus, c'est qu'il y a dérive — interrompre.
