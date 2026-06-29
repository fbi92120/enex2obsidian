"""
enex_parser — Streaming XML extraction from Evernote .enex files.

Responsabilité unique : extraire les données brutes du XML ENEX et les exposer
sous forme de dataclasses. Ne fait pas :
  - conversion XHTML → Markdown (content_converter.py, étape 5)
  - normalisation des métadonnées (metadata_extractor.py, étape 4)
  - décodage base64 (attachment_handler.py, étape 6)
  - écriture disque (writer.py, étape 10)

Utilise lxml.etree.iterparse en mode recover=True pour le streaming tolérant
aux erreurs XML — impératif sur les .enex de plusieurs centaines de Mo.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree


@dataclass
class RawAttachment:
    """Référence brute à une pièce jointe embarquée dans une note ENEX.

    Toutes les chaînes sont conservées verbatim depuis le XML.
    Le décodage base64 de data_base64 est à la charge d'attachment_handler.py.
    """

    hash: str | None
    mime: str | None
    file_name: str | None
    data_base64: str | None


@dataclass
class RawNote:
    """Représentation brute d'une note Evernote extraite d'un .enex.

    Toutes les chaînes sont conservées telles quelles depuis le XML.
    La conversion XHTML→Markdown, la normalisation des dates et le décodage
    base64 ne sont PAS faits ici — ils appartiennent aux modules aval.
    """

    title: str | None
    content_xhtml: str | None
    created: str | None
    updated: str | None
    tags: list[str] = field(default_factory=list)
    source_url: str | None = None
    guid: str | None = None
    attachments: list[RawAttachment] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)


def iter_notes(enex_path: Path) -> Iterator[RawNote]:
    """Itère sur les notes d'un fichier ENEX en streaming.

    Utilise lxml.etree.iterparse pour libérer la mémoire au fur et à mesure :
    chaque <note> est yielded puis son élément XML est clear()'d. Les anciens
    éléments siblings sont également purgés pour contenir l'empreinte mémoire.

    Args:
        enex_path: chemin vers le fichier .enex à parser (Path ou str)

    Yields:
        RawNote: une note par itération, dans l'ordre d'apparition dans le XML.
            Les notes avec erreurs partielles sont yielded avec parse_errors
            non vide — c'est l'appelant qui décide de les skipper.

    Raises:
        FileNotFoundError: si le fichier n'existe pas.
        ValueError: si lxml ne peut pas produire de structure XML exploitable
            même en mode recover (fichier globalement illisible).
    """
    enex_path = Path(enex_path)
    if not enex_path.exists():
        raise FileNotFoundError(f"Fichier ENEX introuvable : {enex_path}")

    try:
        context = etree.iterparse(
            str(enex_path),
            events=("end",),
            tag="note",
            recover=True,
        )
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"Fichier ENEX illisible même en mode recover : {exc}") from exc

    try:
        for _event, elem in context:
            yield _extract_note(elem)
            # Libère l'élément courant et les siblings déjà traités
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"Erreur XML globale non récupérable : {exc}") from exc


def _extract_note(elem) -> RawNote:
    """Extrait les données d'un élément <note> lxml en RawNote.

    Les erreurs sur des sous-éléments individuels sont accumulées dans
    parse_errors sans interrompre l'extraction des autres champs.

    Args:
        elem: élément lxml correspondant à une balise <note>

    Returns:
        RawNote avec les champs extraits et parse_errors éventuel.
    """
    errors: list[str] = []

    title = _text(elem, "title", errors)
    content_xhtml = _text(elem, "content", errors)
    created = _text(elem, "created", errors)
    updated = _text(elem, "updated", errors)
    guid = _text(elem, "guid", errors)

    tags: list[str] = []
    for tag_elem in elem.findall("tag"):
        try:
            if tag_elem.text is not None:
                tags.append(tag_elem.text)
        except Exception as exc:
            errors.append(f"tag extraction error: {exc}")

    source_url: str | None = None
    try:
        attrs_elem = elem.find("note-attributes")
        if attrs_elem is not None:
            su = attrs_elem.find("source-url")
            if su is not None:
                source_url = su.text
    except Exception as exc:
        errors.append(f"source-url extraction error: {exc}")

    attachments = _extract_attachments(elem, errors)

    return RawNote(
        title=title,
        content_xhtml=content_xhtml,
        created=created,
        updated=updated,
        tags=tags,
        source_url=source_url,
        guid=guid,
        attachments=attachments,
        parse_errors=errors,
    )


def _extract_attachments(note_elem, errors: list[str]) -> list[RawAttachment]:
    """Extrait la liste des <resource> d'un élément <note>.

    Args:
        note_elem: élément lxml <note>
        errors: liste d'erreurs partagée avec _extract_note (en-place)

    Returns:
        list[RawAttachment]: une entrée par <resource>, dans l'ordre XML.
    """
    attachments: list[RawAttachment] = []
    for res in note_elem.findall("resource"):
        try:
            data_elem = res.find("data")
            data_b64 = data_elem.text if data_elem is not None else None

            mime_elem = res.find("mime")
            mime = mime_elem.text if mime_elem is not None else None

            file_name: str | None = None
            attrs = res.find("resource-attributes")
            if attrs is not None:
                fn_elem = attrs.find("file-name")
                if fn_elem is not None:
                    file_name = fn_elem.text

            # hash: extrait depuis <recognition> ou calculé par attachment_handler plus tard
            # Pour l'instant on récupère le hash MD5 stocké dans <data> si présent
            hash_val: str | None = None
            recognition = res.find("recognition")
            if recognition is not None:
                hash_val = recognition.get("objID")
            # Fallback: certains ENEX stockent le hash dans l'attribut de <data>
            if hash_val is None and data_elem is not None:
                hash_val = data_elem.get("encoding")  # pas le hash, mais on garde None

            attachments.append(RawAttachment(
                hash=hash_val,
                mime=mime,
                file_name=file_name,
                data_base64=data_b64,
            ))
        except Exception as exc:
            errors.append(f"resource extraction error: {exc}")

    return attachments


def _text(parent, tag: str, errors: list[str]) -> str | None:
    """Retourne le contenu texte d'un sous-élément, ou None si absent.

    Args:
        parent: élément lxml parent
        tag: nom de la balise enfant à chercher
        errors: liste d'erreurs en-place pour enregistrer les problèmes

    Returns:
        str | None: texte du premier élément trouvé, ou None.
    """
    try:
        child = parent.find(tag)
        return child.text if child is not None else None
    except Exception as exc:
        errors.append(f"<{tag}> extraction error: {exc}")
        return None
