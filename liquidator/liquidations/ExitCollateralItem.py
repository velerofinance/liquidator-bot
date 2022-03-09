import logging
from decimal import Decimal
from typing import List

from velero_bot_sdk import DssContractsConnector
from web3.exceptions import TimeExhausted


class ExitCollateralItem:
    liquidation_id: int
    ilk: str
    amount: int
    price: int

    is_completed: bool
    swap_path: List[str]

    def __init__(self, liquidation_id: int, ilk: str, amount: int, price: int, swap_path: List[str], **kwargs):
        self.liquidation_id = liquidation_id
        self.ilk = ilk
        self.amount = amount
        self.price = price
        self.swap_path = swap_path

        self.logger = kwargs.get("logger", logging.getLogger(self.__class__.__name__))

    def process(self, dss: DssContractsConnector):
        try:
            func = dss.get_ilk_join(self.ilk).functions.exit(dss.account.address, self.amount)
            tx = dss.call_tx(func)

            self.logger.notification(f"[{self.liquidation_id} {self.ilk}] "
                                     f"exit {Decimal(self.amount) / Decimal(10**18)} from VAT ( {str(tx.hex())} ).")
        except Exception as e:
            self.logger.error(f"[{self.liquidation_id} {self.ilk}] Failed exit from VAT."
                              f" It is necessary to withdraw and exchange the currency manually",
                              exc_info=e)
            raise e

        try:
            receipt_tx = dss.web3.eth.wait_for_transaction_receipt(transaction_hash=tx, timeout=30)
        except TimeExhausted as e:
            self.logger.warning(f"[{self.liquidation_id} {self.ilk}] the transaction {str(tx.hex())} "
                                f"was not confirmed within 30 seconds. "
                                "Please make sure that the transaction was failed, "
                                "otherwise it is necessary to withdraw and exchange "
                                "the received collateral asset yourself", exc_info=e)
            raise e

        if self.ilk.split("-")[0] == "VLX":
            self.unwrap(dss=dss)

        self.is_completed = True
        return receipt_tx

    def unwrap(self, dss: DssContractsConnector):
        try:
            func = dss.vlx.functions.withdraw(self.amount)
            tx = dss.call_tx(func)
            self.logger.notification(
                f"[{self.liquidation_id} {self.ilk}] unwrapped {Decimal(self.amount) / Decimal(10 ** 18)} ( {str(tx.hex())} )")
        except Exception as e:
            self.logger.error(f"[{self.liquidation_id} {self.ilk}] Failed unwrapped."
                              f" It is necessary unwrapped and exchange the currency manually",
                              exc_info=e)
            raise e

        try:
            receipt_tx = dss.web3.eth.wait_for_transaction_receipt(transaction_hash=tx, timeout=30)
        except TimeExhausted as e:
            self.logger.warning(
                f"[{self.liquidation_id} {self.ilk}] the transaction {str(tx.hex())} was not "
                f"confirmed within 30 seconds. Please make sure that the transaction was failed, "
                "otherwise it is necessary to unwrapped and exchange "
                "the received collateral asset yourself", exc_info=e)
            raise e
        return receipt_tx
