import logging
import threading
import time
from decimal import Decimal
from queue import Queue, Empty

import requests
from velero_bot_sdk import DssContractsConnector, WagyuContractConnector, Converter
from web3.exceptions import ContractLogicError

from liquidator.vault import Vault
from liquidator.liquidations.AuctionItem import AuctionItem
from liquidator.liquidations.ExitCollateralItem import ExitCollateralItem
from liquidator.liquidations.PaybackItem import PaybackItem
from liquidator.liquidations.joinItem import JoinItem


class Liquidator:
    alive: bool = False

    def __init__(self, queue: Queue, dss: DssContractsConnector,
                 wagyu: WagyuContractConnector, percent_price_delta: Decimal):
        self.dss = dss
        self.setup_liquidations_queue = queue
        self.tasks = []
        self.wagyu = wagyu
        self.percent_price_delta = percent_price_delta

        self.liquidations_queue = Queue()
        self.payback_queue = Queue()
        self.exit_queue = Queue()
        self.join_queue = Queue()

        self.liquidations_threads_count = 5

        self.logger = logging.getLogger(self.__class__.__name__)

    def stop(self):
        self.alive = False

    def start(self):
        self.logger.notification(f"Start Liquidator")
        self.alive = True

        while self.alive:
            threads = []
            try:
                threads.append(threading.Thread(target=self.setup_new_liquidation, name="thread_setup_new_auctions"))
                threads.append(threading.Thread(target=self.check_active_auctions, name="thread_check_active_auctions"))
                threads.append(threading.Thread(target=self.processed_exit, name="thread_process_exits"))
                threads.append(threading.Thread(target=self.processed_payback, name="thread_process_payback"))
                threads.append(threading.Thread(target=self.processed_joined, name="thread_processed_joined"))

                for i in range(self.liquidations_threads_count):
                    threads.append(threading.Thread(
                        target=self.processed_liquidation,
                        name=f"thread#{i}_processed_liquidation#0"
                    ))

                list(map(lambda x: x.start(), threads))
                list(map(lambda x: x.join(), threads))
            finally:
                time.sleep(300)
        self.logger.notification(f"Stop Liquidator")

    def processed_joined(self):
        self.logger.info(f"Start processed joined")
        while self.alive:
            try:
                join_item: JoinItem = self.join_queue.get_nowait()
            except Empty:
                time.sleep(10)
                continue

            self.logger.debug(f"start join process for auction #{join_item.liquidation_id} {join_item.ilk}")
            try:
                join_item.process(dss=self.dss)
            except requests.exceptions.ReadTimeout:
                self.join_queue.put_nowait(join_item)
                time.sleep(5)
                continue
            except ContractLogicError as e:
                self.logger.error(
                    f"failed join process for auction #{join_item.liquidation_id} {join_item.ilk}",
                    exc_info=e
                )
                continue
            except Exception as e:
                self.logger.error(
                    f"failed join process for auction #{join_item.liquidation_id} {join_item.ilk}",
                    exc_info=e
                )
                self.join_queue.put_nowait(join_item)
                continue
            self.logger.debug(f"finish join process for auction #{join_item.liquidation_id} {join_item.ilk}")
            time.sleep(10)

    def processed_payback(self):
        self.logger.info(f"Start processed payback")
        while self.alive:
            try:
                payback_item: PaybackItem = self.payback_queue.get_nowait()
            except Empty:
                time.sleep(10)
                continue

            self.logger.debug(f"start payback process for auction #{payback_item.liquidation_id} {payback_item.ilk}")
            try:
                payback_item.process(wagyu=self.wagyu, dss=self.dss)
            except requests.exceptions.ReadTimeout:
                self.payback_queue.put_nowait(payback_item)
                time.sleep(5)
                continue
            except ContractLogicError as e:
                self.logger.error(
                    f"failed payback process for auction #{payback_item.liquidation_id} {payback_item.ilk}",
                    exc_info=e
                )
                continue
            except Exception as e:
                self.logger.error(
                    f"failed payback process for auction #{payback_item.liquidation_id} {payback_item.ilk}",
                    exc_info=e
                )
                self.payback_queue.put_nowait(payback_item)
                continue

            self.logger.debug(f"finish payback process for auction #{payback_item.liquidation_id} {payback_item.ilk}")
            if payback_item.is_completed is True:
                self.logger.debug(
                    f"add received amount to join queue for auction #{payback_item.liquidation_id} {payback_item.ilk}")
                self.join_queue.put_nowait(
                    JoinItem(
                        liquidation_id=payback_item.liquidation_id,
                        ilk=payback_item.ilk,
                        amount=payback_item.payback_amount,
                        logger=self.logger
                    )
                )
            time.sleep(10)

    def processed_exit(self):
        self.logger.info(f"Start processed exit")
        while self.alive:
            try:
                exit_item: ExitCollateralItem = self.exit_queue.get_nowait()
            except Empty:
                time.sleep(10)
                continue
            self.logger.debug(f"start exit process for auction #{exit_item.liquidation_id} {exit_item.ilk}")
            try:
                exit_item.process(dss=self.dss)
            except requests.exceptions.ReadTimeout:
                self.exit_queue.put_nowait(exit_item)
                time.sleep(5)
                continue
            except ContractLogicError as e:
                self.logger.error(
                    f"failed exit process for auction #{exit_item.liquidation_id} {exit_item.ilk}",
                    exc_info=e
                )
                continue
            except Exception as e:
                self.logger.error(
                    f"failed exit process for auction #{exit_item.liquidation_id} {exit_item.ilk}",
                    exc_info=e
                )
                self.exit_queue.put_nowait(exit_item)
                continue
            self.logger.debug(f"finish exit process for auction #{exit_item.liquidation_id} {exit_item.ilk}")
            if exit_item.is_completed is True:
                self.logger.debug(
                    f"add received amount to payback queue for auction #{exit_item.liquidation_id} {exit_item.ilk}")
                self.payback_queue.put_nowait(
                    PaybackItem(
                        liquidation_id=exit_item.liquidation_id,
                        ilk=exit_item.ilk,
                        amount=exit_item.amount,
                        price=exit_item.price,
                        swap_path=exit_item.swap_path,
                        logger=self.logger
                    )
                )
            time.sleep(10)

    def processed_liquidation(self):
        self.logger.info(f"Start processed liquidation")
        while self.alive:
            try:
                auction: AuctionItem = self.liquidations_queue.get_nowait()
            except Empty:
                time.sleep(10)
                continue
            self.logger.debug(f"start liquidation process for auction #{auction.liquidation_id} {auction.ilk}")
            try:
                auction.process(dss=self.dss, wagyu=self.wagyu)
                self.logger.debug(f"start liquidation process for auction #{auction.liquidation_id} {auction.ilk}")

            except requests.exceptions.ReadTimeout:
                self.liquidations_queue.put_nowait(auction)
                time.sleep(5)
                self.logger.info(f"restart liquidation process for auction #{auction.liquidation_id} {auction.ilk}")
                continue
            except ContractLogicError as e:
                self.logger.error(
                    f"failed liquidation process for auction #{auction.liquidation_id} {auction.ilk}",
                    exc_info=e
                )
                continue
            except Exception as e:
                self.logger.error(
                    f"failed liquidation process for auction #{auction.liquidation_id} {auction.ilk}",
                    exc_info=e
                )
                self.liquidations_queue.put_nowait(auction)
                continue
            self.logger.debug(f"finish liquidation process for auction #{auction.liquidation_id} {auction.ilk}")
            if auction.is_completed is True:
                self.logger.debug(f"add received amount to exit queue for auction #{auction.liquidation_id} {auction.ilk}")
                self.exit_queue.put_nowait(
                    ExitCollateralItem(
                        liquidation_id=auction.liquidation_id,
                        ilk=auction.ilk,
                        amount=auction.lot,
                        price=auction.price,
                        swap_path=auction.swap_path,
                        logger=self.logger
                    )
                )
            time.sleep(5)

    def check_active_auctions(self):
        self.logger.info(f"Start processed check active auctions")
        while self.alive:
            try:
                for ilk in self.dss.ilk_list:
                    clipper = self.dss.get_ilk_clip(ilk)
                    for liquidation_id in clipper.caller.list():
                        self.logger.debug(f"add {liquidation_id} auction to queue for liquidation")
                        self.liquidations_queue.put_nowait(
                            AuctionItem(
                                liquidation_id=liquidation_id,
                                ilk=ilk,
                                clipper=clipper,
                                dss=self.dss,
                                wagyu=self.wagyu,
                                percent_price_delta=self.percent_price_delta,
                                logger=self.logger
                            )
                        )
                        time.sleep(5)
            except Exception as e:
                continue
            time.sleep(30)

    def setup_new_liquidation(self):
        self.logger.info(f"Start processed setup new auctions")
        while self.alive:
            try:
                vault: Vault = self.setup_liquidations_queue.get_nowait()
            except Empty:
                time.sleep(10)
                continue

            try:
                call_func = self.dss.dog.functions.bark(
                    ilk=Converter.str_to_bytes32(vault.ilk),
                    urn=vault.address,
                    kpr=self.dss.account.address
                )

                tx = self.dss.call_tx(call_func)
                self.logger.notification(f"Init auction for liquidate {vault.ilk} vault #{vault.id}"
                                         f" ({vault.address}) tx={str(tx.hex())}")
            except ContractLogicError as e:
                a = e
                continue
            except requests.exceptions.ReadTimeout:
                self.setup_liquidations_queue.put_nowait(vault)
            except Exception as e:
                self.setup_liquidations_queue.put_nowait(vault)
                self.logger.error(f"Failed bark vault {vault.id}", exc_info=e, extra=vault.to_dict())

            time.sleep(3)
