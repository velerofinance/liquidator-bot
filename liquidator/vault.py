from decimal import Decimal
from typing import List

from velero_bot_sdk import VeleroFormuls


MIN_LIQUIDITY = Decimal('150')


class Vault:
    id: int
    address: str
    current_liquidity: Decimal = Decimal('0')
    price_liquidity: Decimal = Decimal('0')
    debt: Decimal = 0
    collateral: Decimal = 0
    ilk: str
    owner_proxy: str
    owner: str

    def __init__(self, cdp_id, address, owner_proxy, owner, debt, collateral, ilk, current_price):
        self.id = cdp_id
        self.address = address
        self.owner_proxy = owner_proxy
        self.owner = owner
        self.ilk = ilk

        if collateral > 0 and debt > 0:
            self.debt = Decimal(debt) / Decimal(10 ** 45)
            self.collateral = Decimal(collateral) / Decimal(10 ** 18)

            self.price_liquidity = VeleroFormuls.get_liquidation_price(
                collateral=self.collateral,
                debt_currency=self.debt,
                min_liquidity=MIN_LIQUIDITY
            )
            self.current_liquidity = VeleroFormuls.get_liquidity(
                price=current_price,
                collateral=self.collateral,
                debt_currency=self.debt
            )

    @property
    def is_secured(self):
        return self.current_liquidity == 0 or self.current_liquidity >= MIN_LIQUIDITY

    @classmethod
    def fields(cls):
        return list(cls.__annotations__.keys())

    def to_list(self, fields: List[str] = None):
        return list(map(self.__getattribute__, fields or self.fields()))

    def to_dict(self, fields: List[str] = None):
        return dict(map(lambda x: (x, self.__getattribute__(x)), fields or self.fields()))

    def to_serializable_dict(self, fields: List[str] = None):
        raw_dict = self.to_dict(fields=fields)

        for key in dict(filter(lambda item: item[1] is Decimal, Vault.__annotations__.items())).keys():
            if key in raw_dict:
                raw_dict[key] = str(raw_dict[key])
        return raw_dict
