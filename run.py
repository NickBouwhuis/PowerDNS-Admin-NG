#!/usr/bin/env python3
import uvicorn

from powerdnsadmin.app import create_app
from powerdnsadmin.core.config import get_config

if __name__ == '__main__':
    app = create_app()
    config = get_config()
    uvicorn.run(
        app,
        host=config.get('BIND_ADDRESS', '127.0.0.1'),
        port=int(config.get('PORT', '9191')),
    )
