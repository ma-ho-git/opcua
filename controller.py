"""
controller.py – Controller der MVC-Architektur
=============================================
Vermittelt zwischen Model und View und hält die Haupt-State-Maschine.
"""
from __future__ import annotations

import asyncio
from typing import List

from asyncua import ua

from model import OPCUAClientModel, NodeEntry, load_config
from view import ConsoleView


class ClientController:
    """Kombiniert View + Model → Ablauflogik."""

    def __init__(self, cfg_path: str | None = None) -> None:
        self.cfg = load_config(cfg_path or "setup.txt")
        endpoint = self.cfg.get("endpoint")
        if not endpoint:
            raise ValueError("endpoint in setup.txt nicht definiert!")

        self.model = OPCUAClientModel(
            endpoint=endpoint,
            security_policy=self.cfg.get("security_policy", "None"),
            username=self.cfg.get("username"),
            password=self.cfg.get("password"),
        )
        self.view = ConsoleView()

    # ------------------------------------------------------------------- #
    async def run(self):
        """Hauptroutine: Gerät verbinden, Browser-Loop ausführen."""
        async with self.model:  # → Verbindung steht
            self.view.show_info("Verbunden!")
            await self._main_loop()

        self.view.show_info("Verbindung geschlossen. Auf Wiedersehen!")

    # ------------------------------------------------------------------- #
    async def _main_loop(self):
        while True:
            items = await self.model.collect_items()
            choice = await self.view.choose_menu_entry(items)

            if choice == "q":
                break
            if not choice.isdigit():
                self.view.show_error("Bitte eine Nummer eingeben!")
                continue

            index = int(choice) - 1
            if not (0 <= index < len(items)):
                self.view.show_error("Nummer außerhalb des Bereichs.")
                continue

            await self._handle_selection(items[index])

    # ------------------------------------------------------------------- #
    async def _handle_selection(self, entry: NodeEntry) -> None:
        await self.view.show_node_details(entry)

        if entry.node_class == ua.NodeClass.Variable:
            await self._variable_interaction(entry.node)
        elif entry.node_class == ua.NodeClass.Method and entry.parent_object:
            await self._method_interaction(entry)
        else:
            await self.view.pause()

    # ----------------------- Variable ---------------------------------- #
    async def _variable_interaction(self, node):
        while True:
            vtype, value = await self.model.read_variable(node)
            action = await self.view.read_variable_loop(vtype, value)

            if action == "b":
                return
            if action == "r":
                continue
            if action == "w":
                new_val = await self.view.prompt_new_value()
                try:
                    await self.model.write_variable(node, vtype, new_val)
                    self.view.show_info("Wert gesetzt.")
                except Exception as ex:
                    self.view.show_error(f"Schreibfehler: {ex}")
            else:
                self.view.show_error("Ungültige Eingabe.")

    # ----------------------- Methode ----------------------------------- #
    async def _method_interaction(self, entry: NodeEntry):
        method_node = entry.node
        parent = entry.parent_object
        try:
            # Eingabe-Argumente anzeigen + abfragen
            inarg_node = await method_node.get_child("0:InputArguments")
            inargs: List[ua.Argument] = await inarg_node.get_value()
        except Exception:
            inargs = []

        arg_texts = await self.view.prompt_method_args(inargs)

        try:
            result = await self.model.call_method(parent, method_node, arg_texts)
            await self.view.show_method_result(result)
        except Exception as ex:
            self.view.show_error(f"Call fehlgeschlagen: {ex}")
        finally:
            await self.view.pause()
