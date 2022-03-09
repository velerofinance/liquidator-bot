import asyncio
import logging
import threading
import time

import requests

from decimal import Decimal
from queue import Queue
from typing import List, Tuple

from velero_bot_sdk import DssContractsConnector, Converter

from liquidator.vault import Vault


def chunks(lst, n):
    count = len(lst) // n
    for i in range(0, len(lst), count):
        yield lst[i:i + count]


class Viewer:
    logger: logging.Logger
    alive: bool = False

    def __init__(self, queue: Queue, dss: DssContractsConnector):
        self.dss = dss
        self.liquidation_queue = queue
        self.logger = logging.getLogger(self.__class__.__name__)

    def start(self):
        self.logger.notification(f"Start Viewer")
        self.alive = True
        while self.alive:
            try:
                self.logger.debug("running a check of all vaults")
                self.check_cdps()
                self.logger.debug("finish a check of all vaults")
            finally:
                time.sleep(30)
        self.logger.notification(f"Stop Viewer")

    def stop(self):
        self.alive = False

    async def async_check(self, ids):
        coroutines = list(map(self.check_cdp, ids))
        return await asyncio.gather(*coroutines, return_exceptions=True)

    def check_cdps(self, numbers: List[int] = None, n: int = 6):
        def run_async(*args):
            _st = time.time_ns()
            self.logger.debug(f"start batch check")
            asyncio.run(self.async_check(*args))
            self.logger.debug(f"finish batch check ({time.time_ns() - _st})")

        count = self.dss.cdp_manager.caller.cdpi() if numbers is None else len(numbers)
        self.logger.info(f"start check {count} vaults in {n} threads")
        threads = list(map(lambda x: threading.Thread(target=run_async, args=[x]), chunks(range(1, count + 1), n)))
        list(map(lambda x: x.start(), threads))
        list(map(lambda x: x.join(), threads))
        self.logger.info(f"finish check {count} vaults")

    async def get_urn_address(self, cdp_number: int) -> str:
        return self.dss.cdp_manager.caller.urns(cdp_number)

    async def get_cdp_owner_proxy_address(self, cdp_number: int) -> str:
        return self.dss.cdp_manager.caller.owns(cdp_number)

    async def get_cdp_ilk(self, cdp_number: int) -> str:
        return Converter.bytes32_to_str(self.dss.cdp_manager.caller.ilks(cdp_number))

    async def get_locked_collateral_and_debt(self, urn_address: str, ilk: str) -> Tuple[Decimal, Decimal]:
        ilk = Converter.str_to_bytes32(ilk)
        collateral, art = self.dss.vat.caller.urns(ilk, urn_address)
        _, rate, _, _, _ = self.dss.vat.caller.ilks(ilk)
        debt = art * rate

        return collateral, debt

    async def get_cdp_owner(self, proxy_address: str) -> str:
        return self.dss.get_ds_proxy(proxy_address).caller.owner()

    async def check_cdp(self, cdp_number: int):
        try:
            self.logger.debug(f"start check cdp #{cdp_number}")
            urn_address = self.get_urn_address(cdp_number=cdp_number)
            owner_proxy_address = self.get_cdp_owner_proxy_address(cdp_number=cdp_number)
            ilk = self.get_cdp_ilk(cdp_number=cdp_number)

            urn_address = await urn_address
            ilk = await ilk
            owner_proxy_address = await owner_proxy_address
            collateral_and_debt = await self.get_locked_collateral_and_debt(urn_address=urn_address, ilk=ilk)
            cdp_owner = self.get_cdp_owner(proxy_address=owner_proxy_address)

            current_price = self.dss.get_current_price(ilk)

            vault = Vault(
                cdp_id=cdp_number,
                address=urn_address,
                owner_proxy=owner_proxy_address,
                owner=await cdp_owner,
                debt=collateral_and_debt[1],
                collateral=collateral_and_debt[0],
                ilk=ilk,
                current_price=current_price
            )

            if not vault.is_secured:
                self.logger.notification(f"vault #{cdp_number} is not secured. \n{vault.to_dict()}", extra=vault.to_dict())
                self.liquidation_queue.put(vault)
            self.logger.debug(f"finish check cdp #{cdp_number}", extra=vault.to_dict())
            return vault  #
        except requests.exceptions.ReadTimeout:
            return await self.check_cdp(cdp_number)
        except Exception as e:
            self.logger.error(f"failed check vault #{cdp_number}", exc_info=e)
            return await self.check_cdp(cdp_number)
