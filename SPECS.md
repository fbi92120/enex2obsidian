# SPECS.md — Migration Evernote → Obsidian (carnets admin)

**Version** : 1.8
**Date** : 2026-06-30
**Auteur** : François Biller
**Statut** : V1.8 — Normalisation NFC obligatoire + format embed pour PDFs (bug bloquant découvert en inspection Obsidian)
**Repo** : à créer

---

## Bloc 0 — Constitution

*Règles non négociables. Aucune exception, aucune déviation dans le code.*

1. **Aucun arrêt du batch sur erreur** — toute erreur (parsing XML, décodage base64, écriture disque) est tracée dans un log et le convertisseur continue. Le batch s'arrête uniquement quand toutes les notes de tous les carnets demandés ont été tentées.
2. **Aucune perte silencieuse** — toute note du `.enex` produit soit un `.md` dans le vault, soit une ligne explicite dans le log d'erreurs avec son `evernote_guid` et la cause. Jamais d'omission tacite.
3. **Aucune pièce jointe silencieusement ignorée** — toute pièce jointe d'une note traitée est soit copiée dans `attachments/`, soit signalée dans le log d'erreurs avec une cause explicite (`size_exceeded`, `corrupted_base64`, `mime_excluded`, `traversal_blocked`, `write_error`). Jamais d'omission tacite. Le filtrage par allowlist MIME (cf. Bloc 3 "Filtrage MIME") fait partie des exclusions autorisées tant qu'il est tracé dans le rapport erreurs.
4. **Aucune métadonnée inventée** — si une date, un tag ou un GUID est absent du `.enex`, le frontmatter porte une valeur vide ou nulle. Jamais une valeur fabriquée.
5. **Idempotence** — relancer le convertisseur sur le même périmètre doit produire le même résultat (modulo les logs horodatés). Pas d'effet cumulatif.
6. **Non-destructivité du source** — le convertisseur n'écrit jamais dans le dossier des `.enex`. Il ne les modifie ni les supprime.
7. **Pas de LLM dans le pipeline** — la transformation est purement déterministe. Aucune décision runtime ne fait appel à un modèle de langage.
8. **Pas d'écrasement implicite** — un `.md` cible déjà existant entraîne un skip avec log. L'écrasement nécessite le flag `--force` explicite.
9. **Pas de path traversal** — toute écriture est vérifiée comme étant strictement sous le vault cible. Un nom de pièce jointe contenant `..` ou des séparateurs ne peut sortir du dossier de destination.
10. **Normalisation NFC obligatoire** — tous les noms de fichiers écrits dans le vault Obsidian (pièces jointes, fichiers `.md`) et tous les liens générés vers ces fichiers sont normalisés en Unicode NFC avant écriture. Les noms en NFD (forme décomposée) sont systématiquement convertis en NFC (forme composée) à 3 points du pipeline : `filename_normalizer.sanitize_attachment_name`, `attachment_handler._resolve_filename`, et `writer._resolve_placeholders`. Cette défense en profondeur garantit la résolution correcte des liens dans Obsidian qui normalise ses recherches en NFC.

---

## Bloc 1 — Vue d'ensemble

### Objectif

Outil CLI Python qui convertit les fichiers `.enex` exportés depuis l'app Evernote macOS en notes Markdown organisées dans un vault Obsidian dédié aux notes administratives.

Conçu pour un usage personnel ponctuel — migration unique d'un corpus d'environ 1600 notes admin réparties sur plusieurs carnets.

### Définitions

- **ENEX** : format d'export Evernote (XML), un fichier par carnet, contenant le texte des notes en XHTML et les pièces jointes encodées en base64.
- **Vault admin** : vault Obsidian distinct du vault de connaissance, dédié aux notes administratives migrées depuis Evernote.
- **Carnet** : notebook Evernote. Dans le vault de destination, un carnet devient un dossier de premier niveau.
- **Note** : note Evernote individuelle. Dans le vault de destination, une note devient un fichier `.md`.
- **Pièce jointe** : fichier embarqué dans une note Evernote (PDF, Word, Excel, image, autre). Dans le vault, copiée dans le sous-dossier `attachments/` du carnet.
- **Frontmatter** : bloc YAML en tête du `.md` contenant les métadonnées (date, tags, GUID, etc.).
- **Slug** : version ASCII d'un titre, utilisée comme nom de fichier ou de dossier. Espaces remplacés par tirets, accents enlevés, ponctuation supprimée.

### Périmètre MVP (V1)

- Conversion ENEX → Markdown Obsidian pour les carnets admin uniquement
- Acquisition des `.enex` : export manuel depuis l'app Evernote macOS (clic droit sur carnet → Export Notebook)
- Sélection des carnets à traiter via fichier texte `carnets-a-migrer.txt`
- Interface CLI : `enex2obsidian [--carnets FICHIER] [--source DOSSIER] [--vault DOSSIER] [--carnet NOM] [--force] [--dry-run] [--log-dir DOSSIER]`
- Conversion XHTML → Markdown en mode best-effort
- Préservation intégrale des métadonnées Evernote dans le frontmatter YAML
- Copie de toutes les pièces jointes (tous types confondus)
- Logging structuré : log d'exécution + rapport CSV des collisions + rapport CSV des erreurs
- Configuration via `config.yml` — aucun chemin hardcodé

### Hors scope V1

- Migration des notes de connaissance (~6500 notes, projet séparé — dépendance Wiki LLM)
- Reconstruction des liens internes Evernote entre notes (perte acceptée — usage marginal côté utilisateur)
- Hiérarchie de tags Obsidian (sans objet — pas de tags hiérarchisés dans le corpus source)
- Recherche dans le contenu des pièces jointes (besoin Obsidian post-migration, traité par plugins type Omnisearch)
- LLM dans le pipeline de conversion (rejeté en co-construction — risque de dérive de qualité incompatible avec la fidélité de migration)
- Synchronisation continue Evernote ↔ Obsidian (migration ponctuelle, pas un pont vivant)
- API Evernote (export manuel uniquement, pas de token développeur, pas de réseau)
- Interface graphique ou web
- Restauration d'une migration antérieure ou rollback automatique


#### Champs ENEX identifiés et reportés V2

Une vérification documentaire à mi-parcours (entre étapes 7 et 8) a identifié des champs du format ENEX présents dans la DTD `enml2.dtd` et la documentation Evernote, mais non implémentés en V1. Le report en V2 est une décision consciente, non un oubli :

**Champs de `<note-attributes>` reportés V2 :**

