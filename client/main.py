"""Einstiegspunkt fuer den OPC-UA-Client."""

import asyncio

from opc_controller import ClientController


def main() -> None:
    try:
        asyncio.run(ClientController().run())
    except SystemExit:
        # Durch Controller ausgeloestes Ende
        pass
    except KeyboardInterrupt:
        print("\nAbbruch durch Benutzer")


if __name__ == "__main__":
    main()