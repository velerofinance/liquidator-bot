import logging
import threading
from queue import Queue

import web3

from velero_bot_sdk import DssContractsConnector, WagyuContractConnector, VELERO_DEFAULT_ABI_DIR

import config
from liquidator.utils import setup_logging
from liquidator.viewer import Viewer
from liquidator.liquidations.Liquidator import Liquidator


class BotLiquidator:
    viewer: Viewer
    liquidator: Liquidator

    _viewer_thread: threading.Thread
    _liquidator_thread: threading.Thread

    unsafe_vaults_queue: Queue

    dss: DssContractsConnector
    wagyu: WagyuContractConnector

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.unsafe_vaults_queue = Queue()

        account = web3.Web3().eth.account.from_key(config.AUCTIONEER_PK)
        self.is_only_notificator = config.IS_ONLY_NOTIFICATOR
        self.logger.info(f"Initialization DSS")
        self.dss = DssContractsConnector(http_rpc_url=config.RPC_URL, abi_dir=VELERO_DEFAULT_ABI_DIR,
                                         chain_log_addr=config.CHAIN_LOG_ADDRESS,
                                         external_block_explorer_url=config.EXTERNAL_BLOCK_EXPLORER_URL,
                                         account=account, rpc_timeout=10)
        self.viewer = Viewer(queue=self.unsafe_vaults_queue, dss=self.dss)
        self.logger.info(f"Initialization Wagyu")

        if self.is_only_notificator is False:
            self.wagyu = WagyuContractConnector(http_rpc_url=config.RPC_URL, abi_dir=VELERO_DEFAULT_ABI_DIR,
                                                router_addr=config.WAGYU_ROUTER_ADDRESS,
                                                multicall_addr=self.dss.multicall.address,
                                                slippage=config.WAGYU_SLIPPAGE,
                                                external_block_explorer_url=config.EXTERNAL_BLOCK_EXPLORER_URL,
                                                account=account, rpc_timeout=10)

            self.liquidator = Liquidator(queue=self.unsafe_vaults_queue, dss=self.dss, wagyu=self.wagyu,
                                         percent_price_delta=config.PERCENT_PRICE_DELTA, make_payback=config.MAKE_PAYBACK)

    def start(self):
        self._viewer_thread = threading.Thread(target=self.viewer.start, name="viewer_thread")
        self._viewer_thread.start()
        if self.is_only_notificator is False:
            self._liquidator_thread = threading.Thread(target=self.liquidator.start, name="liquidator_thread")
            self._liquidator_thread.start()

    def stop(self):
        self.viewer.stop()
        if self.is_only_notificator is False:
            self.liquidator.stop()

        self._viewer_thread.join()
        if self.is_only_notificator is False:
            self._liquidator_thread.join()


if __name__ == '__main__':
    setup_logging(
        tg_bot_key=config.TG_BOT_KEY,
        tg_chat_id=config.TG_CHAT_ID,
        is_debug=config.IS_DEBUG,
        is_only_notificator=config.IS_ONLY_NOTIFICATOR
    )
    bot = BotLiquidator()
    try:
        bot.start()
    except KeyboardInterrupt:
        pass
    finally:
        bot.stop()
