"""Console-basierte View fuer den OPC-UA-Client.

Alle Ein- und Ausgaben sowie die Benutzerinteraktion werden hier
definiert. Farbige Ausgaben sind optional, abhhaengig von colorama.
"""

from __future__ import annotations

import asyncio
from typing import List

from opc_model import NodeEntry
from asyncua import ua

try:
    from colorama import Fore, Style, init as colorama_init

    colorama_init()
    COLOR_KEY = Fore.CYAN
    COLOR_OK = Fore.GREEN
    COLOR_ERR = Fore.RED
    COLOR_RESET = Style.RESET_ALL
except Exception:  # Fallback ohne Farbe
    COLOR_KEY = COLOR_OK = COLOR_ERR = COLOR_RESET = ""


async def ainput(prompt: str = "") -> str:
    """Nicht-blockierende Variante von input()."""
    return await asyncio.get_event_loop().run_in_executor(None, input, prompt)


class ConsoleView:
    """Stellt alle Konsolendialoge bereit."""

    async def show_main_menu(self, categories: List[str]) -> str:
        """Zeigt das Hauptmenue mit allen Kategorien."""
        print("\n===== Hauptmenue =====")
        for idx, cat in enumerate(categories, start=1):
            print(f"{COLOR_KEY}{idx}{COLOR_RESET}: {cat}")
        print("q: Programm beenden")
        return (await ainput("Auswahl: ")).strip().lower()

    async def show_category_items(self, cat_name: str, items: List[NodeEntry]) -> str:
        """Zeigt alle Items einer Kategorie."""
        print(f"\n=== {cat_name} ===")
        for idx, entry in enumerate(items, start=1):
            print(f"{COLOR_KEY}{idx}{COLOR_RESET}: {'/'.join(entry.path)}")
        print("b: zurueck")
        print("m: zurueck zum Hauptmenue")
        print("q: Programm beenden")
        return (await ainput("Eingabe: ")).strip().lower()
    
    async def choose_child_node(self, cat_name: str, children: List[str]) -> str:
        """Waehlt einen Child-Knoten innerhalb einer Kategorie aus."""
        print(f"\n=== {cat_name} Child-Nodes ===")
        for idx, name in enumerate(children, start=1):
            print(f"{COLOR_KEY}{idx}{COLOR_RESET}: {name}")
        print("m: zurueck zum Hauptmenue")
        print("q: Programm beenden")
        return (await ainput("Auswahl: ")).strip().lower()

    async def show_method_details(self, path: str, inargs: List[ua.Argument]) -> List[str]:
        """Zeigt Informationen zu einer Methode und fragt Parameter ab."""
        print(f"\n+++ Methode {path} +++")
        if not inargs:
            print("Keine Eingabeargumente")
            await ainput("[Enter] ausfuehren")
            return []
        args: List[str] = []
        for arg in inargs:
            vtype = ua.datatype_to_varianttype(arg.DataType)
            prompt = f"{arg.Name} ({vtype.name}) = "
            args.append(await ainput(prompt))
        return args

    def show_method_result(self, result: object) -> None:
        print(f"{COLOR_OK}Ergebnis: {result}{COLOR_RESET}")    

    def show_info(self, text: str) -> None:
        print(f"{COLOR_OK}{text}{COLOR_RESET}")

    def show_error(self, text: str) -> None:
        print(f"{COLOR_ERR}{text}{COLOR_RESET}")