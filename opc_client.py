# asyncua_client.py – Interaktiver OPC UA‑Client mit asyncio
# =========================================================
# Dieser Client verbindet sich asynchron zu einem OPC UA‑Server (python‑opcua/asyncua),
# liest die komplette Address Space‑Hierarchie unterhalb des Objects‑Ordners ein
# und stellt sie als nummeriertes Menü dar. Der Benutzer kann ein Objekt, eine
# Variable oder eine Methode per Integer auswählen und anschließend passende
# Aktionen durchführen (Variable lesen/setzen, Methode aufrufen). Das Programm
# läuft solange, bis der Benutzer "q" eingibt.
#
# Ablauf:
#   1. Setup‑Datei (setup.txt) einlesen → Verbindungsparameter.
#   2. Asynchrone Verbindung aufbauen (Security optional).
#   3. Rekursiv browsen, Menü ausgeben.
#   4. Benutzerinteraktion in einer Endlosschleife.
#
# Benötigte Pakete: asyncua (>=1.3), colorama (optionale Farb‑Ausgabe).


import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from asyncua import Client, ua
from asyncua.common.node import Node

try:
    from colorama import init as colorama_init, Fore, Style

    colorama_init()
    COLOR_OK = Fore.GREEN
    COLOR_ERR = Fore.RED
    COLOR_KEY = Fore.CYAN
    COLOR_RESET = Style.RESET_ALL
except ImportError:
    # Fallback ohne Farbausgabe
    COLOR_OK = COLOR_ERR = COLOR_KEY = COLOR_RESET = ""

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def load_config(path: str | Path = "setup.txt") -> Dict[str, str]:
    """Sehr einfache Key=Value‑Konfig ohne [Abschnitt]‑Syntax."""
    cfg: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf‑8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, _, val = line.partition("=")
                cfg[key.strip().lower()] = val.strip()
    except FileNotFoundError:
        print(f"{COLOR_ERR}Konfigurationsdatei '{path}' nicht gefunden.{COLOR_RESET}")
        sys.exit(1)
    return cfg

async def ainput(prompt: str = "") -> str:
    """Asynchrone Variante von input()."""
    return await asyncio.get_event_loop().run_in_executor(None, input, prompt)

async def collect_items(root: Node) -> List[Tuple[Node, ua.NodeClass, List[str], Optional[Node]]]:
    """Recursively collect all Objects, Variables and Methods under *root*.

    Returns list of tuples (node, node_class, hierarchical_path, parent_object).
    For methods, *parent_object* is needed for call_method()."""

    items: List[Tuple[Node, ua.NodeClass, List[str], Optional[Node]]] = []
    stack: List[Tuple[Node, List[str], Optional[Node]]] = [(root, [], None)]

    while stack:
        node, path, parent = stack.pop()
        try:
            node_class: ua.NodeClass = await node.read_node_class()
            disp = await node.read_display_name()
            name = disp.Text or str(node.nodeid)
        except Exception:
            # Skip nodes we cannot read
            continue

        new_path = path + [name]

        if node_class in (ua.NodeClass.Object, ua.NodeClass.Variable, ua.NodeClass.Method):
            items.append((node, node_class, new_path, parent))

        # Browse children – but avoid endless loops by filtering ReferenceType
        try:
            children = await node.get_children()
        except Exception:
            children = []

        for child in children:
            stack.append((child, new_path, node if node_class == ua.NodeClass.Object else parent))

    # Sort alphabetically by path for nicer menu
    items.sort(key=lambda t: "/".join(t[2]).lower())
    return items

# ---------------------------------------------------------------------------
# Interaktive Aktionen
# ---------------------------------------------------------------------------

async def interact_with_variable(node: Node):
    while True:
        try:
            value = await node.get_value()
            vtype = await node.read_data_type_as_variant_type()
            print(f"\nAktueller Wert: {COLOR_OK}{value}{COLOR_RESET} (DataType: {vtype.name})")
        except Exception as ex:
            print(f"{COLOR_ERR}Lesefehler: {ex}{COLOR_RESET}")
            return

        choice = (await ainput("[r] neu lesen, [w] wert setzen, [b] zurück: ")).strip().lower()
        if choice == "b":
            return
        elif choice == "r":
            continue
        elif choice == "w":
            new_val_str = await ainput("Neuen Wert eingeben: ")
            try:
                new_val = _convert_string_to_variant(new_val_str, vtype)
                await node.set_value(new_val)
                print(f"{COLOR_OK}Wert gesetzt.{COLOR_RESET}")
            except Exception as ex:
                print(f"{COLOR_ERR}Schreibfehler: {ex}{COLOR_RESET}")
        else:
            print("Ungültige Eingabe.")