| Champ | Usage Evernote | Justification du report |
|---|---|---|
| `subject-date` | Date "sujet" distincte de `created`/`updated` (ex. date d'une facture vs date d'ajout) | Pas d'usage admin avéré chez l'utilisateur en V1 |
| `author` | Auteur de la note | Pas d'usage admin avéré |
| `source` | Origine logique (`web.clip`, `desktop.mac`, etc.) | Information de contexte non critique en V1 |
| `source-application` | Application d'origine | Idem |
| `source-type` | Type de source | Idem |
| `latitude` / `longitude` / `altitude` | Géolocalisation de la note | Sans pertinence pour usage admin |
| `place-name` | Nom de lieu | Idem |
| `reminder-order` / `reminder-time` / `reminder-done-time` / `reminder-time-zone` | Système de rappels/tâches Evernote | Pas d'usage admin avéré (utilisateur ne gère pas ses échéances admin via Evernote) |

**Champs de `<resource-attributes>` reportés V2 :**

| Champ | Usage Evernote | Justification du report |
|---|---|---|
| `attachment` (flag boolean) | Indique vraie pièce jointe vs inline | Sans impact sur la migration — toutes les pièces jointes sont traitées de la même manière |
| `timestamp` | Date associée à la ressource (souvent EXIF) | Non critique pour usage admin |
| `latitude` / `longitude` / `altitude` | Géolocalisation de la pièce jointe | Sans pertinence |

**Champs de `<resource>` reportés V2 :**

| Champ | Usage Evernote | Justification du report |
|---|---|---|
| `width` / `height` | Dimensions d'image | Le rendu Obsidian via `![[image]]` ne requiert pas ces dimensions ; à reconsidérer si V2 a un besoin de rendu fidèle |
| `duration` | Durée audio/vidéo | Hors scope V1 (audio rare en admin) |
| `recognition` | Données OCR Evernote | Obsidian utilise ses propres mécanismes d'indexation (plugins type Omnisearch) |
| `alternate-data` | Variante du binaire | Cas marginal, pas d'usage avéré |

**À reconsidérer pour V2 (carnets connaissance, ~6500 notes) :**

