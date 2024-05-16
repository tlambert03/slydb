import argparse


def main():
    """Argument parser for the command-line interface.

    this cli has two subcommands, `index` and `serve`.
    `index` takes a path to a folder (doesn't need to exist) and indexes all Keynote
    files in that folder.
    `serve` starts a web server to view the indexed Keynote files.
    """

    parser = argparse.ArgumentParser(description="Index and serve Keynote files")
    subparsers = parser.add_subparsers(dest="command")

    index_parser = subparsers.add_parser("index", help="Index Keynote files")
    index_parser.add_argument("path", help="Path to the folder to index")
    subparsers.add_parser("serve", help="Serve the indexed Keynote files")

    args = parser.parse_args()

    if args.command == "index":
        from .dbx import index_folder

        index_folder(args.path)
    elif args.command == "serve":
        from .app import main as app_main

        app_main()
    else:
        parser.print_help()
