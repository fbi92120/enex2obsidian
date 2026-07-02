# CLAUDE.md — Projet Migration Evernote → Obsidian

**Version** : 1.9
**Date** : 2026-07-01
**Auteur** : François Biller
**Statut** : Étape 14/14 exécutée. Prêt pour migration réelle.
**Repo** : enex2obsidian (local)

Emplacement cible : `~/Projects/enex2obsidian/CLAUDE.md`
Portée : ce projet uniquement.

Ce fichier complète les conventions transversales définies dans :
https://github.com/fbi92120/vibe-coding-governed
(CLAUDE.global.md, CLAUDE.projects.md, METHODE_SPECS_CO-CONSTRUCTION.md)

---

## Ce projet

Outil CLI Python qui convertit les fichiers `.enex` exportés depuis l'app Evernote macOS en notes Markdown organisées dans un vault Obsidian dédié aux notes administratives.

Migration ponctuelle d'un corpus d'environ 1772 notes admin. **Scope définitif : V1 admin uniquement, pas de V2 connaissance prévue** — les carnets de connaissance ne seront pas migrés vers Obsidian.

Repo    : `~/Projects/enex2obsidian/` (local, non publié sur GitHub)
Specs   : SPECS.md V1.8 — lire avant toute implémentation
Contexte évolutif : CONTEXTE-PROJET.md V4.0 — état d'avancement, décisions, leçons
Méthode : METHODE_SPECS_CO-CONSTRUCTION.md (projet vibe-coding-governed)
Retour d'expérience hérité : YT_EXTRACTOR_RETOUR_EXPERIENCE.md

## État courant

Voir CONTEXTE-PROJET.md pour l'historique complet des versions SPECS et l'état d'avancement des étapes. Ce fichier CLAUDE.md décrit les règles opérationnelles stables du projet, pas son état.

## Stack technique

