import uvicorn

from backend.config import settings
from backend.web.app import app

if __name__ == '__main__':
    uvicorn.run(app, host=settings.web.host, port=settings.web.port)
