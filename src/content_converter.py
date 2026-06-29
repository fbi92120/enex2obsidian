"""
content_converter — Convert Evernote XHTML note content to Obsidian Markdown.

Responsabilité unique : transformer le contenu XHTML d'une RawNote en Markdown
Obsidian, en remplaçant les balises Evernote propriétaires par des placeholders
ou du Markdown standard.

Ne fait pas :
  - parsing ENEX (enex_parser.py)
  - extraction des métadonnées (metadata_extractor.py)
  - décodage base64 ni résolution des noms de pièces jointes (attachment_handler.py)
  - écriture sur disque (writer.py)

Constitution règle 7 : conversion purement déterministe, aucun LLM.
"""

from __future__ import annotations

import re

import markdownify as md_lib
from lxml import etree


ATTACHMENT_PLACEHOLDER = "{{ATTACHMENT:{hash}}}"


class _EvernoteMarkdownConverter(md_lib.MarkdownConverter):
    """Convertisseur markdownify avec gestion des checkboxes Evernote.

    Surcharge convert_input pour produire '- [ ] ' / '- [x] ' avec le préfixe
    liste, ce qui est le format attendu par Obsidian pour les tâches inline.
    """

    def convert_input(self, el, text, convert_as_inline):
        if el.get("type", "").lower() == "checkbox":
            checked = el.get("checked") is not None
            return "- [x] " if checked else "- [ ] "
        return super().convert_input(el, text, convert_as_inline)


def convert_content(xhtml_content: str | None) -> str:
    """Convertit le contenu XHTML d'une note Evernote en Markdown Obsidian.

    Args:
        xhtml_content: contenu XHTML brut de la note (champ content_xhtml de RawNote).
                       Peut être None si la note n'a pas de contenu texte.

    Returns:
        Chaîne Markdown prête à être insérée dans le .md, après le frontmatter.
        Chaîne vide "" si xhtml_content est None ou vide.
        Les balises <en-media> sont remplacées par des placeholders
        {{ATTACHMENT:hash}} pour résolution ultérieure par l'orchestrateur.
        Si lxml échoue, tentative de conversion via fallback regex ;
        retourne "" uniquement si toutes les tentatives échouent.

    Ne lève jamais d'exception : toute erreur retourne "".
    """
    if not xhtml_content:
        return ""

    try:
        inner_html = _extract_en_note_content(xhtml_content)
        md = _to_markdown(inner_html)
        return _postprocess(md)
    except Exception:
        return ""


def _extract_en_note_content(xhtml_content: str) -> str:
    """Parse le XHTML, pré-traite les balises Evernote, retourne l'inner HTML de <en-note>.

    Utilise lxml en mode recover=True pour tolérer le ENML malformé.
    Pre-processing effectué sur l'arbre lxml avant sérialisation.
    Si lxml échoue, bascule sur _fallback_extract (regex best-effort).
    """
    parser = etree.XMLParser(
        recover=True,
        resolve_entities=False,
        huge_tree=True,
        no_network=True,
    )
    try:
        root = etree.fromstring(xhtml_content.encode("utf-8"), parser)
    except Exception:
        return _fallback_extract(xhtml_content)

    local_tag = root.tag.split("}")[-1] if root.tag else ""
    if local_tag.lower() != "en-note":
        return _fallback_extract(xhtml_content)

    _preprocess_evernote_elements(root)

    # Serialize inner content of <en-note>
    inner = root.text or ""
    for child in root:
        inner += etree.tostring(child, encoding="unicode")
    return inner


