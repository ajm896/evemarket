import asyncio

from evemarket.jobs.prices import pull_prices


def main() -> None:
    asyncio.run(pull_prices())


if __name__ == "__main__":
    main()
