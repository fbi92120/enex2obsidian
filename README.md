# enex2obsidian

Outil CLI Python de conversion `.enex` Evernote vers vault Obsidian, conçu pour une migration ponctuelle de notes administratives.

**Statut : projet archivé après migration réelle. Non maintenu.**

Spécifications de référence : SPECS.md V1.8. Date de migration réelle : à compléter à la clôture.

---

## Installation

Python 3.12 requis (macOS avec Python 3.12 installé via Homebrew ou python.org).

```bash
cd ~/Projects/enex2obsidian
python3.12 -m venv .venv
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

Copier et adapter le fichier de configuration :

```bash
cp config.yml.example config.yml
cp carnets-a-migrer.txt.example carnets-a-migrer.txt
# Éditer config.yml avec les chemins réels (source, vault, logs)
# Éditer carnets-a-migrer.txt avec les noms exacts des carnets à migrer
```

---

## Usage CLI

```
python enex2obsidian.py [OPTIONS]
```

**Options :**

| Option | Défaut | Description |
|---|---|---|
| `--config CONFIG` | `./config.yml` | Chemin du fichier de configuration |
| `--source SOURCE` | config | Dossier contenant les `.enex` exportés |
| `--vault VAULT` | config | Vault Obsidian de destination |
| `--carnets CARNETS` | config | Fichier liste des carnets à migrer |
| `--carnet CARNET` | — | Migrer un seul carnet (par nom exact, ignore `--carnets`) |
| `--log-dir LOG_DIR` | `./logs` | Dossier des logs et rapports CSV |
| `--force` | false | Écraser les `.md` existants (défaut : skip + log) |
| `--dry-run` | false | Lister ce qui serait migré sans écrire |

**Codes de sortie :**

- `0` — migration terminée (même avec des erreurs par note — voir logs)
- `1` — erreur terminale avant démarrage (carnet `--carnet` introuvable, config invalide, source inaccessible)

**Exemples :**

```bash
# 1. Dry-run sur un carnet unique — vérifie sans écrire
python enex2obsidian.py --carnet "Comptabilité 2024" --dry-run

# 2. Migration réelle d'un carnet vers le vault Obsidian
python enex2obsidian.py --carnet "Comptabilité 2024"

# 3. Rejeu avec --force après correction (écrase les .md existants)
python enex2obsidian.py --carnet "Comptabilité 2024" --force
```

Pour migrer tous les carnets listés dans `carnets-a-migrer.txt`, omettre `--carnet` :

```bash
python enex2obsidian.py --dry-run   # dry-run complet
python enex2obsidian.py             # migration complète
```

---

## Format de sortie

Le vault produit est structuré ainsi :

```
vault_path/
├── comptabilite-2024/          # un dossier par carnet (slug ASCII, casse préservée)
│   ├── facture-edf-mars.md     # un .md par note (slug NFC)
│   ├── note-a1b2c3d4.md        # note sans titre → slug basé sur guid
│   └── attachments/
│       ├── scan.pdf
│       ├── scan-2.pdf          # collision → suffixe -2
│       └── photo.jpeg
├── bail-appartement/
│   └── ...
```

Chaque `.md` commence par un frontmatter YAML :

```yaml
---
title: "Facture EDF mars 2024"
created: 2024-03-15T09:23:00
updated: 2024-03-15T09:25:00
tags:
  - facture
  - edf
source_url: ""
evernote_notebook: "Comptabilité 2024"
evernote_guid: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
---
```

Pièces jointes dans le corps Markdown :
- Images et PDFs → embed wikilink : `![[attachments/document.pdf]]`
- Autres types (Word, Excel, archives, audio) → lien classique : `[document.docx](attachments/document.docx)`

Trois fichiers de log sont produits par run dans `log_directory` :
- `migration-YYYY-MM-DD-HHMM.log` — journal d'exécution
- `errors-YYYY-MM-DD-HHMM.csv` — notes et pièces jointes en erreur (une ligne par incident)
- `collisions-YYYY-MM-DD-HHMM.csv` — collisions de noms résolues par suffixe

Pour le détail exhaustif du format : voir SPECS.md V1.8 Bloc 3.

---

## Guide de migration réelle

Procédure pour la migration one-shot des 1772 notes admin.

### 1. Pré-flight

- Nettoyage côté Evernote terminé (notes inutiles supprimées, titres vérifiés).
- Export ENEX à jour : tous les carnets listés dans `carnets-a-migrer.txt` exportés depuis l'app Evernote macOS via Fichier > Exporter les notes. Un `.enex` par carnet, deposé dans `source_directory`.
- Vault Obsidian cible vide (ou état versionné connu).
- `config.yml` vérifié : `source_directory`, `vault_path`, `log_directory`, `notebook_list` pointent vers les bons chemins.

### 2. Dry-run par carnet

Pour chaque carnet, avant d'écrire :

```bash
python enex2obsidian.py --carnet "Nom du carnet" --dry-run
```

Vérifier dans la sortie stdout :
- Nombre de notes détectées correspond à l'attendu Evernote.
- Aucune ligne `[ERREUR]` terminale.

### 3. Migration effective

Carnet par carnet (plus facile à contrôler) ou en une passe (plus rapide) :

```bash
# Carnet par carnet
python enex2obsidian.py --carnet "Comptabilité 2024"
python enex2obsidian.py --carnet "Bail appartement"
# ...

