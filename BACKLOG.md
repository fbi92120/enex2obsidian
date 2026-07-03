# BACKLOG — enex2obsidian

# BACKLOG — enex2obsidian
Version : 1.1 (incrémenter)
Date : 2026-07-03 [heure d'ajout]

Dette technique et écarts identifiés mais non traités.
Chaque entrée mentionne : origine, description, criticité, action de résolution attendue.

---

## Importants — à traiter avant migration réelle

### Filtre entité trop large dans `_validate_enml_structure()`

**Origine** : audit Codex PROMPT-13-AUDIT, section 1. Classé 🔴 BLOQUANT par
Codex, requalifié 🟡 par arbitrage humain (les .enex issus d'evernote-backup
sont a priori bien formés).
**Description** : `src/content_converter.py:105` filtre toute erreur dont le
message contient "entity". Cela ignore `Entity 'nbsp' not defined` (voulu)
mais aussi des erreurs d'entité réellement mal formée type `&amp` (non voulu).
Une note contenant du XHTML cassé uniquement par entité mal formée peut être
convertie silencieusement au lieu d'être loggée `xhtml_malformed`.
**Risque migration** : perte silencieuse possible sur du XHTML Evernote réel
qui contient probablement des entités non-standard.
**Correction attendue** : filtrer uniquement les messages type
`Entity 'xxx' not defined`, pas tous les messages contenant "entity". Ajouter
tests unitaires sur `_validate_enml_structure()` avec `&nbsp;`, `&apos;`,
`&amp;`, `&amp` cassé.
**Action** : à surveiller pendant la migration réelle — si le CSV erreurs
contient des lignes `xhtml_malformed` inattendues, ou si des `.md` sortent
au contenu vide, revenir corriger avant clôture.

### LI-02 ne couvre pas les fichiers .enex non-XML non vides

**Origine** : audit Codex PROMPT-13-AUDIT, sections 5 et 6. Classé 🔴 BLOQUANT
par Codex, requalifié 🟡 par arbitrage humain.
**Description** : la sonde empirique lxml a confirmé qu'un fichier `.enex`
textuellement non-XML (texte brut, binaire, préambule XML seul) ne déclenche
pas `XMLSyntaxError` avec `recover=True` — il produit 0 note extraite sans
erreur remontée. Aucune ligne CSV `enex_unreadable`, aucun log. Violation
Constitution règle 2 au niveau carnet.
**Risque migration** : quasi nul dans le cas nominal (les .enex viennent
d'evernote-backup, format garanti). Risque réel si un .enex est corrompu sur
disque entre l'export et la migration.
**Correction attendue** : dans `iter_notes()` ou `process_notebook()`, si 0
note produite sur un fichier non vide, logger `enex_unreadable` niveau
`notebook`. Amendement SPECS Bloc 4 à ajouter pour formaliser le cas.
**Action** : à traiter avant clôture projet si les .enex se comportent bien,
ou immédiatement si un cas apparaît en migration.

### Fallback `att_map.get("")` peut produire un faux positif "pièce jointe corrompue"

**Origine** : audit Codex PROMPT-13-AUDIT, section 3. Classé 🟡 IMPORTANT.
**Description** : `src/writer.py:289` — si un placeholder hashé n'est pas
trouvé, le writer regarde `attachment_map.get("")`. S'il existe une PJ
corrompue dans la même note, tout placeholder non résolu (ex : correspondant
à une autre PJ absente pour d'autres raisons) devient faussement
"pièce jointe corrompue".
**Risque migration** : cosmétique — l'utilisateur peut voir "corrompue" dans
un `.md` alors que la vraie raison est autre. Diagnostic dégradé.
**Correction attendue** : dans `process_note`, conserver une correspondance
explicite entre placeholder hash et résultat d'attachement.

## Importants — à traiter avant clôture projet ou V2

*Note projet : V1 admin est le scope définitif. Ces items sont ici pour
mémoire au cas où le scope évoluerait.*

### Audit Codex de test_smoke.py (2026-06-30)

Importants reportés (référence PROMPT-12-FIX section Backlog) :
- `test_smoke_no_zero_byte_attachments` non récursif : couvre uniquement
  les fichiers immédiats de `attachments/`. À basculer en `rglob("*")`
  quand l'architecture évoluera vers des sous-dossiers.
- `test_smoke_all_frontmatter_yaml_parsable` : les types ne sont pas
  vérifiés (`tags` en string au lieu de list passerait).
- `test_smoke_no_file_outside_vault` : recherche uniquement `.md` dans
  `log_dir` et `source_dir`. Une PJ écrite hors vault passerait.

### Détail d'erreur XHTML insuffisant pour le CSV

**Origine** : audit Codex PROMPT-13-AUDIT, section 1. Classé 🟡 IMPORTANT.
**Description** : `src/content_converter.py:113` — `ContentConversionError`
ne transporte que `structural_errors[0].message`, sans ligne/colonne. Le CSV
erreurs mentionnera "unclosed element" ou équivalent sans localiser dans la note.
**Correction attendue** : inclure `line`, `column`, `level_name` du
`parser.error_log` dans le message de `ContentConversionError`.
**Impact migration** : diagnostic post-migration dégradé si des notes tombent
en `xhtml_malformed`.

### Performance : idempotence PJ relit tout le fichier existant

**Origine** : audit Codex PROMPT-13-AUDIT, section 4. Classé 🟡 IMPORTANT.
**Description** : `src/attachment_handler.py:229` —
`existing_md5 = hashlib.md5(existing_path.read_bytes()).hexdigest()`.
Sur gros corpus avec PDFs/scans de dizaines de Mo chacun, le 2e run relit
intégralement toutes les PJ existantes.
**Correction attendue** : lire en chunks (`hashlib.md5()` incrémental) au lieu
de `read_bytes()` complet.
**Impact migration** : coût I/O potentiellement élevé sur relance de migration.
Acceptable en V1 pour 1772 notes admin.

### Idempotence cross-session non couverte par tests de contrat

**Origine** : audit Codex PROMPT-13-AUDIT, section 8. Classé 🟡 IMPORTANT.
**Description** : l'idempotence cross-session ajoutée dans `attachment_handler`
(étape 6b) est couverte en intégration par `test_idempotence`, mais pas au
niveau contrat unitaire. Diagnostic dégradé si régression subtile du handler.
**Correction attendue** : ajouter un test contract `AttachmentHandler` : écrire
une PJ, recréer un handler sur le même `target_dir`, traiter la même PJ,
attendre `skipped_existing` et pas de suffixe `-2`.

### BACKLOG.md et CLAUDE.md référencent CONTEXTE-PROJET.md absent du repo

**Origine** : audit Codex PROMPT-13-AUDIT, section 7. Classé 🟡 IMPORTANT
(par Codex, qui ne connaît pas la convention projet).
**Description** : `CONTEXTE-PROJET.md` vit hors repo (dans le projet Claude.ai
enex2obsidian). Les références dans `BACKLOG.md` et `CLAUDE.md:24` peuvent
troubler un futur lecteur du repo.
**Correction attendue** : soit clarifier les références ("hors repo, vit dans
le projet Claude.ai enex2obsidian"), soit remplacer par des entrées autonomes
dans BACKLOG.md.

### LI-06 / md_exists_no_force — PJ tentées avant le skip .md

**Origine** : PROMPT-13 ⚠️ problème 6.
**Description** : SPECS Bloc 4 dit "Pièces jointes de cette note NON copiées
non plus" quand le `.md` cible existe et que `--force` n'est pas activé.
Le code actuel traite les PJ (`process_note`) AVANT d'appeler `writer.write()`.
Si writer retourne `skipped_existing`, les PJ ont déjà été tentées. Avec
l'idempotence cross-session (PROMPT-13-FIX Étape 6b), elles reviennent
`skipped_existing` — pas de fichier dupliqué en pratique. Mais structurellement,
les PJ sont tentées à tort.
**Criticité** : faible (aucune perte de données, aucun fichier dupliqué en V1).
**Résolution** : vérifier l'existence du `.md` cible AVANT la boucle PJ dans
`process_note`. Nécessite refactor de l'ordre des opérations dans l'orchestrateur.

## Mineurs — reportables sans engagement

### Audit Codex de test_smoke.py (2026-06-30)
- Assertion explicite `_FIXTURE_ENEX.exists()` avec message clair
- `iterparse` au lieu de `etree.parse` dans la fixture (cohérence V1.5)
- Regex PDF/image : capturer la cible pour vérification croisée
- Message clés frontmatter manquantes : inclure `present={sorted(fm.keys())}`
- Commentaire de scope sur la fixture (read-only après `migrated_vault`)

### Audit Codex PROMPT-13-AUDIT — mineurs

- **Commentaire obsolète sur fallback dans content_converter** :
  `src/content_converter.py:123` mentionne encore un fallback qui ne s'applique
  plus depuis l'ajout de `_validate_enml_structure()`. À clarifier.
- **Reporter créé même pour erreur terminale `--carnet` absent** :
  `enex2obsidian.py:88` — `main()` instancie `Reporter` avant `run_migration()`.
  Un `--carnet` absent crée potentiellement des fichiers logs vides/header-only
  avant de retourner 1. Contrat SPECS "aucune migration lancée" respecté au sens
  strict, mais artefacts créés à tort.
- **Contexte Markdown non préservé dans les substitutions placeholder** :
  `src/writer.py:309` — substitution regex inline pour messages PJ. Rendu
  dépendant du contexte (liste, tableau).
- **Mutation LI-03 couvre un seul cas de XHTML cassé** :
  `tests/test_limits.py:271` — mutation "balises non fermées". Ne couvre pas
  mal-imbrication, entités, namespace. Tests unitaires directs sur
  `_validate_enml_structure()` seraient plus rigoureux.
- **LI-09 accepte n'importe quel code de sortie non-zéro** :
  `tests/test_limits.py:192` — `exit_code != 0`. Le code réel retourne 1.
  Assertion trop laxe : un retour accidentel de 137 passerait. À durcir en `== 1`.
- **Collision MD5 théorique dans idempotence PJ** :
  `src/attachment_handler.py:230` — deux contenus différents avec même taille
  + même MD5 seraient assimilés identiques. Risque négligeable pour migration
  personnelle, mais SHA-256 serait plus défendable.
- **CT-08 à CT-12 (content_converter) ne couvrent pas la nouvelle exception** :
  Couverture reportée à `test_limits.py::TestDegradedInput::test_li03`.
  Acceptable en intégration.

### Section 5 PROMPT-13-FIX — malformed.enex fixture

**Origine** : PROMPT-13-FIX Section 5.
**Description** : le prompt demandait de remplacer le fichier vide par un XML
tronqué. Empiriquement, lxml `recover=True` parse sans erreur toute variante
de XML tronqué (retourne 0 notes sans levée d'exception). Seul un fichier vide
(0 octet) déclenche `XMLSyntaxError` ('no element found'). La fixture reste vide.
Le choix est documenté dans le docstring du test `test_li02`.
**Criticité** : cosmétique (le test LI-02 passe et couvre bien le cas).
**Résolution** : aucune requise pour V1. Si lxml change de comportement, revisiter.

## Hors scope V1 — bruit connu sur cyber.enex (non pertinent V1 admin)

Documenté dans CONTEXTE-PROJET.md :
- Notes Web Clipper avec contenu pourri : suppression manuelle dans Obsidian
- Ressources `<en-media>` sans `<file-name>` → fichiers `attachment-{hash}.png`
- Notes contenant des `data:image/svg+xml` inline
- Décision : pas d'occurrence significative attendue sur les 1772 notes admin,
  gestion manuelle si rencontrée.

## Dépendances externes

### [exécuté 2026-07-03] Produire vault de référence sur MINITESTMIGRATION.enex

**Projet** : enex2obsidian V1
**Description** : le labo agentique (projet Claude.ai séparé enex2obsidian-agentic) utilise le vault produit par V1 sur MINITESTMIGRATION.enex comme référentiel de comparaison. Le vault de référence sert d'oracle au labo — jamais modifié pendant les cycles, comparaison uniquement en fin de labo.
**Action réalisée** : exécution enex2obsidian V1 (état 123/0/0/0, aucune correction ni ajustement du pipeline) sur MINITESTMIGRATION.enex depuis ~/Migration-Evernote/, sortie vers ~/Migration-Evernote/labo-agentique/reference-vault/. Dry-run préalable pour validation volumétrie, puis migration réelle. Logs auto sous ~/Migration-Evernote/labo-agentique/logs/. Inspections visuelles Obsidian (accents + PJ) validées.
**Livrable** : ~/Migration-Evernote/labo-agentique/reference-vault/MINITESTMIGRATION/
**Log de session** : ~/Migration-Evernote/labo-agentique/reference-vault-execution-2026-07-03.md
**Source** : conversation cadrage labo enex2obsidian-agentic, 2026-07-03
**Statut** : exécuté 2026-07-03. En attente de livraison au projet Claude.ai labo (emplacement de destination défini par SPECS-LABO).