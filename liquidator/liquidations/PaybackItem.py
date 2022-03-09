import logging
from decimal import Decimal
from typing import List

from velero_bot_sdk import WagyuContractConnector, DssContractsConnector
from web3.exceptions import TimeExhausted


class PaybackItem:
    liquidation_id: int
    ilk: str
    amount: int
    price: int
    swap_path: List[str]
    payback_amount: int

    is_completed: bool

    def __init__(self, liquidation_id: int, ilk: str, amount: int, price: int, swap_path: List[str], **kwargs):
        self.liquidation_id = liquidation_id
        self.ilk = ilk
        self.amount = amount
        self.price = price
        self.swap_path = swap_path

        self.logger = kwargs.get("logger", logging.getLogger(self.__class__.__name__))

    def process(self, wagyu: WagyuContractConnector, dss: DssContractsConnector):
        try:
            receive_amount = Decimal(self.amount) * Decimal(self.price)

            ilk_currency = self.ilk.split('-')[0].upper()
            if ilk_currency == "VLX":
                tx = wagyu.swap_exact_coins_for_tokens(
                    amount_in=Decimal(self.amount),
                    path=self.swap_path,
                    min_amount_out=receive_amount / Decimal(10 ** 27)
                )
            elif ilk_currency == "WAG":
                tx = wagyu.swap_exact_tokens_for_tokens(
                    amount_in=Decimal(self.amount),
                    path=self.swap_path,
                    min_amount_out=receive_amount / Decimal(10 ** 27)
                )
            else:
                raise ValueError(f"Unsupported currency {ilk_currency}")

            self.logger.notification(
                f"[{self.liquidation_id} {self.ilk}] swap {Decimal(self.amount) / Decimal(10 ** 18)} "
                f"to {receive_amount / Decimal(10 ** 45)} USDV ( {str(tx.hex())} ).")
        except Exception as e:
            self.logger.error(f"[{self.liquidation_id} {self.ilk}] Failed swap."
                              f" It is necessary exchange the currency manually",
                              exc_info=e)
            raise e

        try:
            receipt_tx = wagyu.web3.eth.wait_for_transaction_receipt(transaction_hash=tx, timeout=30)
        except TimeExhausted as e:
            self.logger.warning(f"[{self.liquidation_id} {self.ilk}] the transaction {str(tx.hex())} "
                                f"was not confirmed within 30 seconds."
                                " Please make sure that the transaction was failed, "
                                "otherwise it is necessary exchange "
                                "the received collateral asset yourself", exc_info=e)
            raise e

        logs = dss.usdv.events.Transfer().processReceipt(receipt_tx)

        if len(logs) < 1:
            self.logger.warning(
                f"[{self.liquidation_id} {self.ilk}] transaction {str(tx.hex())} has more than one Transfer() event")
            return
        log = next(filter(lambda x: x['dst'] == wagyu.account.address, map(lambda x: x['args'], logs)))
        self.payback_amount = log['wad']

        self.is_completed = True
        return receipt_tx
