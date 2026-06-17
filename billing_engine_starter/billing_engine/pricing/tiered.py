"""
TieredPricing — different price per unit depending on the tier.
Cumulative (stacked) tier model.
"""

from dataclasses import dataclass
from typing import Optional

from billing_engine.money import Money
from billing_engine.pricing.base import PricingStrategy


@dataclass(frozen=True)
class Tier:
    from_units: int
    to_units: Optional[int]   # None means "unlimited"
    unit_price: Money


class TieredPricing(PricingStrategy):
    def __init__(self, tiers: list[Tier]) -> None:
        if not isinstance(tiers, list) or not tiers:
            raise ValueError("tiers must be a non-empty list")
        for tier in tiers:
            if not isinstance(tier, Tier):
                raise TypeError("each tier must be a Tier instance")
            if tier.from_units < 0:
                raise ValueError("tier.from_units cannot be negative")
            if tier.to_units is not None and tier.to_units <= tier.from_units:
                raise ValueError("tier.to_units must be > from_units (or None)")
            if not isinstance(tier.unit_price, Money):
                raise TypeError("tier.unit_price must be Money")
            if tier.unit_price.is_negative():
                raise ValueError("tier.unit_price cannot be negative")
        self.tiers = tiers

    def calculate(self, quantity: int) -> Money:
        if not isinstance(quantity, int):
            raise TypeError("quantity must be int")
        if quantity < 0:
            raise ValueError("quantity cannot be negative")

        total = Money(0, self.tiers[0].unit_price.currency)
        remaining = quantity

        for tier in self.tiers:
            if remaining <= 0:
                break
            if tier.to_units is None:
                units_in_tier = remaining
            else:
                units_in_tier = min(remaining, tier.to_units - tier.from_units)
            if units_in_tier > 0:
                total += tier.unit_price * units_in_tier
                remaining -= units_in_tier

        return total
