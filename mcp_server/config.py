import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database Connection Settings
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Individual fallback parameters if DATABASE_URL is not set as a full string
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "agrivision")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# Operational Guardrails
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))       # 5.0s hard timeout
DB_STATEMENT_TIMEOUT = int(os.getenv("DB_STATEMENT_TIMEOUT", "5000")) # 5000ms query timeout

# Logging Setup: ALWAYS stream to stderr to protect MCP stdio JSON-RPC framing
logger = logging.getLogger("agrimind_mcp")
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [agrimind_mcp]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
