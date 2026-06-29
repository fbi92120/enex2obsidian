"""
notebook_selector — Parse carnets-a-migrer.txt and return the list of notebook names.

Responsabilité unique : lire le fichier de configuration listant les carnets à migrer
et retourner leurs noms dans l'ordre du fichier.

Ne fait pas :
  - Résolution des .enex correspondants sur disque (orchestrateur)
  - Validation que les carnets existent (orchestrateur)
  - Filtrage CLI --carnet (orchestrateur)
  - Déduplication (orchestrateur, si besoin métier)
"""

from pathlib import Path


def load_notebook_list(path: Path) -> list[str]:
    """Lit carnets-a-migrer.txt et retourne la liste ordonnée des carnets.

    Format du fichier :
    - Un nom de carnet par ligne
    - Lignes commençant par # (après strip) : commentaires, ignorées
    - Lignes vides ou ne contenant que des espaces : ignorées
    - Espaces en début/fin de ligne strippés ; espaces internes préservés
    - Doublons conservés (la déduplication est la responsabilité de l'orchestrateur)
    - Pas de commentaires inline : "Carnet # note" est un nom valide

    Args:
        path: chemin vers carnets-a-migrer.txt

    Returns:
        Liste des noms de carnets dans l'ordre du fichier.
        Liste vide si le fichier ne contient que des commentaires ou est vide.

    Raises:
        FileNotFoundError: si le fichier n'existe pas
        UnicodeDecodeError: si le fichier n'est pas lisible en UTF-8
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        result.append(stripped)
    return result
