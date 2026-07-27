import asyncio
import pull_prices

async def main():
    await pull_prices.pull_prices()


if __name__ == "__main__":
    asyncio.run(main())
