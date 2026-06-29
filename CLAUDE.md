# CLAUDE.md — Projet Migration Evernote → Obsidian

**Version** : 1.1
**Date** : 2026-06-29
**Auteur** : François Biller
**Statut** : Étape 3/14 validée (enex_parser) — étape 4/14 en cours (metadata_extractor)
**Repo** : à créer

Emplacement cible : `~/Projects/evernote-to-obsidian/CLAUDE.md`
Portée : ce projet uniquement.

Ce fichier complète les conventions transversales définies dans :
https://github.com/fbi92120/vibe-coding-governed
(CLAUDE.global.md, CLAUDE.projects.md, METHODE_SPECS_CO-CONSTRUCTION.md)

---

## Ce projet

Outil CLI Python qui convertit les fichiers `.enex` exportés depuis l'app Evernote macOS en notes Markdown organisées dans un vault Obsidian dédié aux notes administratives.

Migration ponctuelle d'un corpus d'environ 1600 notes admin en V1, élargi à ~6500 notes connaissance en V2.

Repo    : à créer
Specs   : SPECS.md V1.1 — lire avant toute implémentation
Méthode : METHODE_SPECS_CO-CONSTRUCTION.md (projet vibe-coding-governed)
Retour d'expérience hérité : YT_EXTRACTOR_RETOUR_EXPERIENCE.md

## État courant

| Version | Date | Contenu |
|---|---|---|
| V1.0 SPECS | 2026-06-29 | Spécifications initiales co-construites dans Claude.ai |
| V1.1 SPECS | 2026-06-29 | Stack XML actée (lxml), plafond pièce jointe 200 Mo, fixture test = carnet réel |

Implémentation : non démarrée.

## Stack technique

```
Python 3.12 via .venv/ (venv local, PEP 668-compliant — voir setup.sh)
lxml (mode recover=True)       # parsing XML ENEX tolérant
markdownify                    # conversion XHTML → Markdown
python-slugify                 # slug ASCII
python-dateutil                # parsing dates ISO 8601
pyyaml                         # config.yml + frontmatter YAML
```

Aucune dépendance réseau. Aucun token, aucune clé API. Tout en local.

## Constitution — règles absolues de ce projet

Ces règles ne peuvent jamais être violées, même si le résultat semble acceptable.

1. **Aucun arrêt du batch sur erreur** — toute erreur est tracée et le traitement continue. Le batch s'arrête uniquement quand toutes les notes ont été tentées.
2. **Aucune perte silencieuse** — toute note produit soit un `.md`, soit une ligne explicite dans le log d'erreurs.
3. **Aucune pièce jointe silencieusement ignorée** — toute pièce jointe est copiée ou loggée. Mention dans le `.md` si manquante.
4. **Aucune métadonnée inventée** — valeur vide si absente du `.enex`. Jamais une valeur fabriquée.
5. **Idempotence** — même périmètre = même résultat (modulo logs horodatés).
6. **Non-destructivité du source** — jamais d'écriture dans le dossier des `.enex`.
7. **Pas de LLM dans le pipeline** — transformation purement déterministe.
8. **Pas d'écrasement implicite** — `.md` cible existant = skip + log. Écrasement uniquement via `--force`.
9. **Pas de path traversal** — toute écriture vérifiée comme étant strictement sous `vault_path`.

## Comportements aux limites — décisions actées

Voir SPECS.md Bloc 4 pour le tableau complet. Décisions à garder en tête en permanence :

| Situation | Comportement |
|---|---|
| Note avec XHTML mal formé | Log + passage à la note suivante. Le carnet continue. |
| `.enex` introuvable pour carnet listé | Log + passage au carnet suivant. Le batch continue. |
| Pièce jointe > 200 Mo | Log + skip. Mention dans le `.md` à l'emplacement attendu. |
| Collision pièce jointe | Suffixe `-2`, `-3`, ... + log CSV. Pas d'écrasement. |
| Collision nom `.md` | Suffixe `-2`, `-3`, ... + log CSV. Pas d'écrasement. |
| Note sans titre | Slug `note-[8-chars-guid].md`, `title: ""` dans frontmatter. |
| Note sans contenu (juste pièce jointe) | `.md` produit avec frontmatter + lien/embed. |
| `.md` cible existant | Skip + log (défaut) ou écrasement (`--force`). |
| `--dry-run` | Aucune écriture. Plan affiché sur stdout. |
| Caractère dangereux dans nom pièce jointe | Sanitization + log avec mention `sanitized`. |
| Chemin résolu hors `vault_path` | Abandon écriture + log erreur sécurité. |

## Tests — Validation des modules à interface format externe

**Validation par module à interface format externe**

Pour tout module qui consomme ou produit un format externe (ENEX, XHTML Evernote, base64, frontmatter YAML lu par Obsidian), la validation comprend trois étapes obligatoires avant commit :

1. Tests unitaires (CT-XX) sur fragments synthétiques — vérifient le contrat
2. Audit code externe (Codex) — détecte les bugs de structure et de sécurité
3. Test empirique sur fichier réel non synthétique — détecte les particularités du format réel que les fragments ne couvrent pas

Cette règle a été extraite de l'incident enex_parser V1.5 où un bug bloquant (huge_tree=False) ne s'est manifesté que sur un vrai .enex de 91 Mo, après commit. Les fragments XML inline du test CT-01 ne pouvaient pas le détecter.

Modules concernés dans la séquence V1 : enex_parser, metadata_extractor, content_converter, attachment_handler, writer.

## Carnet de référence pour les tests

Le test smoke s'exécute sur un carnet Evernote réel désigné par variable d'environnement :

```bash
export ENEX_REFERENCE_FILE=~/Migration-Evernote/exports-enex/[nom-carnet-test].enex
pytest tests/test_smoke.py
```