def _fallback_extract(xhtml_content: str) -> str:
    """Extraction regex de secours si lxml ne peut pas parser.

    Best-effort : tente de gérer les balises Evernote propriétaires via regex.
    Utilisé uniquement quand lxml échoue totalement.
    """
    m = re.search(r"<en-note[^>]*>(.*)</en-note>", xhtml_content, re.DOTALL | re.IGNORECASE)
    content = m.group(1) if m else xhtml_content
    content = re.sub(
        r'<en-todo\b[^>]*\bchecked=["\']false["\'][^>]*/?>',
        '<input type="checkbox">',
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r'<en-todo\b[^>]*\bchecked=["\']true["\'][^>]*/?>',
        '<input type="checkbox" checked="checked">',
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r"<en-media\b([^>]*)/>",
        lambda m: _media_placeholder_from_attrs(m.group(1)),
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r"<en-crypt\b[^>]*>.*?</en-crypt>",
        "[contenu chiffré Evernote — non migré]",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return content


def _media_placeholder_from_attrs(attrs_str: str) -> str:
    """Extrait le hash depuis une chaîne d'attributs et retourne le placeholder."""
    m = re.search(r'\bhash=["\']([^"\']+)["\']', attrs_str, re.IGNORECASE)
    if m:
        return ATTACHMENT_PLACEHOLDER.replace("{hash}",m.group(1))
    return "[pièce jointe sans hash]"


def _preprocess_evernote_elements(root) -> None:
    """Remplace en-todo, en-media, en-crypt dans l'arbre lxml (in-place).

    - <en-todo checked="false"/> → <input type="checkbox"> (markdownify gère → - [ ] )
    - <en-todo checked="true"/>  → <input type="checkbox" checked="checked">
    - <en-media hash="H">        → texte littéral {{ATTACHMENT:H}}
    - <en-crypt>                 → texte littéral [contenu chiffré Evernote — non migré]

    Collecte d'abord la liste complète pour éviter de modifier l'arbre pendant l'itération.
    """

    def local_name(el) -> str:
        return el.tag.split("}")[-1] if isinstance(el.tag, str) else ""

    def replace_with_text(el, text: str) -> None:
        """Remplace l'élément par du texte, en préservant le tail."""
        parent = el.getparent()
        if parent is None:
            return
        tail = el.tail or ""
        siblings = list(parent)
        idx = siblings.index(el)
        if idx == 0:
            parent.text = (parent.text or "") + text + tail
        else:
            prev = siblings[idx - 1]
            prev.tail = (prev.tail or "") + text + tail
        parent.remove(el)

    # en-crypt first (can have children — remove before iterating descendants)
    crypts = [el for el in root.iter() if local_name(el) == "en-crypt"]
    for el in crypts:
        replace_with_text(el, "[contenu chiffré Evernote — non migré]")

    # en-todo and en-media (self-closing, no children)
    evernote_els = [
        el for el in root.iter() if local_name(el) in ("en-todo", "en-media")
    ]
    for el in evernote_els:
        name = local_name(el)
        if name == "en-todo":
            checked = el.get("checked", "false").lower() == "true"
            tail = el.tail or ""
            parent = el.getparent()
            if parent is None:
                continue
            input_el = etree.Element("input")
            input_el.set("type", "checkbox")
            if checked:
                input_el.set("checked", "checked")
            input_el.tail = tail
            parent.replace(el, input_el)
        elif name == "en-media":
            hash_val = el.get("hash", "")
            if hash_val:
                replace_with_text(el, ATTACHMENT_PLACEHOLDER.replace("{hash}",hash_val))
            else:
                replace_with_text(el, "[pièce jointe sans hash]")


def _to_markdown(html: str) -> str:
    """Convertit du HTML en Markdown via markdownify (convertisseur Evernote personnalisé)."""
    return _EvernoteMarkdownConverter(
        heading_style=md_lib.ATX,
        bullets="-",
        strip=["script", "style"],
    ).convert(html)


def _postprocess(md: str) -> str:
    """Normalise les sauts de ligne multiples et supprime les espaces de fin de ligne."""
    lines = md.splitlines()
    result = []
    blank_count = 0
    for line in lines:
        stripped = line.rstrip()
        if stripped == "":
            blank_count += 1
            if blank_count <= 2:
                result.append("")
        else:
            blank_count = 0
            result.append(stripped)
    return "\n".join(result).strip()
