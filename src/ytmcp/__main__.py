"""Entry point: python -m ytmcp."""

import sys

from ytmcp.config import ConfigError, load_settings
from ytmcp.server import build_server


def main() -> None:
    """Start the server."""
    try:
        settings = load_settings()
        server = build_server(settings)
    except ConfigError as err:
        sys.stderr.write(f"Configuration error: {err}\n")
        sys.stderr.flush()
        raise SystemExit(2) from None

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