Recommandation pour le choix : petit carnet (10-30 notes), représentatif, avec au moins une note texte, une note avec PDF, une note avec image, une note dégradée.

Le `.enex` de référence n'est JAMAIS versionné dans le repo (risque de fuite de données personnelles).

Les tests de contrat (CT-XX dans SPECS.md) utilisent des fragments XML inlinés dans le code de test, indépendants du carnet de référence.

## Séquence d'implémentation — ordre obligatoire

```
1.  Bootstrap (structure repo + fichiers vides + docstrings)
2.  src/filename_normalizer.py   (slug, sanitization, anti-traversal)
3.  src/enex_parser.py           (parsing XML, extraction notes brutes)
4.  src/metadata_extractor.py    (extraction + normalisation frontmatter)
5.  src/content_converter.py     (XHTML → Markdown)
6.  src/attachment_handler.py    (décodage, collisions, écriture)
7.  src/notebook_selector.py     (parsing carnets-a-migrer.txt)
8.  src/reporter.py              (logs + CSV)
9.  tests/test_contract.py       ← AVANT writer (TDD)
10. src/writer.py                ← implémenté pour passer les tests
11. enex2obsidian.py             (orchestrateur passif, zéro logique métier)
12. tests/test_smoke.py          ← APRÈS pipeline complet
13. tests/test_limits.py
14. README.md + README.fr.md
```

Ne jamais paralléliser des étapes de cette séquence.
Ne jamais passer à l'étape N+1 sans que l'étape N soit validée.

## Patterns architecturaux hérités de YT Knowledge Extractor

Issus de `YT_EXTRACTOR_RETOUR_EXPERIENCE.md`, applicables directement ici :

- **Flux directionnel** : `ENEX → Parsing → Conversion → Validation → Écriture`. Chaque module a une responsabilité unique. Le module qui lit ne valide pas. Le module qui valide n'écrit pas.
- **Orchestrateur passif** : `enex2obsidian.py` ne contient aucune logique métier. Il appelle les modules dans l'ordre, transmet les données, gère les erreurs terminales. Toute la logique est dans `src/`.
- **Validateur séparé** : le générateur produit, le validateur vérifie. Permet de sauvegarder avec avertissement plutôt que de bloquer.
- **Constitution avant code** : règles non négociables définies en amont, vérifiées par le validateur.

Différence structurelle vs YT Extractor : ce projet est **stateful** au sens où il écrit dans un vault Obsidian que l'utilisateur va faire vivre dans la durée. La constitution doit donc être particulièrement stricte sur la non-destructivité et la traçabilité.

## Conventions de branches

Pour les features significatives :
- Créer une branche : `git checkout -b feature/nom-feature`
- Travailler sur la branche
- Lancer `/review` sur la branche avant de merger
- Merger sur main via PR ou `git merge`

Pour ce projet de migration ponctuelle, le développement principal restera probablement sur main. Branches uniquement si une décision d'architecture significative émerge en cours d'implémentation et nécessite une validation isolée.

## Gestion des documents de spec

Tout document de spec modifié inclut la date ET l'heure de dernière modification dans son header.

Toute spec doit avoir un entête conforme aux règles inviolables : `**Version**`, `**Date**`, `**Auteur**`, `**Statut**`, `**Repo**`.

Toute modification d'un fichier `.md` structurant existant doit incrémenter la version ET la date.

## Signal d'alarme

Si un cas non couvert par les specs est rencontré pendant l'implémentation :

> 🚨 SPEC MANQUANTE : [description précise]

Stopper et attendre une instruction explicite. Ne pas improviser.

**Règle absolue — gap détecté en cours d'implémentation**

Tout gap détecté suit ce flux obligatoire :
1. Signaler : 🚨 SPEC MANQUANTE : [description précise]
2. Stopper — ne pas implémenter
3. Attendre validation dans Claude.ai
4. Recevoir l'instruction de mise à jour des specs
5. Implémenter uniquement après confirmation

Un gap implémenté sans mise à jour des specs préalable est une dette de spec silencieuse — exactement ce que la méthode cherche à prévenir.

## Problèmes transversaux — pattern de gestion

Si pendant l'implémentation d'un prompt, Claude Code identifie des problèmes transversaux (incohérences, duplications, tests manquants), il les SIGNALE en fin de réponse sous "⚠️ Problèmes transversaux identifiés" mais ne les CORRIGE PAS dans le même prompt. Chaque transversal devient une entrée BACKLOG pour un prompt dédié.

Règle : "1 prompt = 1 livrable testable" implique aussi "1 prompt ≠ refactor opportuniste".

## Points sensibles à surveiller pendant l'implémentation

Risques identifiés en co-construction, à garder en tête à chaque prompt :

- **Parsing XML mémoire** : un `.enex` volumineux (centaines de Mo avec pièces jointes embarquées) chargé d'un coup avec `lxml.etree.parse` sature la RAM. Utiliser `lxml.etree.iterparse` en streaming pour traiter les notes une par une et libérer la mémoire au fur et à mesure.
- **Décodage base64 streamé** : ne pas charger une pièce jointe complète en mémoire avant de l'écrire. Décoder par chunks vers le fichier de destination.
- **Encodage des noms de fichiers** : macOS utilise NFD pour les noms de fichiers, Linux NFC. Normaliser systématiquement en NFC avant écriture pour éviter les surprises sur les caractères accentués.
- **iCloud et fichiers en cours de copie** : le vault est dans iCloud Drive. Écrire dans un dossier temporaire local puis déplacer atomiquement vers le vault évite les états intermédiaires synchronisés.
- **Logs horodatés** : tous les noms de fichiers de log incluent un timestamp `YYYY-MM-DD-HHMM` pour permettre plusieurs runs sans écrasement.