```
Python 3.12 via .venv/ (venv local, PEP 668-compliant — voir setup.sh)
lxml (mode recover=True, huge_tree=True, resolve_entities=False, no_network=True)
                               # parsing XML ENEX tolérant + sécurisé
markdownify                    # conversion XHTML → Markdown
python-slugify                 # slug ASCII
python-dateutil                # parsing dates ISO 8601
pyyaml                         # config.yml + frontmatter YAML
pytest                         # tests unitaires + intégration
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
10. **NFC obligatoire** — tous les noms de fichiers et de dossiers produits par le pipeline sont normalisés en NFC à l'écriture, quelle que soit la forme du source ENEX.

## Comportements aux limites — décisions actées

Voir SPECS.md Bloc 4 pour le tableau complet. Décisions à garder en tête en permanence :

| Situation | Comportement |
|---|---|
| Note avec XHTML mal formé | Log + passage à la note suivante. Le carnet continue. |
| `.enex` introuvable pour carnet listé | Log + passage au carnet suivant. Le batch continue. |
| `--carnet "X"` avec X absent | Erreur terminal explicite (exit ≠ 0). Aucune migration. |
| Pièce jointe > 200 Mo | Log + skip. Mention `[pièce jointe ignorée : taille > N Mo, voir log]` dans le `.md`. |
| Pièce jointe avec base64 corrompu | Log + skip. Mention `[pièce jointe corrompue, voir log]` dans le `.md`. |
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

**Représentativité du fichier de test empirique**

Le test empirique sur fichier réel (étape 3 de la validation) doit utiliser un échantillon **représentatif du corpus cible**. Un test sur un carnet "knowledge" (bookmarks, captures web) ne valide pas le comportement attendu sur un corpus "admin" (PDFs reçus, scans).

Si le test empirique fait apparaître des comportements inattendus (volumes anormaux, patterns non prévus dans SPECS.md), traiter comme un signal de spec manquante — pas comme un succès du module testé.

Leçon extraite de l'étape 6 (attachment_handler V1) : cyber.enex (knowledge) a passé les tests avec 114 PJ traitées, ce qui aurait été catastrophique en migration admin réelle (ressources web parasites). Amendement SPECS.md V1.6 introduit suite à cette découverte.

**Consultation documentaire des formats sources — étape de cadrage**

Pour tout projet qui consomme ou produit un format externe documenté (XML, JSON-Schema, protocole binaire, DTD), la consultation de la documentation officielle du format est une étape de cadrage **avant écriture des specs**, pas une vérification post-implémentation.

Ce qui doit être consulté :
- Documentation officielle de l'éditeur du format (le cas échéant)
- Schémas formels (DTD, XSD, JSON Schema, etc.)
- Au moins une analyse tierce indépendante (projets open source de migration, par exemple)

Ce qui doit être produit :
- Diff explicite entre les champs du format et le scope du projet
- Pour chaque champ hors scope : décision documentée (reporté à version ultérieure, jugé sans pertinence, etc.)
- Aucun champ ne doit être ignoré par défaut sans décision tracée

Leçon extraite du projet enex2obsidian : la consultation documentaire a été faite à mi-parcours (entre étapes 7 et 8 sur 14), pas en cadrage. Conséquence : V1.5 (huge_tree=True) et V1.6 (MIME allowlist) sont des amendements correctifs post-commit. L'amendement V1.7 documente le diff exhaustif et tranche le scope V2.

Pour les prochains projets : intégrer cette étape **avant la rédaction de SPECS.md V1.0**, pas après.

**Inspection visuelle pré-commit pour les outputs visuellement consommés**

Pour tout projet dont l'output est consommé visuellement par un humain dans un outil cible (Obsidian, Word, browser, etc.), l'inspection visuelle dans cet outil est une étape de validation obligatoire — pas un nice-to-have post-livraison.

**Règle** : aucun module qui produit un fichier destiné à être ouvert dans un outil externe n'est considéré comme validé tant qu'un échantillon de sa sortie n'a pas été ouvert dans cet outil et inspecté visuellement.

**Pourquoi** : les tests automatisés et les tests empiriques sur fichiers de référence vérifient la structure et la complétude des outputs, mais ne révèlent pas les bugs de rendu propres à l'outil cible. Un fichier `.md` peut être structurellement parfait, passer tous les tests, mais avoir un comportement cassé dans Obsidian (résolution de liens, encodage, format d'embed).

**Couverture des accents** : l'échantillon inspecté doit contenir des caractères Unicode non-ASCII (accents français, caractères composés). Les bugs de normalisation Unicode (NFC/NFD) sont systématiquement masqués par un échantillon purement ASCII et ne ressortent que sur du contenu accentué.

**Modules concernés par l'inspection visuelle V1** : `writer` (sortie .md vers Obsidian).

Checklist d'inspection visuelle Obsidian pour ce projet :
1. Ouvrir le vault produit dans Obsidian
2. Inspecter 5-10 notes au hasard (frontmatter rendu correctement, contenu Markdown lisible)
3. Cliquer sur **au moins 3 liens vers pièces jointes**, dont au moins 1 avec un nom accentué
4. Vérifier l'affichage des embeds (images, PDFs) en mode lecture
5. Vérifier la présence des tags dans la palette de tags Obsidian
6. Vérifier qu'aucun fichier vide "X.pdf 1", "X.pdf 2" n'apparaît dans la sidebar attachments (signal de lien cassé)

**Leçon extraite de l'étape 11** : `cyber.enex` a été migré, le test empirique a passé (23 notes → 23 `.md`, 113 pièces jointes copiées), mais l'inspection visuelle dans Obsidian a révélé que les liens vers les ~5 PDFs au nom accentué étaient cassés (création de fichiers vides au clic). Amendement V1.8 introduit suite à cette découverte.

Pour les prochains projets : prévoir cette étape **avant** de considérer une étape comme validée et commitée, pas après.

**Tests d'intégration révélant des violations Constitution**

*Nouvelle règle V1.8 — leçon PROMPT-13.*

Un test d'intégration (smoke, limits) qui révèle qu'un comportement du pipeline viole une règle de la Constitution (Bloc 0 des SPECS) doit être traité comme un **bloquant pré-migration**, pas comme une adaptation acceptable du test.

Exemples de violations Constitution détectables par test :
- Règle 2 (aucune perte silencieuse) : une note en erreur ne produit aucune ligne dans le CSV d'erreurs
- Règle 5 (idempotence) : un 2e run produit un état différent du 1er
- Règle 8 (pas d'écrasement implicite) : `.md` existant écrasé sans `--force`
- Règle 9 (pas de path traversal) : un fichier est écrit en dehors de `vault_path`

Un test qui découvre ce type de violation doit :
1. Émettre 🚨 SPEC MANQUANTE (cf. section "Signal d'alarme" ci-dessous)
2. Ne pas être commité tant que la violation n'est pas corrigée dans le code de production
3. Sauf `pytest.xfail(strict=True)` explicite avec entrée BACKLOG.md sous "Importants — à traiter avant migration réelle"

**Leçon PROMPT-13** : à l'étape 13, Claude Code a rencontré 6 divergences entre code et SPECS (dont 2 violations Constitution règle 2). Il a initialement adapté les tests au comportement réel plutôt que de signaler et stopper. La détection s'est faite par question subsidiaire pré-commit ("as-tu fait des choix d'adaptation ?"), pas par rituel formalisé. La règle "Récap structuré pré-commit obligatoire" plus bas dans ce fichier transforme cette parade en discipline systématique.

## Carnet de référence pour les tests

Le test smoke s'exécute sur une fixture versionnée dans le repo :

```
tests/fixtures/testmigration.enex   # 7 notes synthétiques sans données personnelles
```

Cette fixture est reproductible et diffusable. Elle est référencée directement dans le code de test, pas via variable d'environnement.

Pour un test empirique sur un vrai carnet plus volumineux, la variable d'environnement `ENEX_REFERENCE_FILE` reste disponible :

```bash
export ENEX_REFERENCE_FILE=~/Migration-Evernote/exports-enex/[nom-carnet].enex
```

Recommandation pour le choix d'un carnet réel : petit carnet (10-30 notes), représentatif du corpus cible (admin, pas knowledge), avec au moins une note texte, une note avec PDF, une note avec image, une note dégradée.

Un `.enex` réel n'est JAMAIS versionné dans le repo (risque de fuite de données personnelles) — seule la fixture synthétique l'est.

Les tests de contrat (CT-XX dans SPECS.md) utilisent des fragments XML inlinés dans le code de test, indépendants de toute fixture.

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
14. README.md
```

