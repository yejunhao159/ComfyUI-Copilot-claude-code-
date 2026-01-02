#!/usr/bin/env python3
"""
AgentX CLI

Command-line interface for running the AgentX API server.
"""

import sys
import logging
import argparse
from aiohttp import web
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.agentx.config import AgentConfig
from backend.agentx.api import create_app


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AgentX API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--log-level", default="INFO", help="Log level")

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Load configuration
    try:
        config = AgentConfig.from_env()
        config.validate()
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Create and run app
    app = create_app(config)

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                   AgentX API Server                       ║
╟───────────────────────────────────────────────────────────╢
║  Model: {config.model:44s} ║
║  Database: {config.database_url:41s} ║
║  Host: {args.host}:{args.port:5d}                                    ║
╟───────────────────────────────────────────────────────────╢
║  Endpoints:                                               ║
║    POST   /api/agentx/sessions                            ║
║    GET    /api/agentx/sessions                            ║
║    GET    /api/agentx/sessions/{{id}}                       ║
║    POST   /api/agentx/sessions/{{id}}/messages             ║
║    WS     /api/agentx/sessions/{{id}}/stream               ║
╚═══════════════════════════════════════════════════════════╝
""")

    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
