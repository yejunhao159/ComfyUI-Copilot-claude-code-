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
from backend.agentx.api.server_v2 import create_agentx_routes_v2
from backend.agentx.config import AgentConfig

async def main():
    app = web.Application()
    
    # Add AgentX routes (V2)
    routes = create_agentx_routes_v2()
    app.add_routes(routes)
    
    # Serve static files from dist/agentx_web
    static_path = os.path.join(os.path.dirname(__file__), 'dist', 'agentx_web')
    if os.path.exists(static_path):
        app.router.add_static('/agentx_web/', static_path)
        # Also serve index.html at root
        async def index_handler(request):
            return web.FileResponse(os.path.join(static_path, 'index.html'))
        app.router.add_get('/', index_handler)
    
    port = int(os.environ.get('AGENTX_PORT', 8199))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', port)

    print(f"Starting standalone AgentX server at http://localhost:{port}")
    print(f"API: http://localhost:{port}/api/agentx/")
    print(f"UI: http://localhost:{port}/agentx_web/")
    
    await site.start()
    
    # Keep running
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
