import os
import pathlib
from typing import Iterable, Union

PathLike = Union[str, pathlib.Path]

def prepend_ld_library_path(*paths: PathLike,
                            check_exists: bool = True) -> str:
    """
    Präpendiert ein oder mehrere Verzeichnisse vor $LD_LIBRARY_PATH.

    Parameters
    ----------
    *paths : str | pathlib.Path
        Beliebig viele Pfade, die ganz vorne eingereiht werden sollen.
    check_exists : bool, default True
        Wenn True, werden nur existierende Verzeichnisse übernommen.

    Returns
    -------
    str
        Der neue LD_LIBRARY_PATH-String.
    """
    # Aktuelle Einträge zerlegen ⟶ Liste, leere Strings filtern
    current_parts: list[str] = [
        p for p in os.environ.get("LD_LIBRARY_PATH", "").split(":") if p
    ]

    # Neue Pfade normalisieren, in Strings umwandeln und optional filtern
    new_parts: list[str] = []
    for p in paths:
        p_str = str(pathlib.Path(p).expanduser())
        if check_exists and not pathlib.Path(p_str).is_dir():
            continue
        # Duplikate vermeiden: wenn bereits vorhanden, später aus current_parts entfernen
        new_parts.append(p_str)

    # Duplikate aus dem Rest entfernen
    remaining_parts = [p for p in current_parts if p not in new_parts]

    full_path = ":".join(new_parts + remaining_parts)
    os.environ["LD_LIBRARY_PATH"] = full_path
    return full_path