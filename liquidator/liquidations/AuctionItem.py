import logging
from decimal import Decimal
from typing import List

from velero_bot_sdk import WagyuContractConnector, DssContractsConnector, calc_perc
from web3.contract import Contract
from web3.exceptions import TimeExhausted


class AuctionItem:
    clipper: Contract
    liquidation_id: int
    ilk: str
    swap_path: List[str]

    is_completed: bool = False
    lot: int
    price: int
    percent_price_delta: Decimal

    def __init__(self, liquidation_id: int, ilk: str, clipper: Contract, dss: DssContractsConnector,
                 wagyu: WagyuContractConnector, percent_price_delta: Decimal, **kwargs):
        self.liquidation_id = liquidation_id
        self.ilk = ilk
        self.coin = self.ilk.split("-")[0]
        self.clipper = clipper
        self.percent_price_delta = percent_price_delta

        if self.coin == "VLX":
            self.swap_path = [wagyu._wrapped_coin_addr, dss.get_contact_address("WAG"), dss.usdv.address]
        elif self.coin == "WAG":
            self.swap_path = [dss.get_contact_address("WAG"), dss.usdv.address]
        elif self.coin == "WBTC":
            self.swap_path = [dss.get_contact_address("WBTC"), dss.usdv.address]
        else:
            raise ValueError("Not supported coin")

        self.logger = kwargs.get("logger", logging.getLogger(self.__class__.__name__))

    def process(self, dss: DssContractsConnector, wagyu: WagyuContractConnector):
        needs_redo, price, lot, tab = self.clipper.caller.getStatus(self.liquidation_id)

        tab = Decimal(tab) / Decimal(10 ** 27)
        price = Decimal(price) / Decimal(10 ** 27)

        if needs_redo:
            return self.redo(dss=dss)

        if tab <= 0 or lot <= 0:
            self.logger.info(f"[{self.liquidation_id} {self.ilk}] liquidation already not active (lot={lot} tab={tab})")
            return

        amount_in = Decimal(wagyu.get_amount_in(amount_out=tab, path=self.swap_path))
        market_price = tab / amount_in

        max_price = calc_perc(market_price, self.percent_price_delta)
        if price > max_price:
            self.logger.info(f"[{self.liquidation_id} {self.ilk}] {price} (max_price={max_price}) price for liquidation is great.")
            return

        amount = Decimal(min(lot, Decimal(dss.vat.caller.usdv(dss.account.address)) / Decimal(10 ** 27)))

        if Decimal(lot) - amount != Decimal('0') and Decimal(lot) - amount < (
                Decimal(self.clipper.caller.chost()) / Decimal(10 ** 27)):
            self.logger.warning(f"[{self.liquidation_id} {self.ilk}] there is not enough balance on VAT for a take")
            return

        func = self.clipper.functions.take(
            amt=int(amount),
            id=self.liquidation_id,
            max=int(calc_perc(price, Decimal("0.1")) * Decimal(10 ** 27)),
            who=dss.account.address,
            data="0x"
        )
        tx = dss.call_tx(func)
        self.logger.notification(
            f"[{self.liquidation_id} {self.ilk}] take lot by liquidation with max price {max_price} ( {str(tx.hex())} )")

        try:
            receipt_tx = dss.web3.eth.wait_for_transaction_receipt(transaction_hash=tx, timeout=30)
        except TimeExhausted as e:
            self.logger.warning(
                f"[{self.liquidation_id} {self.ilk}] the transaction {str(tx.hex())} was not confirmed within 30 seconds. "
                "Please make sure that the transaction was failed, "
                "otherwise it is necessary to withdraw and exchange "
                "the received collateral asset yourself", exc_info=e)
            raise e

        logs = self.clipper.events.Take().processReceipt(receipt_tx)

        if len(logs) != 1:
            self.logger.warning(
                f"[{self.liquidation_id} {self.ilk}] transaction {str(tx.hex())} has more than one Take() event")
            return
        take_log = logs[0]['args']

        self.price = take_log['price']
        self.lot = int(Decimal(str(take_log['owe'])) / Decimal(str(self.price)))  # owe / price
        self.is_completed = True

    def redo(self, dss: DssContractsConnector):
        try:
            tx = dss.call_tx(self.clipper.functions.redo(id=self.liquidation_id, kpr=dss.account.address))
            self.logger.notification(f"[{self.liquidation_id} {self.ilk}] restart auction ({str(tx.hex())})")
        except Exception as e:
            self.logger.error(f"[{self.liquidation_id} {self.ilk}] failed restart auction", exc_info=e)
            raise e

        try:
            receipt_tx = dss.web3.eth.wait_for_transaction_receipt(transaction_hash=tx, timeout=30)
        except TimeExhausted as e:
            self.logger.warning(
                f"[{self.liquidation_id} {self.ilk}] the transaction {str(tx.hex())} "
                f"was not confirmed within 30 seconds. "
                "Please make sure that the transaction was failed, "
                "otherwise it is necessary to withdraw and exchange "
                "the received collateral asset yourself", exc_info=e)
            raise e

        return receipt_tx