Ne jamais paralléliser des étapes de cette séquence.
Ne jamais passer à l'étape N+1 sans que l'étape N soit validée.

Cycles de correction acceptés : `12 → 12-AUDIT → 12-FIX → 13 → 13-FIX → 13-AUDIT` etc. Chaque cycle est un livrable testable en soi, mais reste rattaché à son étape macro.

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

Pour ce projet de migration ponctuelle, le développement principal reste sur `main`. Branches uniquement si une décision d'architecture significative émerge en cours d'implémentation et nécessite une validation isolée.

## Gestion des documents de spec

Tout document de spec modifié inclut la date ET l'heure de dernière modification dans son header.

Toute spec doit avoir un entête conforme aux règles inviolables : `**Version**`, `**Date**`, `**Auteur**`, `**Statut**`, `**Repo**`.

Toute modification d'un fichier `.md` structurant existant doit incrémenter la version ET la date.

Le fichier `BACKLOG.md` à la racine du repo matérialise la dette technique connue mais non traitée. Il est mis à jour à chaque prompt qui identifie une nouvelle dette ou en résout une.

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

**Cas particulier V1.8 — divergence code de production vs SPECS révélée par un test**

Si pendant l'écriture d'un test, Claude Code découvre que le code de production actuel diverge de ce que les SPECS demandent (par exemple : SPECS attendent un exit code non-zéro sur une erreur, le code retourne 0 ; SPECS attendent un message précis, le code produit une variante) :

**Comportement interdit** : ajuster les assertions du test au comportement réel du code. C'est de l'adaptation silencieuse — le test valide un bug comme s'il était une feature.

**Comportement obligatoire** :
1. Signaler immédiatement : `🚨 SPEC MANQUANTE : divergence code/SPECS révélée — [description précise avec référence SPECS Bloc/ligne]`
2. Stopper l'écriture du test concerné
3. Attendre l'arbitrage humain (via session Claude.ai en tandem) : soit corriger le code pour se conformer aux SPECS, soit modifier les SPECS pour acter la divergence, soit `pytest.xfail(strict=True)` explicite du test avec référence BACKLOG.md.

**Cas de plusieurs divergences dans la même session** : signaler chacune séparément, ne pas les agréger en un seul signal générique. L'humain a besoin de chaque cas pour arbitrer proprement.

## Problèmes transversaux — pattern de gestion

