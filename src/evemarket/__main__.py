import argparse
import asyncio

from evemarket.jobs.assets import pull_assets
from evemarket.jobs.login import login
from evemarket.jobs.prices import pull_prices


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evemarket", description="EVE Online market and asset pulls.")
    commands = parser.add_subparsers(dest="command")
    _ = commands.add_parser("login", help="Authorise a character via EVE SSO and store its refresh token.")
    _ = commands.add_parser("prices", help="Pull /markets/prices into DuckDB.")
    assets = commands.add_parser("assets", help="Pull a character's assets into DuckDB.")
    _ = assets.add_argument(
        "--character-id",
        type=int,
        default=None,
        help="Character to pull; defaults to the most recently authorised.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    match args.command:
        case "login":
            asyncio.run(login())
        case "prices":
            asyncio.run(pull_prices())
        case "assets":
            asyncio.run(pull_assets(args.character_id))
        case _:
            parser.print_help()


if __name__ == "__main__":
    main()
