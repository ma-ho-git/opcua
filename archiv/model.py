"""
model.py – Model-Ebene des asynchronen OPC-UA-Clients
====================================================
Kapselt:
• Laden der Konfiguration
• Verbindungs-Management (asyncua.Client)
• Rekursives Browsen des Address-Space
• Lesen/Schreiben von Variablen
• Methodenaufrufe
Alle I/O-freien Geschäftsfunktionen liegen hier.

Autor: Dein Name, 2025
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from asyncua import Client, ua
from asyncua.common.node import Node


# ---------------------------------------------------------------------------#
# Hilfs-Strukturen
# ---------------------------------------------------------------------------#

@dataclass
class NodeEntry:
    """Repräsentiert einen Knoten im Address-Space-Menü."""
    node: Node
    node_class: ua.NodeClass
    path: List[str]
    parent_object: Optional[Node] = None  # Nur für Methoden nötig

# ---------------------------------------------------------------------------#
# Konfiguration
# ---------------------------------------------------------------------------#

def load_config(path: str | Path = "setup.txt") -> Dict[str, str]:
    """Liest eine sehr einfache Key=Value-Datei ein."""
    cfg: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, val = line.partition("=")
            cfg[key.strip().lower()] = val.strip()
    return cfg


# ---------------------------------------------------------------------------#
# Model-Klasse
# ---------------------------------------------------------------------------#

class OPCUAClientModel:
    """Stellt sämtliche domänenspezifische Logik bereit (keine Ein-/Ausgabe)."""

    def __init__(
        self,
        endpoint: str,
        security_policy: str = "None",
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.security_policy = security_policy
        self.username = username
        self.password = password

        # wird in connect() gesetzt
        self._client: Client | None = None
    
    


    # ---------- Kontext-Management ---------------------------------------- #
    async def __aenter__(self) -> "OPCUAClientModel":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

    # ---------- Verbindungs-Handling -------------------------------------- #
    async def connect(self) -> None:
        """Stellt die Verbindung zum OPC-UA-Server her."""
        self._client = Client(url=self.endpoint)
        if self.security_policy.lower() != "none":
            await self._client.set_security_string(self.security_policy)
        if self.username:
            await self._client.set_user(self.username, self.password or "") # type: ignore
        await self._client.connect()

    async def disconnect(self) -> None:
        """Schließt die OPC-UA-Verbindung."""
        if self._client:
            await self._client.disconnect()
            self._client = None

    # ---------- Address-Space-Browsing ----------------------------------- #
    async def collect_items(self) -> List[NodeEntry]:
        """Liest rekursiv alle Objekte/Variablen/Methoden unter Objects ein."""
        assert self._client is not None, "Client nicht verbunden"
        root = self._client.nodes.objects

        items: List[NodeEntry] = []
        stack: list[tuple[Node, list[str], Optional[Node]]] = [(root, [], None)]

        while stack:
            node, path, parent_obj = stack.pop()
            try:
                node_class: ua.NodeClass = await node.read_node_class()
                disp = await node.read_display_name()
                name = disp.Text or str(node.nodeid)
            except Exception:
                continue  # Unlesbare Knoten überspringen

            new_path = path + [name]
            if node_class in (
                ua.NodeClass.Object,
                ua.NodeClass.Variable,
                ua.NodeClass.Method,
            ):
                items.append(NodeEntry(node, node_class, new_path, parent_obj))

            # Kinder durchlaufen
            try:
                children = await node.get_children()
            except Exception:
                children = []

            for child in children:
                stack.append(
                    (
                        child,
                        new_path,
                        node if node_class == ua.NodeClass.Object else parent_obj,
                    )
                )

        # Alphabetisch sortieren → reproduzierbares Menü
        items.sort(key=lambda e: "/".join(e.path).lower())
        return items

    # ---------- Variablen-Operationen ------------------------------------ #
    async def read_variable(self, node: Node) -> tuple[ua.VariantType, object]:
        vtype = await node.read_data_type_as_variant_type()
        value = await node.get_value()
        return vtype, value

    async def write_variable(self, node: Node, vtype: ua.VariantType, text_value: str) -> None:
        variant_value = self._convert_string_to_variant(text_value, vtype)
        await node.set_value(variant_value)

    # ---------- Methoden-Aufruf ------------------------------------------ #
    async def call_method(
        self, parent: Node, method_node: Node, arg_texts: list[str]
    ) -> object:
        """Ruft eine OPC-UA-Methode auf und liefert das Ergebnis."""
        # Eingabe-Argument-Typen ermitteln
        inarg_node = await method_node.get_child("0:InputArguments")
        inargs: list[ua.Argument] = await inarg_node.get_value()

        if len(inargs) != len(arg_texts):
            raise ValueError("Argumentanzahl stimmt nicht")

        parsed_args: list[object] = []
        for arg, txt in zip(inargs, arg_texts, strict=True):
            parsed_args.append(
                self._convert_string_to_variant(txt, ua.VariantType(arg.DataType))
            )

        result = await self._client.uaclient.call_method(  # type: ignore[attr-defined]
            parent.nodeid, method_node.nodeid, *parsed_args
        )
        return result
    
    # ---------- Utilities ------------------------------------------------ #
    @staticmethod
    def _convert_string_to_variant(text: str, vtype: ua.VariantType):
        """Primitive Typ-Konvertierung (identisch zum Original-Skript)."""
        try:
            if vtype in (
                ua.VariantType.Int16,
                ua.VariantType.Int32,
                ua.VariantType.Int64,
                ua.VariantType.UInt16,
                ua.VariantType.UInt32,
                ua.VariantType.UInt64,
            ):
                return int(text)
            if vtype in (ua.VariantType.Float, ua.VariantType.Double):
                return float(text)
            if vtype == ua.VariantType.Boolean:
                return text.lower() in ("1", "true", "t", "yes", "y")
            return text  # Fallback: String
        except ValueError as ve:
            raise ValueError(f"Ungültiger Datentyp: {ve}") from ve
