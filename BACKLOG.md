# BACKLOG — enex2obsidian

Dette technique et écarts identifiés mais non traités.
Chaque entrée mentionne : origine, description, criticité, action de résolution attendue.

---

## Importants — à traiter avant migration réelle

*(Vide — PROMPT-13-FIX a résolu les 6 divergences Constitution bloquantes.)*

## Importants — à traiter avant V2 (si V2)

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

---

*Dernière mise à jour : 2026-07-01 (PROMPT-13-FIX)*
