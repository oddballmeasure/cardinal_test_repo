"""Start the notes HTTP service."""

import argparse

from notes.api import run_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve an in-memory notes API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
