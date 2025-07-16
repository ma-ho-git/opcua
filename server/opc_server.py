"""
opc_server.py
=============

Startet einen einfachen OPC-UA-Server, der dieselben Nodes, Variablen
und Methoden bereitstellt wie das ursprüngliche Notebook `opc_ua_server.ipynb`.

• Endpoint     : opc.tcp://127.0.0.1:4848  
• Namespace    : "OPCUA_SERVER"
• Variablen    : Temperature, Pressure, Flow  (schreib-/lesbar)
                 folder_test/Flow2           (schreib-/lesbar)
                 TargetTemperature           (nur via Methode änderbar)
• Methoden     : IsEven(Int64)   -> Bool
                 SetTargetTemperature(Double)  – validiert 0-100 °C

Mit Strg +C beenden.
"""

from __future__ import annotations

import argparse
import signal
import sys
from time import sleep
from typing import List

from opcua import ua, uamethod, Server


class DemoOpcServer:
    """Kapselt den kompletten Server-Lifecycle."""

    def __init__(self, endpoint: str = "opc.tcp://127.0.0.1:4848") -> None:
        self.server = Server()
        self.server.set_endpoint(endpoint)
        self.server.set_server_name("OPC-UA Demo Server")

        # ---------- Address-Space -------------------------------------------------
        self.idx = self.server.register_namespace("OPCUA_SERVER")
        objects = self.server.get_objects_node()

        # Haupt-Objekt
        self.root_obj = objects.add_object(self.idx, "DA_UA")

        # Variablen unterhalb des Haupt-Objekts
        self.temp = self.root_obj.add_variable(
            self.idx, "Temperature", 0.0, ua.VariantType.Float
        )
        self.press = self.root_obj.add_variable(
            self.idx, "Pressure", 0.0, ua.VariantType.Float
        )
        self.flow = self.root_obj.add_variable(
            self.idx, "Flow", 0.0, ua.VariantType.Float
        )

        # Variablen beschreibbar machen, damit der MVC-Client sie setzen kann
        for var in (self.temp, self.press, self.flow):
            var.set_writable()

        # Unterordner + weitere Variable
        folder = self.root_obj.add_folder(self.idx, "folder_test")
        self.flow2 = folder.add_variable(
            self.idx, "Flow2", 0.0, ua.VariantType.Float
        )
        self.flow2.set_writable()

        # ---------- Methoden ------------------------------------------------------
        # 1) Einfache Beispiel-Methode
        @uamethod
        def is_even(parent, value: int) -> bool:  # noqa: N802 (OPC-UA Signatur)
            return value % 2 == 0

        self.root_obj.add_method(
            self.idx,
            "IsEven",
            is_even,
            [ua.VariantType.Int64],
            [ua.VariantType.Boolean],
        )

        # 2) Methode zum sicheren Ändern einer Ziel-Temperatur
        self.target = self.root_obj.add_variable(
            self.idx, "TargetTemperature", 20.0, ua.VariantType.Double
        ) 

        @uamethod
        def set_target_temperature(parent, value: float) -> ua.StatusCode:  # noqa: N802
            if not (0.0 <= value <= 100.0):
                return ua.StatusCode(ua.StatusCodes.BadOutOfRange)
            self.target.set_value(value)
            return ua.StatusCode(ua.StatusCodes.Good)

        self.root_obj.add_method(
            self.idx,
            "SetTargetTemperature",
            set_target_temperature,
            [ua.VariantType.Double],
            [],
        )

    # --------------------------------------------------------------------- #
    def start(self) -> None:
        """Server starten und Hintergrund-Loop für Demo-Daten anstoßen."""
        self.server.start()
        print(f"Server läuft auf {self.server.endpoint.geturl()} - zum Beenden: ctrl+c ")
        self._run_main_loop()

    def stop(self, *_: object) -> None:
        """Server herunterfahren."""
        print("\nStoppe Server …")
        self.server.stop()
        sys.exit(0)

    # --------------------------------------------------------------------- #
    def _run_main_loop(self) -> None:
         """Aktualisiert die Demo-Variablen bis zum Abbruch (Strg +C)."""
         i = 0
         while True:
             #self.temp.set_value(i * 0.25, ua.VariantType.Float)
             #self.press.set_value(i * 0.26, ua.VariantType.Float)
             #self.flow.set_value(i * 0.27, ua.VariantType.Float)
             #self.flow2.set_value(i * 0.15, ua.VariantType.Float)
             sleep(1)
             i += 1


# ------------------------------------------------------------------------- #
def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Startet den OPC-UA-Demo-Server.",
    )
    parser.add_argument(
        "--endpoint",
        default="opc.tcp://127.0.0.1:4848",
        help="OPC-UA Endpoint (Standards: opc.tcp://<host>:4848)",
    )
    args = parser.parse_args(argv)

    srv = DemoOpcServer(endpoint=args.endpoint)

    # Ctrl+C / SIGINT abfangen
    signal.signal(signal.SIGINT, srv.stop)
    signal.signal(signal.SIGTERM, srv.stop)

    srv.start()  # blockiert bis Abbruch


if __name__ == "__main__": 
    main()