# Ou en une passe complète (tous les carnets de carnets-a-migrer.txt)
python enex2obsidian.py
```

Temps indicatif : quelques secondes par carnet de taille standard (< 100 notes, PDFs < 10 Mo). Les carnets lourds (scans haute résolution) peuvent prendre 1-2 minutes.

### 4. Inspection post-migration

Ouvrir le vault dans Obsidian, puis :

1. Inspecter 5-10 notes au hasard — frontmatter rendu correctement, contenu Markdown lisible.
2. Cliquer sur au moins 3 liens vers pièces jointes, dont au moins 1 avec un nom accentué (ex : `Réclamation.pdf`). Un clic qui crée un fichier vide `X.pdf 1` signale un lien cassé.
3. Vérifier les embeds (images, PDFs) en mode lecture Obsidian.
4. Vérifier les tags dans la palette de tags Obsidian.
5. Ouvrir `errors-*.csv` — s'assurer qu'aucune ligne n'est inattendue. Chaque ligne d'erreur doit être connue ou traitée.
6. Ouvrir `collisions-*.csv` — les collisions de noms sont normales si deux notes partagent le même titre.

### 5. Traitement des rejets

Notes en erreur (`cause` dans `errors-*.csv`) :
- `xhtml_malformed` : XHTML de la note structurellement cassé. Traitement manuel recommandé dans Evernote puis rejeu `--force`.
- `enex_not_found` : carnet listé mais `.enex` absent — vérifier l'export Evernote.
- `md_exists_no_force` : `.md` existant skippé — normal en rejeu sans `--force`.
- `write_error` : erreur disque — vérifier l'espace disponible et les droits iCloud Drive.

Rejeu ciblé après correction :

```bash
python enex2obsidian.py --carnet "Nom du carnet" --force
```

### 6. Clôture

- Archiver les logs (`logs/`) dans `~/Migration-Evernote/logs-archivés/`.
- Mettre à jour `CONTEXTE-PROJET.md` avec la date de migration réelle et la volumétrie finale (notes ok, erreurs, collisions).
- Désactiver le venv. Le repo peut rester en place pour référence.

---

## Limitations connues

Deux points de vigilance actifs pendant la migration, issus de l'audit pré-migration :

### Filtre entité trop large (`content_converter.py`)

Le filtre d'erreurs ENML ignore toute erreur dont le message contient "entity". Cela couvre le cas attendu (`Entity 'nbsp' not defined` — normal en ENML sans DTD) mais aussi des entités réellement cassées comme `&amp` malformé. Une note avec ce type d'erreur peut être convertie sans avertissement au lieu d'être rejetée.

**Symptôme observable :** note présente dans le vault (pas de ligne `xhtml_malformed` dans `errors-*.csv`) mais contenu `.md` vide ou tronqué.

**Diagnostic :** ouvrir la note dans Evernote et inspecter son contenu ; si elle contient des entités HTML non standard, c'est ce bug. Confirmer en cherchant le GUID dans `errors-*.csv` : absence de ligne = conversion silencieuse.

**Action :** corriger la note dans Evernote (supprimer l'entité cassée ou reformater) puis relancer avec `--force` sur le carnet concerné.

### Détection incomplète des `.enex` non-XML non vides

Si un fichier `.enex` est corrompu sur disque (contenu non-XML, binaire, ou XML partiellement invalide non vide), `lxml` en mode `recover=True` peut produire 0 note sans lever d'exception — aucune ligne dans `errors-*.csv`, aucune alerte.

**Symptôme observable :** le stdout affiche `[Carnet X] — 0 notes` pour un carnet qui devrait en avoir.

**Diagnostic :** vérifier la taille du `.enex` sur disque et l'ouvrir dans un éditeur texte pour confirmer qu'il contient bien du XML ENEX valide. Si le fichier est corrompu, re-exporter depuis Evernote.

**Action :** re-exporter le carnet depuis Evernote, remplacer le `.enex` et relancer la migration.

---

Pour la dette technique non liée à la migration, voir `BACKLOG.md`.

---

## Architecture

Flux de traitement :

```
ENEX → enex_parser → metadata_extractor → content_converter → attachment_handler → writer → reporter
```

`enex2obsidian.py` est l'orchestrateur passif : il parse les arguments CLI, charge la configuration, et délègue à `src/` sans contenir de logique métier.

| Document | Rôle | Version | Emplacement |
|---|---|---|---|
| `SPECS.md` | Spécification fonctionnelle et technique | V1.8 | Racine repo |
| `CLAUDE.md` | Règles opérationnelles du projet | V1.9 | Racine repo |
| `CONTEXTE-PROJET.md` | Mémoire d'avancement et décisions | V4.0 | Hors repo — `~/Migration-Evernote/` (projet Claude.ai enex2obsidian) |
| `BACKLOG.md` | Dette technique connue | Courante | Racine repo |
| `METHODE_SPECS_CO-CONSTRUCTION.md` | Méthode transversale | — | Repo `vibe-coding-governed` (externe) |

---

## Licence

Projet privé, non publié. Tous droits réservés.
