"""
enex_parser — Parse Evernote .enex XML files and extract raw note data.

Reads .enex files using lxml in recover=True mode for tolerance on malformed XML.
Streams notes one by one via iterparse to avoid loading multi-hundred-MB files
entirely into RAM.
"""

from typing import Iterator


def parse_enex(enex_path: str) -> Iterator[dict]:
    """
    Parse a .enex file and yield raw note data dicts one at a time.

    Uses lxml iterparse for streaming — safe on large .enex files.
    Malformed individual notes are yielded with a parse_error flag rather than
    raising an exception (per constitution rule 1).

    Args:
        enex_path (str): absolute path to the .enex file

    Yields:
        dict with keys:
            - title (str|None)
            - created (str|None): raw Evernote date string e.g. "20240315T092300Z"
            - updated (str|None): raw Evernote date string
            - tags (list[str]): may be empty
            - source_url (str|None)
            - guid (str|None)
            - content (str|None): raw XHTML content string (the CDATA value)
            - resources (list[dict]): raw resource/attachment data
            - parse_error (str|None): error message if note failed to parse

    Raises:
        OSError: if enex_path does not exist or is not readable.
        lxml.etree.XMLSyntaxError: if the file-level XML is globally malformed
            and lxml recover=True cannot produce any usable structure.
    """
    raise NotImplementedError("Étape 3 de la séquence")


def _extract_resource(resource_element) -> dict:
    """
    Extract raw attachment data from a <resource> XML element.

    Args:
        resource_element: lxml element for <resource>

    Returns:
        dict with keys:
            - data (str|None): raw base64-encoded content
            - mime (str|None): MIME type e.g. "application/pdf"
            - file_name (str|None): original filename from <resource-attributes>
            - hash (str|None): MD5 hex hash for matching with <en-media> tags
            - width (int|None): image width if present
            - height (int|None): image height if present
    """
    raise NotImplementedError("Étape 3 de la séquence")
