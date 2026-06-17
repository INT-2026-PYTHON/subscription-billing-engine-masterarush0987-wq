"""
TieredPricing — different price per unit depending on the tier the quantity falls into.
Cumulative (stacked) tier model.
"""

from dataclasses import dataclass
from typing import Optional

from billing_engine.money import Money
from billing_engine.pricing.base import PricingStrategy   # <-- this was missing!


@dataclass(frozen=True)
class Tier:
    from_units: int
    to_units: Optional[int]   # None means "unlimited"
    unit_price: Money


class TieredPricing(PricingStrategy):
    def __init__(self, tiers: list[Tier]) -> None:
        if not tiers:
            raise ValueError("tiers must be non-empty")
        # Validate all currencies same
        first_currency = tiers[0].unit_price.currency
        for tier in tiers:
            if not isinstance(tier, Tier):
                raise TypeError("each element must be a Tier")
            if tier.unit_price.currency != first_currency:
                raise ValueError("All tiers must have the same currency")
            if tier.from_units < 0:
                raise ValueError("from_units cannot be negative")
            if tier.to_units is not None and tier.to_units <= tier.from_units:
                raise ValueError("to_units must be > from_units (or None)")
        # Sort by from_units to check contiguity
        sorted_tiers = sorted(tiers, key=lambda t: t.from_units)
        # Check contiguity: first from_units must be 0, and each next's from_units == previous to_units
        if sorted_tiers[0].from_units != 0:
            raise ValueError("First tier must start at 0")
        for i in range(len(sorted_tiers) - 1):
            if sorted_tiers[i].to_units is None:
                raise ValueError("Only the last tier may have to_units = None")
            if sorted_tiers[i + 1].from_units != sorted_tiers[i].to_units:
                raise ValueError("Tiers must be contiguous (adjacent tier's from_units == previous to_units)")
        # Last tier must have to_units = None
        if sorted_tiers[-1].to_units is not None:
            raise ValueError("The top tier must be open-ended (to_units = None)")

        self.tiers = sorted_tiers

    def calculate(self, quantity: int) -> Money:
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
