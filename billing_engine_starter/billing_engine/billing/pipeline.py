def build_invoice(
    subscription: Subscription,
    plan: Plan,
    strategy: PricingStrategy,
    discount: Optional[Discount],
    tax_calc: TaxCalculator,
    tax_context: TaxContext,
    usage_quantity: int,
    period_start: date,
    period_end: date,
    invoice_count_so_far: int,
) -> Invoice:
    """Pure function. Returns an Invoice (id=None, status=DRAFT) ready to be persisted."""
    # Input validation
    if subscription.id is None:
        raise ValueError("subscription must have an id")
    if plan.currency != strategy.calculate(0).currency:
        raise ValueError("Strategy currency does not match plan currency")

    currency = plan.currency

    # 1. Base charge
    base = strategy.calculate(usage_quantity)
    if base.currency != currency:
        raise ValueError("Base amount currency mismatch")

    # 2. Discount
    if discount is not None:
        ctx = DiscountContext(invoice_count_so_far=invoice_count_so_far)
        discount_amount = discount.apply(base, ctx)
        if discount_amount.currency != currency:
            raise ValueError("Discount amount currency mismatch")
    else:
        discount_amount = Money(0, currency)

    # 3. Taxable amount (base - discount, never negative)
    taxable = base - discount_amount
    if taxable.is_negative():
        taxable = Money(0, currency)

    # 4. Tax
    tax_breakdown = tax_calc.apply(taxable, tax_context)
    tax_total = tax_breakdown.total
    if tax_total.currency != currency:
        raise ValueError("Tax total currency mismatch")

    # 5. Total
    total = taxable + tax_total

    # Build the Invoice dataclass (no 'currency' argument – it's derived from Money objects)
    return Invoice(
        id=None,
        subscription_id=subscription.id,
        period_start=period_start,
        period_end=period_end,
        subtotal=base,
        discount_total=discount_amount,
        tax_total=tax_total,
        total=total,
        status=InvoiceStatus.DRAFT,
        issued_at=None,
        pdf_path=None,
    )
