# utils/invoice_math.py
from decimal import Decimal

def _as_amount(value, base: Decimal) -> Decimal:
    if value is None:
        return Decimal("0")

    if isinstance(value, str) and value.strip().endswith("%"):
        pct = Decimal(value.strip().rstrip("%"))
        return (pct / Decimal("100")) * base

    return Decimal(str(value))


def calc_invoice_totals(sub_total, tax, discount) -> dict:
    """
    sub_total … numeric
    tax       … numeric or 'X%'
    discount  … numeric or 'X%'

    returns a dict with the resolved amounts + grand total.
    """
    sub_total = Decimal(str(sub_total))

    tax_amount      = _as_amount(tax,      sub_total)
    discount_amount = _as_amount(discount, sub_total)

    gross  = sub_total + tax_amount
    net    = gross - discount_amount

    return {
        "sub_total":        sub_total,
        "tax_amount":       tax_amount,
        "discount_amount":  discount_amount,
        "total":            max(net, Decimal("0")),   
    }
