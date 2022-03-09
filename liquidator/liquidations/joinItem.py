import logging
from decimal import Decimal

from velero_bot_sdk import DssContractsConnector
from web3.exceptions import TimeExhausted


class JoinItem:
    liquidation_id: int
    ilk: str
    amount: int
    price: int

    is_completed: bool

    def __init__(self, liquidation_id: int, ilk: str, amount: int, **kwargs):
        self.liquidation_id = liquidation_id
        self.ilk = ilk
        self.amount = amount

        self.logger = kwargs.get("logger", logging.getLogger(self.__class__.__name__))

    def process(self, dss: DssContractsConnector):
        try:
            func = dss.join_main_stablecoin.functions.join(dss.account.address, self.amount)
            tx = dss.call_tx(func)

            self.logger.notification(f"[{self.liquidation_id} {self.ilk}] "
                                     f"start join {Decimal(self.amount) / Decimal(10**18)} USDV to VAT ( {str(tx.hex())} ).")
        except Exception as e:
            self.logger.error(f"[{self.liquidation_id} {self.ilk}] Failed join usdv to VAT."
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

        self.logger.notification(f"[{self.liquidation_id} {self.ilk}] "
                                 f"finish join {Decimal(self.amount) / Decimal(10 ** 18)} USDV to VAT ( {str(tx.hex())} ).")

        self.is_completed = True
        return receipt_tx
