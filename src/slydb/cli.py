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

    local_index = subparsers.add_parser("index", help="Index Keynote files")
    local_index.add_argument("path", help="Path to the folder to index")
    local_index.add_argument(
        "-o", "--output", help="Path to write the index to", default=None
    )
    db_index = subparsers.add_parser(
        "index-dropbox", help="Index Keynote files in Dropbox folder"
    )
    db_index.add_argument("path", help="Path to the folder to index")
    meili = subparsers.add_parser("meili", help="Index Keynote files")
    meili.add_argument("records", help="Path to the records file")
    subparsers.add_parser("serve", help="Serve the indexed Keynote files")

    args = parser.parse_args()

    if args.command == "index":
        from .index import index_path

        index_path(args.path, args.output)
    elif args.command == "index-dropbox":
        index_path(args.path)
    elif args.command == "meili":
        from .meili import meili_main

        meili_main(args.records)

    elif args.command == "serve":
        from .app import main as app_main

        app_main()
    else:
        parser.print_help()
