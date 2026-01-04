"""
Standalone API server for testing without ComfyUI.
"""
import asyncio
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from aiohttp import web
from backend.agentx.api.server import create_agentx_routes
from backend.agentx.config import AgentConfig

async def main():
    app = web.Application()
    
    # Add AgentX routes
    routes = create_agentx_routes()
    app.add_routes(routes)
    
    # Serve static files from dist/agentx_web
    static_path = os.path.join(os.path.dirname(__file__), 'dist', 'agentx_web')
    if os.path.exists(static_path):
        app.router.add_static('/agentx_web/', static_path)
        # Also serve index.html at root
        async def index_handler(request):
            return web.FileResponse(os.path.join(static_path, 'index.html'))
        app.router.add_get('/', index_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8188)
    
    print("Starting standalone AgentX server at http://localhost:8188")
    print("API: http://localhost:8188/api/agentx/")
    print("UI: http://localhost:8188/agentx_web/")
    
    await site.start()
    
    # Keep running
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
