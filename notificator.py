import logging
import threading
from queue import Queue

import web3

from velero_bot_sdk import DssContractsConnector, VELERO_DEFAULT_ABI_DIR

import config
from liquidator.utils import setup_notificator
from liquidator.viewer import Viewer


class BotLiquidator:
    viewer: Viewer

    _viewer_thread: threading.Thread

    unsafe_vaults_queue: Queue
    dss: DssContractsConnector

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.unsafe_vaults_queue = Queue()

        account = web3.Web3().eth.account.from_key(config.AUCTIONEER_PK)

        self.logger.info(f"Initialization DSS")
        self.dss = DssContractsConnector(http_rpc_url=config.RPC_URL, abi_dir=VELERO_DEFAULT_ABI_DIR,
                                         chain_log_addr=config.CHAIN_LOG_ADDRESS,
                                         external_block_explorer_url=config.EXTERNAL_BLOCK_EXPLORER_URL,
                                         account=account, rpc_timeout=5)

        self.viewer = Viewer(queue=self.unsafe_vaults_queue, dss=self.dss)

    def start(self):
        self._viewer_thread = threading.Thread(target=self.viewer.start, name="viewer_thread")
        self._viewer_thread.start()

    def stop(self):
        self.viewer.stop()
        self._viewer_thread.join()


if __name__ == '__main__':
    setup_notificator(tg_bot_key=config.TG_BOT_KEY, tg_chat_id=config.TG_CHAT_ID, is_debug=config.IS_DEBUG)
    bot = BotLiquidator()
    try:
        bot.start()
    except KeyboardInterrupt:
        pass
    finally:
        bot.stop()
