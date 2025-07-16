"""Asynchrone Model-Schicht fuer den OPC-UA-Client.

Diese Datei enthaelt die Logik zum Einlesen aller Knoten des Servers und
das Verbindungsmanagement. Alle I/O freien Funktionen werden hier
gekapselt. Die Klasse :class:`OPCUAClientModel` laesst sich asynchron
benutzen (``async with`` Kontextmanager).
"""

from __future__ import annotations

# import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from asyncua import Client, ua
from asyncua.common.node import Node


@dataclass
class NodeEntry:
    """Repraesentiert einen eingelesenen Knoten im Address Space."""

    node: Node
    node_class: ua.NodeClass
    path: List[str]
    parent_object: Optional[Node] = None


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


class OPCUAClientModel:
    """Model-Klasse: haelt Verbindung und stellt Browsing-Funktionen bereit."""

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
        self._client: Optional[Client] = None

    # ------------------------------------------------------------------
    async def __aenter__(self) -> "OPCUAClientModel":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.disconnect()

    # ------------------------------------------------------------------
    async def connect(self) -> None:
        """Verbindet zum OPC-UA Server."""
        self._client = Client(url=self.endpoint)
        if self.security_policy.lower() != "none":
            await self._client.set_security_string(self.security_policy)
        if self.username:
            await self._client.set_user(self.username, self.password or "")  # type: ignore
        await self._client.connect()

    async def disconnect(self) -> None:
        """Trennt die Verbindung."""
        if self._client:
            await self._client.disconnect()
            self._client = None
            
    # ------------------------------------------------------------------
    async def call_method(
        self,
        parent: Node,
        method_node: Node,
        arg_texts: List[str],
    ) -> object:
        """Fuehrt eine OPC-UA-Methode aus und gibt das Ergebnis zurueck."""
        assert self._client is not None, "Client nicht verbunden"
        try:
            inarg_node = await method_node.get_child("0:InputArguments")
            inargs: List[ua.Argument] = await inarg_node.get_value()
        except Exception:
            inargs = []

        if len(inargs) != len(arg_texts):
            raise ValueError("Argumentanzahl stimmt nicht")

        parsed_args = [
            self._convert_string_to_variant(txt, ua.VariantType(arg.DataType))
            for arg, txt in zip(inargs, arg_texts, strict=True)
        ]

        result = await self._client.uaclient.call_method(  # type: ignore[attr-defined]
            parent.nodeid,
            method_node.nodeid,
            *parsed_args,
        )
        return result

    # ------------------------------------------------------------------
    @staticmethod
    def _convert_string_to_variant(text: str, vtype: ua.VariantType) -> object:
        """Einfache Typumwandlung der Benutzereingabe."""
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
            return text
        except ValueError as exc:
            raise ValueError(f"Ungueltiger Wert fuer {vtype.name}: {text}") from exc

    # ------------------------------------------------------------------
    async def collect_items(self) -> List[NodeEntry]:
        """Liest rekursiv alle Knoten unterhalb von Objects ein."""
        assert self._client is not None, "Client nicht verbunden"
        root = self._client.nodes.objects
        items: List[NodeEntry] = []
        stack: List[Tuple[Node, List[str], Optional[Node]]] = [(root, [], None)]

        while stack:
            node, path, parent_obj = stack.pop()
            try:
                node_class: ua.NodeClass = await node.read_node_class()
                disp = await node.read_display_name()
                name = disp.Text or str(node.nodeid)
            except Exception:
                # Unlesbare Knoten ignorieren
                continue

            new_path = path + [name]
            if node_class in (
                ua.NodeClass.Object,
                ua.NodeClass.Variable,
                ua.NodeClass.Method,
            ):
                items.append(NodeEntry(node, node_class, new_path, parent_obj))

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

        # alphabetisch sortieren fuer ein reproduzierbares Menue
        items.sort(key=lambda e: "/".join(e.path).lower())
        return items