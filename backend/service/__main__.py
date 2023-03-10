import asyncio
import logging

from backend.log import init_logging
from backend.service.app_container import AppContainer


async def main() -> None:
    init_logging()
    logger = logging.getLogger(__name__)
    app = AppContainer()

    try:
        await app.run()
    except Exception as e:
        logger.exception(f"Ошибка сервера: {e}")


if __name__ == '__main__':
    asyncio.run(main())