Si pendant l'implémentation d'un prompt, Claude Code identifie des problèmes transversaux (incohérences, duplications, tests manquants), il les SIGNALE en fin de réponse sous "⚠️ Problèmes transversaux identifiés" mais ne les CORRIGE PAS dans le même prompt. Chaque transversal devient une entrée BACKLOG pour un prompt dédié.

Règle : "1 prompt = 1 livrable testable" implique aussi "1 prompt ≠ refactor opportuniste".

## Récap structuré pré-commit obligatoire

*Nouvelle règle V1.8 — parade méthodologique à la dérive silencieuse.*

Toute session Claude Code qui produit des modifications de code doit se terminer par un récap structuré **avant** de demander l'autorisation de commit. Le récap distingue explicitement :

1. **Modifications code production** : fichiers et fonctions touchés dans `src/` et `enex2obsidian.py`, avec référence SPECS Bloc/règle Constitution si applicable.
2. **Modifications tests** : tests dont les assertions ont changé, avec justification (alignement SPECS, correction bug, renforcement).
3. **Fichiers nouveaux ou renommés** : fixtures, documentation, scripts, etc.
4. **Signaux 🚨 SPEC MANQUANTE émis** : liste explicite. Si aucun, l'affirmer : "Aucun signal SPEC MANQUANTE émis pendant cette session."
5. **Découvertes non traitées** : tout bug, incohérence, ou trou de spec identifié en lisant le code mais non corrigé dans le scope du prompt. À reporter à BACKLOG.md.
6. **Adaptations vs prompt initial** : tout choix d'implémentation qui diverge de ce que le prompt prescrivait littéralement (nom de fichier, structure, signature). À justifier en une ligne.
7. **Décompte final des tests** : `pytest` complet, décompte passants / failed / skipped / xfail.

Ce récap est **obligatoire** pour :
- Prompts touchant du code de production
- Prompts créant des tests d'intégration
- Prompts modifiant des specs ou de la documentation structurante

Il est **optionnel mais recommandé** pour les prompts triviaux (renommage, correction de typo, ajout de docstring).

**Sans ce récap, l'autorisation de commit ne peut pas être donnée.** Si Claude Code demande à committer sans avoir produit le récap, l'humain (ou une session Claude.ai supervisante) doit refuser et redemander le récap.

**Origine de la règle** : étape 13 (PROMPT-13). Claude Code a fait 6 adaptations silencieuses (assertions ajustées au code réel divergent des SPECS, sans émission des signaux 🚨 SPEC MANQUANTE prévus). La détection s'est faite par question subsidiaire ad hoc pré-commit ("as-tu fait des choix d'adaptation ?"), pas par rituel formalisé. Cette règle transforme la parade en discipline systématique — la méthode ne tient plus sur la bonne foi mais sur un rituel imposé.

## Points sensibles à surveiller pendant l'implémentation

Risques identifiés en co-construction, à garder en tête à chaque prompt :

- **Parsing XML mémoire** : un `.enex` volumineux (centaines de Mo avec pièces jointes embarquées) chargé d'un coup avec `lxml.etree.parse` sature la RAM. Utiliser `lxml.etree.iterparse` en streaming pour traiter les notes une par une et libérer la mémoire au fur et à mesure.
- **Décodage base64 streamé** : ne pas charger une pièce jointe complète en mémoire avant de l'écrire. Décoder par chunks vers le fichier de destination.
- **Encodage des noms de fichiers** : macOS utilise NFD pour les noms de fichiers, Linux NFC. Normaliser systématiquement en NFC avant écriture pour éviter les surprises sur les caractères accentués. Constitution règle 10.
- **iCloud et fichiers en cours de copie** : le vault est dans iCloud Drive. Écrire dans un dossier temporaire local puis déplacer atomiquement vers le vault évite les états intermédiaires synchronisés.
- **Logs horodatés** : tous les noms de fichiers de log incluent un timestamp `YYYY-MM-DD-HHMM` pour permettre plusieurs runs sans écrasement.
- **Divergences code/SPECS pendant les tests** : cf. règle V1.8 sous "Signal d'alarme". Un test qui adapte silencieusement ses assertions au comportement réel divergent des SPECS est une dette de contrôle silencieuse — traitement obligatoire par signal 🚨 SPEC MANQUANTE.
