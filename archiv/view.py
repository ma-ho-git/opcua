"""
view.py – Konsolen-View für den OPC-UA-Client
============================================
Alle Ein-/Ausgabe liegt hier.  Getrennt von Logik & Daten (Model).
Farbige Darstellung über colorama (optional).
"""
from __future__ import annotations

import asyncio
import sys
from typing import List

from asyncua import ua
from asyncua.common.node import Node

try:
    from colorama import init as colorama_init, Fore, Style

    colorama_init()
    COLOR_OK = Fore.GREEN
    COLOR_ERR = Fore.RED
    COLOR_KEY = Fore.CYAN
    COLOR_RESET = Style.RESET_ALL
except ImportError:  # Fallback ohne Farbe
    COLOR_OK = COLOR_ERR = COLOR_KEY = COLOR_RESET = ""

# ---------------------------------------------------------------------------#
# Asynchrone Eingabe
# ---------------------------------------------------------------------------#
async def ainput(prompt: str = "") -> str:
    """Nicht-blockierende Variante von input()."""
    return await asyncio.get_event_loop().run_in_executor(None, input, prompt)


# ---------------------------------------------------------------------------#
# View-Klasse
# ---------------------------------------------------------------------------#
class ConsoleView:
    """Stellt alle rein visuellen Abläufe bereit."""

    # ---------- Menü ----------------------------------------------------- #
    async def choose_menu_entry(self, items: List["NodeEntry"]) -> str:
        """Zeigt das Hauptmenü, liefert Benutzerwahl (Index oder 'q')."""
        print("\n===== Address Space Browser =====")
        for idx, entry in enumerate(items, start=1):
            nclass_name = str(entry.node_class).split(".")[-1]
            print(f"{COLOR_KEY}{idx:3d}{COLOR_RESET}: {nclass_name:<8} /{'/'.join(entry.path)}")
        print("q  : Programm beenden")
        return (await ainput("Auswahl: ")).strip().lower()

    # ---------- Detail-Anzeige ------------------------------------------ #
    async def show_node_details(self, entry: "NodeEntry"):
        print(f"\n=== Details zu {'/'.join(entry.path)} ===")
        print(f"NodeId        : {entry.node.nodeid}")
        print(f"NodeClass     : {entry.node_class}")
        browse_name = await entry.node.read_browse_name()
        print(f"BrowseName    : {browse_name}")

    # ---------- Variable ------------------------------------------------- #
    async def read_variable_loop(self, vtype: ua.VariantType, value: object) -> str:
        print(f"\nAktueller Wert: {COLOR_OK}{value}{COLOR_RESET} (DataType: {vtype.name})")
        return (await ainput("[r] neu lesen, [w] wert setzen, [b] zurück: ")).strip().lower()

    async def prompt_new_value(self) -> str:
        return await ainput("Neuen Wert eingeben: ")

    # ---------- Methode -------------------------------------------------- #
    async def prompt_method_args(self, inargs: List[ua.Argument]) -> List[str]:
        arg_vals: List[str] = []
        for arg in inargs:
            prompt = f"{arg.Name} ({ua.VariantType(arg.DataType).name}) = "
            arg_vals.append(await ainput(prompt))
        return arg_vals

    async def show_method_result(self, result: object):
        print(f"{COLOR_OK}Ergebnis: {result}{COLOR_RESET}")

    # ---------- Allgemein ------------------------------------------------ #
    async def pause(self, message: str = "[Enter] zurück …"):
        await ainput(message)

    def show_error(self, msg: str):
        print(f"{COLOR_ERR}{msg}{COLOR_RESET}", file=sys.stderr)

    def show_info(self, msg: str):
        print(f"{COLOR_OK}{msg}{COLOR_RESET}")
