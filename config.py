import os
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv
from eth_typing import URI

from distutils.util import strtobool

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env", override=False)

AUCTIONEER_PK = os.environ["AUCTIONEER_PK"]

IS_DEBUG = bool(strtobool(os.environ.get("IS_DEBUG", "False")))
IS_ONLY_NOTIFICATOR = bool(strtobool(os.environ.get("IS_ONLY_NOTIFICATOR", "False")))

RPC_URL = URI(os.environ.get("RPC_URL", "https://evmexplorer.velas.com/rpc"))
EXTERNAL_BLOCK_EXPLORER_URL = os.environ.get("EXTERNAL_BLOCK_EXPLORER_URL", "https://evmexplorer.velas.com/api")

CHAIN_LOG_ADDRESS = os.environ.get("CHAIN_LOG_ADDRESS", "0x87986E3AC1F67aDc36027Df78fBfc06CbB36E768")
PERCENT_PRICE_DELTA = Decimal(os.environ.get("PERCENT_PRICE_DELTA", "-7"))

WAGYU_SLIPPAGE = Decimal(os.environ.get("WAGYU_SLIPPAGE", "0.5"))
WAGYU_ROUTER_ADDRESS = os.environ.get("WAGYU_ROUTER_ADDRESS", "0x3D1c58B6d4501E34DF37Cf0f664A58059a188F00")

TG_BOT_KEY = os.environ.get("TG_BOT_KEY")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
