import asyncio
from archiv.controller import ClientController

if __name__ == "__main__":
    try:
        asyncio.run(ClientController().run())
    except KeyboardInterrupt:
        print("\nAbbruch durch Benutzer.")