async def interact_with_method(client: Client, node: Node, parent: Node):
    try:
        inargs: List[ua.Argument] = []
        try:
            inarg_node = await node.get_child("0:InputArguments")
            inargs = await inarg_node.get_value()
        except Exception:
            pass

        print("\nMethode aufrufen:")
        arg_values: List = []
        for arg in inargs:
            prompt = f"{arg.Name} ({ua.VariantType(arg.DataType).name}) = "
            user_in = await ainput(prompt)
            arg_values.append(_convert_string_to_variant(user_in, ua.VariantType(arg.DataType)))

        # Call method
        try:
            result = await client.uaclient.call_method(parent.nodeid, node.nodeid, *arg_values) # type: ignore
            print(f"{COLOR_OK}Ergebnis: {result}{COLOR_RESET}")
        except Exception as ex:
            print(f"{COLOR_ERR}Call fehlgeschlagen: {ex}{COLOR_RESET}")
    finally:
        await ainput("[Enter] zurück zum Hauptmenü …")

async def interact(client: Client):
    root = client.nodes.objects
    while True:
        items = await collect_items(root)
        print("\n===== Address Space Browser =====")
        for idx, (_, nclass, path, _) in enumerate(items, start=1):
            nclass_name = str(nclass).split(".")[-1]
            print(f"{COLOR_KEY}{idx:3d}{COLOR_RESET}: {nclass_name:<8} /{'/'.join(path)}")
        print("q  : Programm beenden")

        choice = (await ainput("Auswahl: ")).strip().lower()
        if choice == "q":
            break
        if not choice.isdigit():
            print("Bitte eine Nummer eingeben!")
            continue

        index = int(choice) - 1
        if index < 0 or index >= len(items):
            print("Nummer außerhalb des Bereichs.")
            continue

        node, nclass, path, parent = items[index]
        print(f"\n=== Details zu {'/'.join(path)} ===")
        print(f"NodeId        : {node.nodeid}")
        print(f"NodeClass     : {nclass}")
        browse_name = await node.read_browse_name()
        print(f"BrowseName    : {browse_name}")

        if nclass == ua.NodeClass.Variable:
            await interact_with_variable(node)
        elif nclass == ua.NodeClass.Method and parent is not None:
            await interact_with_method(client, node, parent)
        else:
            await ainput("[Enter] zurück zum Hauptmenü …")

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _convert_string_to_variant(text: str, vtype: ua.VariantType):
    """Primitive Konvertierung von Eingabetext zu passender Python‑/UA‑Variante."""
    try:
        if vtype in (ua.VariantType.Int16, ua.VariantType.Int32, ua.VariantType.Int64,
                     ua.VariantType.UInt16, ua.VariantType.UInt32, ua.VariantType.UInt64):
            return int(text)
        if vtype in (ua.VariantType.Float, ua.VariantType.Double):
            return float(text)
        if vtype == ua.VariantType.Boolean:
            return text.lower() in ("1", "true", "t", "yes", "y")
        # Fallback: treat as string
        return text
    except ValueError as ve:
        raise ValueError(f"Ungültiger Datentyp: {ve}") from ve

# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

async def main():
    cfg = load_config()
    endpoint = cfg.get("endpoint")
    if not endpoint:
        print("endpoint in setup.txt nicht definiert!")
        return
    security_policy = cfg.get("security_policy", "None")

    print(f"Verbinde zu {endpoint} …")
    async with Client(url=endpoint) as client:
        if security_policy.lower() != "none":
            await client.set_security_string(security_policy)
        # Username/Password
        if cfg.get("username"):
            await client.set_user(cfg["username"], cfg.get("passwo rd", "")) # type: ignore
        print(f"{COLOR_OK}Verbunden!{COLOR_RESET}")
        await interact(client)
    print("Verbindung geschlossen. Auf Wiedersehen!")

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAbbruch durch Benutzer.")