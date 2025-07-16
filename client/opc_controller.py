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
        """Untermenue fuer eine Kategorie mit Navigation ueber Child-Nodes."""
        groups = self._group_by_child(items)
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
            choice = await self.view.choose_child_node(name, list(groups.keys()))
            if choice == "m":
                return
            if choice == "q":
                # Propagiere zum Abbruch
                raise SystemExit
            if not choice.isdigit():
                self.view.show_error("Bitte eine Zahl eingeben!")
                continue
            idx = int(choice) - 1
            keys = list(groups.keys())
            if not (0 <= idx < len(keys)):
                self.view.show_error("Nummer ausserhalb des Bereichs")
                continue
            child = keys[idx]
            await self._child_loop(child, groups[child])

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
    
    # ------------------------------------------------------------------
    def _group_by_child(self, items: List[NodeEntry]) -> Dict[str, List[NodeEntry]]:
        """Gruppiert Items nach dem ersten Child-Knoten hinter 'Objects'."""
        grouped: Dict[str, List[NodeEntry]] = defaultdict(list)
        for it in items:
            if len(it.path) > 1:
                key = it.path[1]
            else:
                key = it.path[0]
            grouped[key].append(it)
        ordered: Dict[str, List[NodeEntry]] = {}
        for k in sorted(grouped.keys()):
            ordered[k] = grouped[k]
        return ordered

    # ------------------------------------------------------------------
    async def _child_loop(self, child: str, items: List[NodeEntry]) -> None:
        """Zeigt die Items eines Child-Knotens an und ermoeglicht Auswahl."""
        while True:
            action = await self.view.show_category_items(child, items)
            if action == "m":
                return
            if action == "b":
                break
            if action == "q":
                raise SystemExit
            if not action.isdigit():
                self.view.show_error("Bitte eine Zahl eingeben!")
                continue
            idx = int(action) - 1
            if not (0 <= idx < len(items)):
                self.view.show_error("Nummer ausserhalb des Bereichs")
                continue
            entry = items[idx]
            if entry.node_class == ua.NodeClass.Method and entry.parent_object:
                await self._method_interaction(entry)
            else:
                self.view.show_info("/".join(entry.path))

    # ------------------------------------------------------------------
    async def _method_interaction(self, entry: NodeEntry) -> None:
        """Zeigt Methodendetails an und fuehrt sie auf Wunsch aus."""
        method_node = entry.node
        parent = entry.parent_object
        if parent is None:
            self.view.show_error("Parent-Objekt nicht gefunden")
            return
        try:
            inarg_node = await method_node.get_child("0:InputArguments")
            inargs: List[ua.Argument] = await inarg_node.get_value()
        except Exception:
            inargs = []

        arg_vals = await self.view.show_method_details("/".join(entry.path), inargs)
        try:
            result = await self.model.call_method(parent, method_node, arg_vals)
            self.view.show_method_result(result)
        except Exception as ex:
            self.view.show_error(str(ex))