- `source-url` est **déjà couvert en V1** (`metadata_extractor.NoteMetadata.source_url`, extrait depuis `note-attributes/source-url`). Vérifié explicitement à l'amendement V1.7.
- `author` pourrait gagner en pertinence sur les carnets de connaissance (articles d'auteurs identifiés).
- `subject-date` pourrait devenir critique si les notes de connaissance contiennent des références bibliographiques.
- `recognition` (OCR) pourrait être utile pour la recherche dans les vieux scans, mais probablement remplacé par les plugins Obsidian.

Cette liste est exhaustive au regard de la vérification documentaire menée. Tout champ découvert ultérieurement sera traité comme un signal de spec manquante (signal 🚨), pas comme une omission silencieuse.

### Évolutions prévues

- **V2 — Migration des carnets de connaissance** : même outil, périmètre élargi aux ~6500 notes restantes. Le code de V1 doit le permettre sans modification — il suffit d'ajouter les noms de carnets dans `carnets-a-migrer.txt`.
- **V3 — Audit post-migration** : passer un échantillon de `.md` produits à un LLM (en outil annexe, hors pipeline) pour vérifier la fidélité de conversion. Outil de QA séparé.

---

## Bloc 2 — Architecture technique

### Stack

```
Python 3.12 via .venv/ (venv local, PEP 668-compliant)
lxml (iterparse, resolve_entities=False, no_network=True, huge_tree=True, recover=True)
                               # streaming sécurisé (XXE désactivé) ; huge_tree=True requis
                               # car les pièces jointes ENEX (base64) génèrent des nodes >10 Mo
markdownify                    # conversion XHTML → Markdown
python-slugify                 # génération slug ASCII depuis titres
python-dateutil                # parsing dates ISO 8601 Evernote
pyyaml                         # lecture config.yml + écriture frontmatter YAML
```

Aucune dépendance réseau. Aucun token, aucune clé API.

Choix de `lxml` plutôt que `xml.etree.ElementTree` : performance sur les `.enex` volumineux (corpus de 8000+ notes attendu en V2), mode `recover=True` natif pour parsing tolérant (cohérent avec la constitution règle 1 — aucun arrêt sur erreur). Configuration explicite `resolve_entities=False, no_network=True` pour bloquer les attaques XXE à l'entrée du pipeline.

### Structure du repo

```
evernote-to-obsidian/
├── README.md                        # EN — installation + usage
├── README.fr.md                     # FR — même contenu
├── SPECS.md                         # ce document
├── CLAUDE.md                        # instructions Claude Code projet
├── config.yml.example               # template configuration utilisateur
├── carnets-a-migrer.txt.example     # template liste carnets
├── .gitignore                       # config.yml, carnets-a-migrer.txt, logs/, output/
├── enex2obsidian.py                 # point d'entrée CLI — orchestration uniquement
├── requirements.txt
├── src/
│   ├── enex_parser.py               # parsing XML ENEX, extraction notes
│   ├── metadata_extractor.py        # extraction métadonnées Evernote → frontmatter
│   ├── content_converter.py         # conversion XHTML → Markdown (best-effort)
│   ├── attachment_handler.py        # décodage base64, copie disque, collisions
│   ├── filename_normalizer.py       # slug ASCII, sanitization, anti-traversal
│   ├── notebook_selector.py         # parsing carnets-a-migrer.txt
│   ├── writer.py                    # écriture .md + arborescence vault
│   └── reporter.py                  # logs exécution + rapports CSV
└── tests/
    ├── test_contract.py             # validation contrats modules (fragments XML inline)
    ├── test_smoke.py                # carnet réel via ENEX_REFERENCE_FILE
    └── test_limits.py               # comportements aux limites (fixtures inline)
```

### Configuration utilisateur

`config.yml` (copié depuis `config.yml.example`) :

```yaml
# Dossier contenant les fichiers .enex exportés depuis l'app Evernote
source_directory: ~/Migration-Evernote/exports-enex

# Vault Obsidian de destination (admin)
vault_path: ~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Vault-Admin

# Dossier des logs et rapports CSV (hors vault)
log_directory: ~/Migration-Evernote/logs

# Fichier listant les carnets à migrer
notebook_list: ~/Migration-Evernote/carnets-a-migrer.txt

# Plafond de taille d'une pièce jointe (au-delà : log + skip)
# Valeur par défaut : 200 Mo — suffisant pour PDFs, Word, Excel, images standard
# À augmenter uniquement si le corpus contient des vidéos ou archives volumineuses
attachment_size_limit_mb: 200

# Allowlist des types MIME à migrer (toute pièce jointe avec un MIME absent
# de cette liste est ignorée et tracée dans le rapport erreurs avec cause "mime_excluded")
# Filtrage actif depuis V1.6 — protège contre les ressources annexes de captures web
# (CSS, fonts, icônes web) qui pollueraient le vault.
allowed_mime_types:
  # Documents bureautiques
  - application/pdf
  - application/msword
  - application/vnd.openxmlformats-officedocument.wordprocessingml.document
  - application/vnd.ms-excel
  - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
  - application/vnd.ms-powerpoint
  - application/vnd.openxmlformats-officedocument.presentationml.presentation
  - application/vnd.oasis.opendocument.text
  - application/vnd.oasis.opendocument.spreadsheet
  - application/vnd.oasis.opendocument.presentation
  - application/rtf
  - text/rtf
  - text/plain
  - text/csv
  # Images
  - image/jpeg
  - image/png
  - image/heic
  - image/heif
  - image/tiff
  # Email
  - message/rfc822
  - application/vnd.ms-outlook
  # Archives
  - application/zip
  - application/x-7z-compressed
  - application/x-rar-compressed
  # Audio
  - audio/mpeg
  - audio/mp4
  - audio/wav

# Comportement si un fichier .md cible existe déjà
# false = skip + log (défaut sécuritaire)
# true  = écrasement (réservé à --force CLI, jamais en config)
force_overwrite: false
```

`carnets-a-migrer.txt` (copié depuis `carnets-a-migrer.txt.example`) :

```
# Liste des carnets Evernote à migrer.
# Un nom de carnet par ligne, tel qu'il apparaît dans Evernote.
# Lignes commençant par # : commentaires, ignorées.
# Lignes vides : ignorées.

# Carnets admin — vague 1
Comptabilité 2024
Bail appartement
Factures EDF

# Carnets admin — vague 2 (à migrer plus tard)
# Impôts 2023
# Mutuelle
```

### Interface CLI

```
enex2obsidian [OPTIONS]

Options :
  --carnets FICHIER       Fichier liste des carnets à migrer
                          (défaut : valeur de notebook_list dans config.yml)
  --source DOSSIER        Dossier contenant les .enex exportés
                          (défaut : valeur de source_directory dans config.yml)
  --vault DOSSIER         Vault Obsidian de destination
                          (défaut : valeur de vault_path dans config.yml)
  --carnet NOM            Migre un seul carnet (ignore --carnets)
                          Le nom doit correspondre exactement au nom Evernote
  --force                 Écrase les .md cibles existants (défaut : skip + log)
  --dry-run               Liste ce qui serait migré sans rien écrire ni copier
  --log-dir DOSSIER       Dossier des logs et rapports CSV
                          (défaut : valeur de log_directory dans config.yml)
  -h, --help              Affiche cette aide
```

Exemples d'usage :

```bash
enex2obsidian --dry-run                       # voir le plan complet
enex2obsidian                                 # migre tous les carnets du txt
enex2obsidian --carnet "Comptabilité 2024"    # un seul carnet
enex2obsidian --carnet "Bail" --force         # rejoue en écrasant
```

### Flux de traitement

```
Phase 1 — Initialisation
1.  Chargement config.yml
2.  Résolution des chemins (priorité : flags CLI > config.yml)
3.  Validation existence et accessibilité de source_directory, vault_path, log_directory
4.  Création du dossier log_directory si absent
5.  Création du fichier log d'exécution : migration-YYYY-MM-DD-HHMM.log
6.  Création des fichiers rapports : collisions-YYYY-MM-DD-HHMM.csv et errors-YYYY-MM-DD-HHMM.csv

Phase 2 — Sélection des carnets
7.  Lecture du fichier carnets-a-migrer.txt (ou flag --carnet)
8.  Filtrage des lignes (commentaires #, lignes vides)
9.  Pour chaque nom de carnet : recherche du .enex correspondant dans source_directory
    Matching tolérant aux accents et espaces (normalisation Unicode NFC)
10. Si --dry-run : affichage du plan et arrêt après cette phase

Phase 3 — Traitement par carnet
Pour chaque carnet sélectionné :
11. Création du dossier carnet dans le vault (slug ASCII du nom de carnet)
12. Création du sous-dossier attachments/ dans le dossier carnet
13. Parsing du .enex (lxml ou ElementTree, parsing tolérant aux erreurs)
14. Pour chaque <note> du XML :
    a. Extraction des métadonnées (title, created, updated, tags, source-url, guid)
    b. Conversion du contenu XHTML en Markdown (best-effort)
    c. Pour chaque <resource> (pièce jointe) :
       - Décodage base64
       - Détermination du nom de fichier (priorité : <file-name> du <resource-attributes>)
       - Sanitization du nom (anti-traversal, caractères interdits FS)
       - Gestion collision (suffix -2, -3, ... + log CSV)
       - Vérification taille vs attachment_size_limit_mb
       - Écriture dans [vault]/[carnet]/attachments/
       - Mémorisation de la correspondance hash <en-media> → nom final
    d. Substitution des balises <en-media> dans le Markdown
       - Image (.png, .jpg, .jpeg, .gif, .webp, .heic, .heif, .tiff) → embed Obsidian ![[attachments/nom.ext]]
       - PDF (.pdf) → embed Obsidian ![[attachments/nom.pdf]]
       - Autre → lien simple [nom.ext](attachments/nom.ext)
    e. Construction du frontmatter YAML
    f. Construction du chemin cible : [vault]/[carnet]/[slug-titre].md
    g. Gestion collision de nom de .md (suffix -2, -3, ... + log CSV)
    h. Vérification existence .md cible :
       - Si existe et pas de --force : skip + log
       - Si existe et --force : écrasement
       - Si n'existe pas : écriture
    i. Écriture frontmatter + contenu converti + références pièces jointes
15. Compteurs : N notes en entrée, X succès, Y erreurs partielles, Z erreurs totales

Phase 4 — Finalisation
16. Écriture du résumé en fin du fichier log d'exécution
17. Fermeture des fichiers CSV
18. Affichage du résumé terminal : chemin des logs, compteurs globaux
```

### Structure du vault produit

```
Vault-Admin/
├── Comptabilite-2024/                            ← slug ASCII du carnet
│   ├── Facture-EDF-mars-2024.md
│   ├── Facture-EDF-avril-2024.md
│   ├── Releve-bancaire-Q1.md
│   └── attachments/
│       ├── Facture EDF mars 2024.pdf             ← nom d'origine conservé
│       ├── Facture EDF avril 2024.pdf
│       └── Relevé Q1.pdf
├── Bail-appartement/
│   ├── Bail-signe.md
│   └── attachments/
│       ├── Bail signé.pdf
│       └── État des lieux.pdf
└── ...
```

Le vault ne contient aucun fichier de log ni de rapport. Le matériel de migration est strictement séparé.

### Structure du matériel transitoire

```
~/Migration-Evernote/
├── exports-enex/                                 ← .enex bruts depuis l'app Evernote
│   ├── Comptabilité 2024.enex
│   ├── Bail appartement.enex
│   └── ...
├── logs/
│   ├── migration-2026-06-29-1430.log             ← log d'exécution
│   ├── collisions-2026-06-29-1430.csv            ← rapport collisions
│   └── errors-2026-06-29-1430.csv               ← rapport erreurs
├── carnets-a-migrer.txt                          ← liste des carnets à traiter
└── config.yml                                    ← config locale
```

Ce dossier reste hors iCloud, hors vault. Supprimable après validation de la migration.

---

## Bloc 3 — Format de sortie

### Frontmatter YAML

Champs obligatoires en tête de chaque `.md` :

```yaml
---
title: "Titre Evernote conservé verbatim (accents et ponctuation autorisés)"
created: 2024-03-15T09:23:00
updated: 2024-03-15T09:25:00
tags:
  - facture
  - edf
  - 2024
source_url: ""
evernote_notebook: "Comptabilité 2024"
evernote_guid: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
---
```

Règles de remplissage :

- `title` : nom de la note Evernote verbatim. Quotes YAML requises si le titre contient `:`, `"`, `'` ou commence par un caractère spécial YAML.
- `created` / `updated` : format ISO 8601 sans timezone (UTC implicite, comme dans l'ENEX). Si absent du `.enex` : chaîne vide `""`.
- `tags` : liste plate, sans hiérarchie. Chaque tag normalisé : minuscules, accents enlevés, espaces remplacés par tirets, caractères non-ASCII enlevés. Liste vide `[]` si aucun tag.
- `source_url` : URL d'origine si la note était un web clip. Chaîne vide `""` sinon.
- `evernote_notebook` : nom du carnet Evernote source, verbatim (accents et espaces conservés).
- `evernote_guid` : identifiant unique Evernote, conservé tel quel.

### Conversion XHTML → Markdown (best-effort)

Le contenu d'une note Evernote est du XHTML. La conversion en Markdown s'effectue avec `markdownify` configuré comme suit :

Préservé :
- Paragraphes, sauts de ligne
- Listes à puces et numérotées (`<ul>`, `<ol>`, `<li>`)
- Listes imbriquées (sur 1 niveau, au-delà aplaties)
- Liens (`<a href>`)
- Gras (`<b>`, `<strong>`) et italique (`<i>`, `<em>`)
- Citations (`<blockquote>`)
- Code inline et blocs de code
- Tableaux simples (`<table>` sans cellules fusionnées)
- Cases à cocher Evernote (`<en-todo>`) → `- [ ]` non cochée, `- [x]` cochée

Aplati ou ignoré :
- Couleurs de texte et de fond
- Polices et tailles personnalisées
- Indentation décorative
- Cellules de tableau fusionnées (le tableau est rendu sans fusion, contenu préservé)
- Balises HTML inconnues (contenu textuel préservé, balise enlevée)

Pièces jointes : la balise `<en-media hash="...">` est remplacée par :
- Pour les images (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.heic`, `.heif`, `.tiff`) : `![[attachments/nom-fichier.ext]]` (embed Obsidian, chemin relatif explicite pour résolution déterministe)
- Pour les PDFs (`.pdf`) : `![[attachments/nom-fichier.pdf]]` (embed Obsidian, affichage inline du visualiseur PDF)
- Pour les autres types (docx, xlsx, zip, audio, etc.) : `[nom-fichier.ext](attachments/nom-fichier.ext)` (lien Markdown classique, ouvre l'application système au clic)

**Important — normalisation NFC** : le nom de fichier utilisé dans le wikilink ou le lien est systématiquement normalisé en Unicode NFC avant inclusion. Cela garantit la résolution correcte par Obsidian qui compare les noms en NFC.

**Important — chemin relatif dans les embeds** : le chemin `attachments/` est inclus dans le wikilink (forme `![[attachments/fichier.pdf]]`) plutôt que de compter sur l'index global d'Obsidian (forme `![[fichier.pdf]]`). C'est plus déterministe en cas de doublons de noms entre carnets.

### Normalisation Unicode

Tous les noms de fichiers écrits dans le vault Obsidian (pièces jointes dans `attachments/` et fichiers `.md` à la racine du carnet) sont normalisés en Unicode NFC (Normalization Form C — Canonical Composition) avant écriture.

**Pourquoi** : macOS APFS stocke les noms de fichiers en NFD (forme décomposée : `e` + accent combinant), mais Obsidian normalise ses recherches en NFC (forme composée : `é` comme un seul codepoint). Sans normalisation explicite, les fichiers écrits en NFD depuis l'ENEX deviennent introuvables par Obsidian quand un lien les référence.

**Points de normalisation** (défense en profondeur, 3 niveaux) :

1. **`filename_normalizer.sanitize_attachment_name`** — normalisation NFC du nom de pièce jointe à la sortie de la sanitization. Tout le pipeline aval reçoit du NFC.

2. **`attachment_handler._resolve_filename`** — normalisation NFC en sortie, même sur le fallback `attachment-{hash[:8]}.{ext}`. Couvre le cas où le sanitizer aurait été contourné.

3. **`writer._resolve_placeholders`** — normalisation NFC sur le `final_filename` reçu de l'`AttachmentResult` avant utilisation dans le lien généré. Couvre le cas d'un `AttachmentResult` venu d'un test ou d'un état sérialisé non normalisé.

4. **`writer` (slug `.md`)** — normalisation NFC sur le slug du nom de fichier `.md` produit par `slug_for_note`. `python-slugify` produit habituellement du NFC mais ce n'est pas garanti par contrat.

**Comparaison stricte des collisions** : la gestion des collisions intra-session (`_written_filenames`) compare les noms après normalisation NFC. Deux noms NFC et NFD du même contenu sont considérés comme identiques.

**Pas de normalisation côté `enex_parser`** : ce module reste le point de lecture brut de l'ENEX. La normalisation est une règle de sortie filesystem, pas de parsing.

### Gestion des collisions

**Collision de pièce jointe** (deux notes du même carnet ont une pièce jointe nommée `scan.pdf`) :

- Première copiée : `scan.pdf`
- Deuxième : `scan-2.pdf`
- Troisième : `scan-3.pdf`
- ...

Chaque collision est enregistrée dans `collisions-YYYY-MM-DD-HHMM.csv` :

```csv
timestamp,carnet,note_titre,note_guid,fichier_original,fichier_final
2026-06-29T14:32:18,Comptabilité 2024,Facture EDF mars,a1b2c3d4-...,scan.pdf,scan.pdf
2026-06-29T14:32:19,Comptabilité 2024,Facture EDF avril,b2c3d4e5-...,scan.pdf,scan-2.pdf
```

**Collision de nom de fichier `.md`** (deux notes du même carnet ont le même titre) :

- Premier `.md` : `Facture-EDF.md`
- Deuxième : `Facture-EDF-2.md`
- Troisième : `Facture-EDF-3.md`

Loggé dans le même fichier CSV avec une colonne supplémentaire `type` (ou un CSV séparé `collisions-md.csv`, à trancher à l'implémentation).

### Normalisation des noms

| Élément | Règle |
|---|---|
| Nom de dossier carnet | Slug ASCII : casse conservée, accents enlevés, espaces → tirets, ponctuation enlevée |
| Nom de fichier `.md` | Slug ASCII (même règle que le dossier carnet) |
| Nom de pièce jointe | Conservé verbatim (accents et espaces autorisés) |
| Titre dans frontmatter | Conservé verbatim |
| Tag | Normalisé : minuscules, accents enlevés, espaces → tirets, caractères non-ASCII enlevés |
| Nom de carnet dans `evernote_notebook` | Conservé verbatim |

Exemples :

| Source | Slug `.md` / dossier |
|---|---|
| `Facture EDF mars 2024` | `Facture-EDF-mars-2024` |
| `Comptabilité 2024` | `Comptabilite-2024` |
| `Réunion: bilan Q1/2024` | `Reunion-bilan-Q1-2024` |
| `Élève — évaluation` | `Eleve-evaluation` |

### Filtrage MIME

Seules les pièces jointes dont le MIME figure dans la `allowed_mime_types` (cf. `config.yml`) sont migrées. Toute autre pièce jointe est :

- Non écrite sur disque
- Tracée dans le rapport erreurs avec niveau `attachment` et cause `mime_excluded`
- Aucune mention ajoutée dans le `.md` correspondant (sinon les notes issues de captures web seraient polluées de dizaines de lignes "ressource non migrée")

Cette politique remplace une approche "tout migrer" qui aurait inondé le vault avec les ressources annexes des captures web Evernote (CSS, fonts, icônes du site source, etc.).

Le test du filtrage se fait sur le MIME extrait de la balise `<mime>` du `<resource>` ENEX. Comparaison stricte (sensible à la casse, sans normalisation). Un MIME absent du `<resource>` (cas dégénéré) est traité comme `mime_excluded`.

La allowlist par défaut couvre les usages admin standard : documents bureautiques (PDF, Office, OpenDocument, RTF, texte, CSV), images sans formats web (JPEG, PNG, HEIC, TIFF — **pas** SVG, WebP, GIF), email exporté, archives, audio. Les MIME explicitement exclus par décision V1.6 : `image/svg+xml`, `image/webp`, `image/gif`, tout MIME non listé.

L'utilisateur peut amender la liste dans son `config.yml` selon les besoins de son corpus, sans modifier le code.

### Sanitization sécurité

Avant toute écriture de fichier :

- Suppression des caractères interdits par macOS / Linux / Windows : `< > : " / \ | ? *`
- Suppression des séquences de path traversal sur base segmentaire : un nom de fichier est rejeté si l'un de ses segments (split sur `/` ou `\`) est exactement `..` ou `.`. Les `..` internes à un segment (exemple : `report..backup.pdf`) sont conservés comme parties légitimes du nom.
- Vérification que le chemin résolu (`os.path.realpath`) est strictement sous `vault_path`
- Si la vérification échoue : abandon de l'écriture, log d'erreur

---

## Bloc 4 — Comportements aux limites

| Situation | Comportement |
|---|---|
| `.enex` introuvable pour un carnet listé | Log erreur (carnet, nom recherché, dossier source). Passage au carnet suivant. |
| `.enex` vide ou XML mal formé global | Log erreur (carnet, cause). Passage au carnet suivant. |
| Note avec XHTML mal formé | Log erreur (carnet, note_guid, cause). Aucun `.md` produit pour cette note. Passage à la note suivante. |
| Note sans titre | Slug généré depuis `evernote_guid` : `note-[8-premiers-caractères-guid].md`. Le frontmatter `title:` est `""`. |
| Note sans contenu (pièce jointe uniquement) | `.md` produit avec frontmatter + lien/embed vers la pièce jointe. Aucun corps de texte. |
| Note avec `created` ou `updated` absent | Champ frontmatter vide `""`. Pas de date inventée. |
| Balise XML absente vs balise vide | Balise absente → champ Python `None`. Balise présente mais vide (`<tag></tag>`) → champ Python `""`. La distinction est préservée verbatim par `enex_parser.py` ; `metadata_extractor.py` traite les deux cas. |
| Note sans tags | `tags: []` dans le frontmatter. |
| Pièce jointe sans nom (`<file-name>` absent) | Nom généré : `attachment-[hash-8-premiers-caractères].[extension-inférée-depuis-mime]`. Si mime inconnu : extension `.bin`. |
| Pièce jointe > `attachment_size_limit_mb` (200 Mo par défaut) | Log erreur (carnet, note, fichier, taille). Pièce jointe NON copiée. Le `.md` contient à l'emplacement : `[pièce jointe ignorée : taille > N Mo, voir log]`. |
| Pièce jointe avec MIME hors allowlist (`text/css`, `font/*`, `image/svg+xml`, `image/webp`, `image/gif`, etc.) | Log erreur niveau attachment, cause `mime_excluded`. Pièce jointe NON copiée. Aucune mention dans le `.md`. |
| Pièce jointe avec base64 corrompu | Log erreur. Pièce jointe NON copiée. Mention dans le `.md` : `[pièce jointe corrompue, voir log]`. |
| Pièce jointe avec nom dangereux (`../`, chemins absolus) | Sanitization automatique → suffixe + log dans collisions.csv avec mention `sanitized`. La pièce jointe est copiée sous son nom sanitisé. |
| Collision de pièce jointe dans un carnet | Suffixe `-2`, `-3`, ... + log CSV. Pas d'écrasement. |
| Collision de nom `.md` dans un carnet | Suffixe `-2`, `-3`, ... + log CSV. Pas d'écrasement. |
| `.md` cible existe déjà, pas de `--force` | Skip + log erreur (carnet, note, chemin cible). Pièces jointes de cette note NON copiées non plus. |
| `.md` cible existe déjà, `--force` actif | Écrasement silencieux. Pièces jointes de cette note copiées normalement (avec gestion collision). |
| Tag avec espaces multiples ou caractères exotiques | Normalisation : trim + collapse espaces + slug. Tag vide après normalisation → ignoré. |
| Carnet listé dans `carnets-a-migrer.txt` deux fois | Traité une seule fois. Log warning. |
| `--carnet "X"` et X absent du fichier `.enex` | Erreur terminal explicite. Aucune migration lancée. |
| `--dry-run` | Aucune écriture, aucune copie. Affichage du plan : carnets sélectionnés, nombre de notes par carnet, nombre de pièces jointes par carnet, collisions prévues si détectables. |
| `source_directory` introuvable au démarrage | Erreur terminal explicite. Arrêt immédiat avant toute écriture. |
| `vault_path` introuvable au démarrage | Erreur terminal explicite. Arrêt immédiat. |
| `vault_path` existe mais en lecture seule | Erreur terminal explicite. Arrêt immédiat. |
| `log_directory` introuvable | Création automatique. Pas d'erreur. |
| Convertisseur tué pendant l'exécution (Ctrl+C, crash) | Aucune transaction. Les `.md` et pièces jointes déjà écrits restent. Le log d'exécution montre la dernière note traitée — permet de reprendre. |

### Sécurité — règles explicites

1. **Parser XML tolérant** : utiliser `lxml` en mode `recover=True` ou `ElementTree` avec gestion d'exception par note. Une note dont le XHTML est invalide est skippée, pas le carnet entier.
2. **Plafond pièce jointe** : `attachment_size_limit_mb` (défaut 200 Mo). Au-delà : log + skip. Empêche la saturation RAM sur un fichier embarqué anormalement gros.
3. **Sanitization noms de fichiers** : suppression des caractères interdits par les systèmes de fichiers majeurs avant toute écriture.
4. **Anti path-traversal** : `os.path.realpath` du chemin cible doit commencer par `os.path.realpath(vault_path)`. Sinon : abandon de l'écriture, log d'erreur. Empêche qu'une pièce jointe nommée `../../etc/passwd` sorte du vault.

### Format des logs

**Log d'exécution** : `migration-YYYY-MM-DD-HHMM.log` — format texte lisible humain.

```
[2026-06-29 14:30:00] Démarrage migration
[2026-06-29 14:30:00] Config : source=/Users/.../exports-enex, vault=/Users/.../Vault-Admin
[2026-06-29 14:30:00] Carnets sélectionnés (3) : Comptabilité 2024, Bail appartement, Factures EDF
[2026-06-29 14:30:01] === Carnet : Comptabilité 2024 ===
[2026-06-29 14:30:01] ENEX trouvé : Comptabilité 2024.enex (12.3 Mo)
[2026-06-29 14:30:02] Parsing : 47 notes détectées
[2026-06-29 14:30:02] Note 1/47 : Facture EDF mars 2024 → OK
[2026-06-29 14:30:03] Note 2/47 : Facture EDF avril 2024 → OK (collision attachment : scan.pdf → scan-2.pdf)
[2026-06-29 14:30:04] Note 3/47 : Relevé bancaire Q1 → ERREUR (XHTML mal formé, voir erreurs.csv)
...
[2026-06-29 14:32:15] === Résumé Carnet : Comptabilité 2024 ===
[2026-06-29 14:32:15] Notes : 47 en entrée, 45 succès, 1 erreur partielle, 1 erreur totale
[2026-06-29 14:32:15] Pièces jointes : 89 copiées, 2 collisions, 1 ignorée (taille)
...
[2026-06-29 14:45:30] === Résumé global ===
[2026-06-29 14:45:30] Carnets : 3/3 traités
[2026-06-29 14:45:30] Notes : 156 en entrée, 151 succès, 3 erreurs partielles, 2 erreurs totales
[2026-06-29 14:45:30] Pièces jointes : 287 copiées, 5 collisions, 1 ignorée
[2026-06-29 14:45:30] Voir : collisions-2026-06-29-1430.csv, errors-2026-06-29-1430.csv
```

**Rapport collisions** : `collisions-YYYY-MM-DD-HHMM.csv`

```csv
timestamp,carnet,note_titre,note_guid,type,nom_original,nom_final,note
2026-06-29T14:30:03,Comptabilité 2024,Facture EDF avril,b2c3d4e5-...,attachment,scan.pdf,scan-2.pdf,
2026-06-29T14:31:12,Comptabilité 2024,Facture Free,c3d4e5f6-...,attachment,IMG_1234.jpg,IMG_1234-2.jpg,
2026-06-29T14:32:05,Comptabilité 2024,Réunion,d4e5f6g7-...,md,Reunion.md,Reunion-2.md,deuxième note de même titre
```

Colonne `type` : `attachment` ou `md`. Colonne `note` : libre, pour annotations supplémentaires (`sanitized` si le nom a été modifié pour raison sécurité).

**Rapport erreurs** : `errors-YYYY-MM-DD-HHMM.csv`

```csv
timestamp,carnet,note_titre,note_guid,niveau,cause,detail
2026-06-29T14:30:04,Comptabilité 2024,Relevé bancaire Q1,c3d4e5f6-...,note,xhtml_malformed,XMLSyntaxError ligne 47
2026-06-29T14:31:45,Comptabilité 2024,Photos vacances,d4e5f6g7-...,attachment,size_exceeded,fichier video.mp4 : 720 Mo > 500 Mo
2026-06-29T14:35:00,Impôts 2023,—,—,notebook,enex_not_found,Aucun fichier Impôts 2023.enex dans source_directory
```

Colonne `niveau` : `notebook` (carnet entier en erreur), `note` (note en erreur totale), `attachment` (pièce jointe en erreur, note OK).

---

## Bloc 5 — Stratégie de test

### Fixture de référence

Pas de `.enex` versionné dans le repo (risque de fuite de données personnelles si un vrai carnet est commité par erreur).

Le test smoke s'exécute sur un carnet Evernote réel désigné par l'utilisateur via la variable d'environnement `ENEX_REFERENCE_FILE`. Si la variable n'est pas définie, le test est skip avec un message explicite (`pytest.skip`).

```bash
export ENEX_REFERENCE_FILE=~/Migration-Evernote/exports-enex/Bail-test.enex
pytest tests/test_smoke.py
```

Recommandation pour le choix du carnet de référence : un petit carnet (10 à 30 notes) représentatif des cas courants — notes texte, notes avec pièces jointes PDF, notes avec images, au moins une note dégradée (sans titre, sans tags, ou avec caractères exotiques). L'utilisateur prépare ce carnet une fois, en début de projet, et le garde sous `~/Migration-Evernote/exports-enex/`.

Les tests de contrat (CT-XX) restent indépendants de cette fixture et s'exécutent toujours — ils utilisent des fragments XML inlinés dans le code de test, pas un fichier ENEX complet.

### Tests de contrat (automatisés)

`tests/test_contract.py` — écrits avant les modules concernés. Validation que chaque module respecte le contrat des specs.

| # | Cas testé | Résultat attendu |
|---|---|---|
| CT-01 | Parsing du `reference.enex` | 3 notes extraites, métadonnées complètes pour chacune |
| CT-02 | Slug ASCII de "Comptabilité 2024" | "Comptabilite-2024" |
| CT-03 | Slug ASCII de "Réunion: bilan Q1/2024" | "Reunion-bilan-Q1-2024" |
| CT-04 | Tag normalisé "Facture EDF" | "facture-edf" |
| CT-05 | Tag normalisé "Élève évaluation" | "eleve-evaluation" |
| CT-06 | Frontmatter d'une note complète | Tous les champs présents, dates ISO 8601 |
| CT-07 | Frontmatter d'une note sans `updated` | Champ `updated: ""` (chaîne vide, pas absente) |
| CT-08 | Conversion XHTML basique en MD | Balises `<p>`, `<ul>`, `<li>`, `<strong>` correctement converties |
| CT-09 | Conversion `<en-todo>` non cochée | `- [ ]` |
| CT-10 | Conversion `<en-todo>` cochée | `- [x]` |
| CT-11 | Image embarquée → embed Obsidian | `![[attachments/image.png]]` |
| CT-12 | PDF embarqué → embed Obsidian | `![[attachments/document.pdf]]` |
| CT-13 | Collision de pièce jointe (2 fois "scan.pdf") | "scan.pdf" puis "scan-2.pdf" |
| CT-14 | Collision de `.md` (2 notes "Facture") | "Facture.md" puis "Facture-2.md" |
| CT-15 | Pièce jointe avec nom "../etc/passwd" | Sanitisé en "etc-passwd" ou similaire, log dans collisions.csv avec note "sanitized" |
| CT-16 | Pièce jointe > plafond taille | Non copiée, log erreur, mention dans le `.md` |
| CT-16b | Pièce jointe avec MIME hors allowlist (image/svg+xml) | Non copiée, log erreur cause `mime_excluded`, aucune mention dans le `.md` |
| CT-17 | Note sans titre | Slug `note-[8-chars-guid].md`, frontmatter `title: ""` |
| CT-18 | Tag vide après normalisation | Tag ignoré, pas d'entrée vide dans `tags:` |
| CT-19 | Pièce jointe avec nom en NFD (`nucléaire.pdf`) | `final_filename` en NFC (`nucléaire.pdf`), `unicodedata.is_normalized("NFC", result)` == True |
| CT-20 | Lien généré pour PDF accentué (`nucléaire.pdf`) | URL-encoding produit `%C3%A9` et `%C3%A7`, pas `%CC%81` ni `%CC%A7` |
| CT-21 | Embed wikilink pour PDF | Lien généré au format `![[attachments/fichier.pdf]]`, pas `[fichier.pdf](attachments/fichier.pdf)` |
| CT-22 | Lien Markdown classique pour docx | Lien au format `[fichier.docx](attachments/fichier.docx)`, pas d'embed |

### Test de smoke (intégration)

`tests/test_smoke.py` — exécute le pipeline complet sur le carnet désigné par `ENEX_REFERENCE_FILE`. Skip si la variable n'est pas définie.

```python
import os, pytest

def test_smoke():
    enex_path = os.environ.get("ENEX_REFERENCE_FILE")
    if not enex_path or not os.path.exists(enex_path):
        pytest.skip("ENEX_REFERENCE_FILE non défini ou fichier introuvable")

    # Setup : dossier temporaire vault + log
    # Execution : enex2obsidian sur le carnet de référence
    # Vérifications :
    # - Au moins 1 fichier .md produit dans [vault]/[carnet]/
    # - Sous-dossier attachments/ présent si le carnet a des pièces jointes
    # - Fichiers de log présents et non vides
    # - Aucun fichier écrit hors du vault temporaire
    # - Compte de .md + lignes "erreurs niveau note" du CSV = nombre de notes dans le .enex
```

Le test ne valide pas le contenu fonctionnel des fichiers produits (c'est le rôle de la checklist de relecture humaine) — il valide uniquement la complétude du pipeline et la conformité structurelle.

### Tests de comportements aux limites (automatisés)

`tests/test_limits.py` — fixtures dédiées pour chaque cas.

| # | Cas testé | Résultat attendu |
|---|---|---|
| LI-01 | ENEX inexistant pour carnet listé | Log erreur niveau notebook, carnet suivant traité |
| LI-02 | ENEX XML invalide global | Log erreur, carnet suivant traité |
| LI-03 | Note avec XHTML mal formé | Log erreur niveau note, note suivante traitée |
| LI-04 | Pièce jointe > plafond | Log erreur, mention dans le `.md`, note traitée |
| LI-05 | Pièce jointe avec base64 corrompu | Log erreur, mention dans le `.md`, note traitée |
| LI-06 | `.md` cible existe, pas de `--force` | Skip + log, note suivante traitée |
| LI-07 | `.md` cible existe, `--force` | Écrasement, log info |
| LI-08 | `--dry-run` sur reference.enex | Aucune écriture disque, plan affiché sur stdout |
| LI-09 | `--carnet "X"` avec X absent | Erreur terminal, aucune migration |
| LI-10 | `vault_path` en lecture seule | Erreur terminal au démarrage, arrêt immédiat |

### Checklist de relecture humaine

Après une migration réelle, à parcourir sur un échantillon de 5 à 10 notes par carnet :

1. **Titre Obsidian** : correspond-il au titre Evernote (via le frontmatter `title:`) ?
2. **Date de création** : la date dans Obsidian correspond-elle à la date Evernote ?
3. **Tags** : tous les tags Evernote sont-ils présents (normalisés) ?
4. **Corps de texte** : la structure du texte est-elle préservée (paragraphes, listes, gras) ?
5. **Cases à cocher** : si la note en contenait, sont-elles présentes et avec le bon état ?
6. **Pièces jointes** : toutes présentes dans `attachments/` ? Les liens fonctionnent (clic depuis Obsidian ouvre le fichier) ?
7. **Images inline** : affichées correctement dans Obsidian via les embeds ?
8. **Rapport erreurs** : lecture du CSV — chaque ligne d'erreur correspond-elle à un cas attendu, ou y a-t-il des surprises ?
9. **Rapport collisions** : les renommages `-2`, `-3` correspondent-ils à des cas légitimes ?
10. **Vault propre** : aucun fichier orphelin ? Aucun dossier hors structure prévue ?

### Validation finale par carnet

Un carnet est validé migrer quand :

- Le nombre de `.md` produits + le nombre de notes en erreur totale (CSV erreurs, niveau `note`) = nombre de notes du `.enex` source.
- Toutes les pièces jointes des notes en succès sont présentes dans `attachments/` ou loggées en erreur explicite.
- L'utilisateur a relu à vue 5 à 10 notes choisies au hasard.

---

## Annexe — Exemple de conversion

### Source ENEX (extrait simplifié)

```xml
<note>
  <title>Facture EDF mars 2024</title>
  <content><![CDATA[<?xml version="1.0" encoding="UTF-8"?>
<en-note>
  <div>Facture reçue le 15 mars.</div>
  <div>Montant : <strong>127,45 €</strong></div>
  <en-todo checked="false"/>Payer avant le 30 mars
  <div><en-media hash="abc123..." type="application/pdf"/></div>
</en-note>]]></content>
  <created>20240315T092300Z</created>
  <updated>20240315T092500Z</updated>
  <tag>factures</tag>
  <tag>EDF</tag>
  <tag>2024</tag>
  <note-attributes>
    <source-url></source-url>
  </note-attributes>
  <resource>
    <data encoding="base64">JVBERi0xLjQK...</data>
    <mime>application/pdf</mime>
    <resource-attributes>
      <file-name>Facture EDF mars 2024.pdf</file-name>
    </resource-attributes>
  </resource>
</note>
```

### Résultat dans Obsidian

Fichier : `Vault-Admin/Comptabilite-2024/Facture-EDF-mars-2024.md`

```markdown
---
title: "Facture EDF mars 2024"
created: 2024-03-15T09:23:00
updated: 2024-03-15T09:25:00
tags:
  - factures
  - edf
  - 2024
source_url: ""
evernote_notebook: "Comptabilité 2024"
evernote_guid: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
---

Facture reçue le 15 mars.

Montant : **127,45 €**

- [ ] Payer avant le 30 mars

![[attachments/Facture EDF mars 2024.pdf]]
```

Pièce jointe copiée : `Vault-Admin/Comptabilite-2024/attachments/Facture EDF mars 2024.pdf`

---

## Séquence d'implémentation — ordre obligatoire

```
1.  Bootstrap (structure repo complète + fichiers vides + docstrings)
2.  src/filename_normalizer.py (slug, sanitization, anti-traversal)
3.  src/enex_parser.py (parsing XML, extraction notes brutes)
4.  src/metadata_extractor.py (extraction + normalisation frontmatter)
5.  src/content_converter.py (XHTML → Markdown)
6.  src/attachment_handler.py (décodage, gestion collisions, écriture)
7.  src/notebook_selector.py (parsing carnets-a-migrer.txt)
8.  src/reporter.py (logs et CSV)
9.  tests/test_contract.py ← AVANT writer (TDD)
10. src/writer.py ← implémenté pour passer les tests de contrat
11. enex2obsidian.py (orchestrateur passif, zéro logique métier)
12. tests/test_smoke.py ← APRÈS pipeline complet
13. tests/test_limits.py
14. README.md + README.fr.md + CLAUDE.md
```

Ne jamais paralléliser. Ne jamais passer à l'étape N+1 sans validation de l'étape N.

---

*Fin des spécifications V1.4*
*Amendement V1.1 : stack XML actée (lxml), plafond pièce jointe à 200 Mo, fixture de test = carnet réel via variable d'environnement*
*Amendement V1.2 : casse conservée pour le slug ASCII (alignement avec les exemples — Facture-EDF-mars-2024, pas facture-edf-mars-2024)*
*Amendement V1.3 : alignement de la spec sur l'approche segmentaire de path traversal.*
*Amendement V1.4 : corrections post-audit du module enex_parser — protection XXE (resolve_entities=False, no_network=True), hash RawAttachment toujours None, tolérance par note via try/except, distinction balise absente (None) vs vide ("").*
*Amendement V1.5 : huge_tree=True pour autoriser les pièces jointes Evernote en base64. Détecté en test empirique post-commit (cyber.enex 91 Mo, 0 notes extraites avec huge_tree=False).*
*Amendement V1.6 : filtrage des pièces jointes par allowlist MIME. Découvert sur cyber.enex (114 PJ dont 86% ressources annexes de captures web). Allowlist par défaut couvre les documents bureautiques, images sans formats web (JPEG/PNG/HEIC/TIFF, **pas** SVG/WebP/GIF), email, archives, audio. Configurable dans `config.yml`.*
*Amendement V1.7 : vérification documentaire à mi-parcours (entre étapes 7 et 8). Identification explicite des champs ENEX hors scope V1, reportés V2. Décision motivée par l'usage réel de l'utilisateur (pas de rappels, pas de géoloc, pas de référencement par auteur en admin). source-url confirmé comme couvert en V1.*
*Amendement V1.8 : bug fonctionnel découvert en inspection visuelle Obsidian (post-étape 11). Liens vers PDFs avec accents cassés à cause de l'absence de normalisation NFC. Correction en 3 points (sanitize_attachment_name, _resolve_filename, _resolve_placeholders) + extension du format embed wikilink aux PDFs (en plus des images). CT-11 et CT-12 mis à jour. CT-19 à CT-22 ajoutés. Confirmé par audit Codex.*
*Document à consommer directement par Claude Code après validation humaine.*
