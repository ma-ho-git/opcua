"""Controller-Schicht fuer den OPC-UA-Client.

Diese Klasse verbindet Model und View. Sie verwaltet die Hauptschleife
und reagiert auf Benutzereingaben.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from asyncua import ua

from opc_model import OPCUAClientModel, NodeEntry, load_config
from opc_view import ConsoleView


class ClientController:
    """Kombiniert Model und View zu einer logischen Einheit."""

    def __init__(self, cfg_path: str = "setup.txt") -> None:
        cfg = load_config(cfg_path)
        endpoint = cfg.get("endpoint")
        if not endpoint:
            raise ValueError("endpoint in setup.txt nicht definiert!")

        self.model = OPCUAClientModel(
            endpoint=endpoint,
            security_policy=cfg.get("security_policy", "None"),
            username=cfg.get("username") or None,
            password=cfg.get("password") or None,
        )
        self.view = ConsoleView()

    # ------------------------------------------------------------------
    async def run(self) -> None:
        """Hauptlogik starten."""
        async with self.model:
            await self._main_loop()

    # ------------------------------------------------------------------
    async def _main_loop(self) -> None:
        """Zeigt das Hauptmenue und reagiert auf Eingaben."""
        while True:
            items = await self.model.collect_items()
            categories = self._group_by_class(items)
            choice = await self.view.show_main_menu(list(categories.keys()))

            if choice == "q":
                break
            if not choice.isdigit():
                self.view.show_error("Bitte eine Zahl eingeben!")
                continue

            idx = int(choice) - 1
            cats = list(categories.items())
            if not (0 <= idx < len(cats)):
                self.view.show_error("Nummer ausserhalb des Bereichs")
                continue

            cat_name, cat_items = cats[idx]
            await self._category_loop(cat_name, cat_items)

    # ------------------------------------------------------------------
    async def _category_loop(self, name: str, items: List[NodeEntry]) -> None:
        """Untermenue fuer eine Kategorie."""
        while True:
            action = await self.view.show_category_items(name, items)
            if action == "m":
                return
            if action == "q":
                # Propagiere zum Abbruch
                raise SystemExit
            # sonst erneut anzeigen

    # ------------------------------------------------------------------
    def _group_by_class(self, items: List[NodeEntry]) -> Dict[str, List[NodeEntry]]:
        grouped: Dict[str, List[NodeEntry]] = {}
        tmp: Dict[str, List[NodeEntry]] = defaultdict(list)
        for it in items:
            key = ua.NodeClass(it.node_class).name
            tmp[key].append(it)
        # sortiere nach Schluessel fuer stabile Ausgabe
        for k in sorted(tmp.keys()):
            grouped[k] = tmp[k]
        return grouped