from __future__ import annotations
import re, logging
from decimal import Decimal
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import dateparser
from rapidfuzz import fuzz
from datetime import date
from typing import Optional, List
from dateutil import parser as dtparser

log = logging.getLogger(__name__)

_CURRENCY_SIGNS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}
AMOUNT_RE = r"[$€£₹]?\s*\d+(?:,\d{5})*(?:\.\d{1,6})?"
_DATE_STYLES    = {"DATE_ORDER": "DMY"}


_LABELS: dict[str, list[str]] = {
    "invoice_number": ["invoice number", "inv no", "invoice #", "bill no", "ref", "invoice no.", "no:", "number"],
    "invoice_date"  : ["invoice date", "date", "bill date"],
    "due_date"      : ["due date", "payment due", "duedate", "due-date"],
    "vendor"        : ["vendor", "supplier", "seller"],
    "subtotal"      : ["subtotal", "sub-total", "sub total"],
    "discount"      : ["discount", "deduct"],
    "tax"           : ["tax", "vat", "gst", "cgst", "sgst"],
    "total"         : ["total", "grand total", "amount due", "Total"],
}

_CANON = {k: [re.sub(r"[^a-z0-9]", "", v) for v in vs] for k, vs in _LABELS.items()}

# -------------------------------------------------------------------------------
# 2. Date helpers 
# -------------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Public dataclass returned by parser
# -----------------------------------------------------------------------------
@dataclass
class InvoiceExtract:
    invoice_number: Optional[str]
    invoice_date : Optional[str]
    due_date     : Optional[str]
    vendor       : Optional[str]
    subtotal     : Optional[Decimal]
    discount     : Optional[Decimal]
    tax          : Optional[Decimal]
    total        : Optional[Decimal]
    currency     : Optional[str]
    items        : List[Dict[str, Any]]
    score        : float              
    raw_text     : str

    def dict(self):
        return asdict(self)

# -----------------------------------------------------------------------------
# Core extraction pipeline
# -----------------------------------------------------------------------------

_DATE_RX = re.compile(r"\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b")

class InvoiceParser:
    def __init__(self, min_score: float = 0.6):
        self.min_conf = min_score

    # ---------- helpers --------------------------------------------------
    @staticmethod
    def _iso(match: str) -> str:
        return dtparser.parse(match, dayfirst=True).date().isoformat()

    @staticmethod
    def _find_date_near_label(
        lines: List[str],
        aliases: List[str],
        window: int = 5,
    ) -> Optional[str]:
        aliases = [a.lower() for a in aliases]

        for idx, line in enumerate(lines):
            lower = line.lower()
            if not any(a in lower for a in aliases):
                continue

            # (1) tail‑of‑line --------------    
            label_end_idx = max(lower.find(a) + len(a) for a in aliases if a in lower)
            tail = line[label_end_idx:]
            if m := _DATE_RX.search(tail):
                return InvoiceParser._iso(m.group(1))

            # (2) inline full‑scan ----------
            if m := _DATE_RX.search(line):
                return InvoiceParser._iso(m.group(1))

            # (3) downward sweep ------------
            steps, ptr = 0, idx + 1
            while ptr < len(lines) and steps < window:
                probe = lines[ptr].strip()
                if probe:
                    if m := _DATE_RX.search(probe):
                        return InvoiceParser._iso(m.group(1))
                    steps += 1
                ptr += 1
        return None

    def parse(self, text: str) -> InvoiceExtract:
        text = self._normalise(text)
        lines = text.splitlines()
        values, scores = {}, []

        for key in _LABELS:
            val, score = self._extract_field(key, text, lines)
            values[key] = val
            if score is not None:
                scores.append(score)

        # numeric amounts & date ----------------------------------------------------
        subtotal  = self._to_decimal(values["subtotal"])
        discount  = self._to_decimal(values["discount"]) 
        tax       = self._to_decimal(values["tax"])
        total     = self._to_decimal(values["total"])

        invoice_date = self._find_date_near_label(
            lines, _LABELS["invoice_date"], window=5)
        due_date = self._find_date_near_label(
            lines, _LABELS["due_date"], window=5)
        

        raw_disc  = values["discount"]                    
        raw_tax   = values["tax"]  
        # ---------- DISCOUNT ------------------------------------------------------
        discount     = None
        discount_pct = None

        if raw_disc and "%" in raw_disc:
            m = re.search(r"(\d+(?:\.\d+)?)", raw_disc)
            if m and subtotal is not None:
                discount_pct = Decimal(m.group(1))
                discount = (subtotal * discount_pct) / Decimal(100)
            else:
                discount = self._to_decimal(raw_disc)
        else:
            discount = self._to_decimal(raw_disc) or Decimal(0)


    # ---------- 2)  TAX  (percentage uses discounted base) --------------------
        tax     = None
        tax_pct = None
        discounted_subtotal = (subtotal or Decimal(0)) - discount

        if raw_tax and "%" in str(raw_tax):
            m   = re.search(r"(\d+(?:\.\d+)?)", raw_tax)
            tax = (discounted_subtotal * Decimal(m.group(1)) / 100) if m else Decimal(0)
        else:
            tax = self._to_decimal(raw_tax)

        if tax is None:
            tax = self._infer_tax(raw_tax, subtotal, discount)


        if discount is None:
            discount = Decimal(0)  

        if tax is None:
            tax = self._infer_tax(raw_tax, discounted_subtotal, discount)

        if subtotal is None:
            subtotal = self._infer_subtotal(text)
            discounted_subtotal = subtotal - discount  

        total = discounted_subtotal + (tax or Decimal(0))

        # ----------  Dates ------------------------------------------------------
        if due_date is None and invoice_date:
            if "payment due within 15 days" in text.lower():
                from datetime import timedelta
                # invoice_date is ISO str → parse then add 15 days
                parsed  = dtparser.parse(invoice_date)          # already imported above
                due_date = (parsed + timedelta(days=15)).date().isoformat()

        if invoice_date:
            values["invoice_date"] = invoice_date

        if due_date:
            values["due_date"] = due_date

        # currency detection -------------------------------------------------
        currency = self._detect_currency(text)
        conf = sum(scores) / len(scores) if scores else 0
        if conf < self.min_conf:
            raise ParseError(f"Low score ({conf:.2f}). Text probably not an invoice.")

        return InvoiceExtract(
            invoice_number = values["invoice_number"],
            invoice_date   = self._to_date(values["invoice_date"]),
            due_date       = self._to_date(values["due_date"]),
            vendor         = values["vendor"],
            subtotal       = subtotal,
            discount       = discount,
            tax            = tax,
            total          = total,
            currency       = currency,
            items          = self._extract_items(lines),
            score     = conf,
            raw_text       = text,
        )

    # ----------------------------------------------------------------------
    # helpers
    # ----------------------------------------------------------------------
    @staticmethod
    def _normalise(t: str) -> str:
        t = re.sub(r"[ \t]{2,}", " ", t)
        t = re.sub(r"(\r\n|\r)", "\n", t)
        return t.strip()

    def _extract_field(self, key: str, full: str, lines: List[str]) -> tuple[Optional[str], Optional[float]]:
        if (m := re.search(rf"(?:{'|'.join(map(re.escape, _LABELS[key]))})\s*[:#]?\s*(.+)", full, re.I)):
            return m.group(1).split("\n")[0].strip(), 1.0

        idx = self._label_index(key, lines)
        if idx is not None and idx + 1 < len(lines):
            return lines[idx + 1].strip(), 0.8
        return None, None

    def _label_index(self, key: str, lines: List[str]) -> Optional[int]:
        canon_targets = _CANON[key]
        for i, l in enumerate(lines):
            cl = re.sub(r"[^a-z0-9]", "", l.lower())
            if any(t in cl for t in canon_targets):
                return i
            if any(fuzz.partial_ratio(lbl, l.lower()) > 85 for lbl in _LABELS[key]):
                return i
        return None

    @staticmethod
    def _to_decimal(seg: Optional[str]) -> Optional[Decimal]:
        if not seg:
            return None
        seg = seg.replace(",", "")
        seg = re.sub(r"[$€£₹\s]", "", seg)
        if (m := re.search(r"\d+(?:\.\d+)?", seg)):
            return Decimal(m.group())
        return None

    @staticmethod
    def _to_date(seg: Optional[str]) -> Optional[str]:
        if not seg:
            return None
        dt = dateparser.parse(seg, settings=_DATE_STYLES)
        return dt.strftime("%Y-%m-%d") if dt else None

    @staticmethod
    def _detect_currency(text: str) -> Optional[str]:
        if (m := re.search(r"[$€£₹]", text)):
            return _CURRENCY_SIGNS[m.group()]
        if (m := re.search(r"\b(USD|EUR|GBP|INR|AED|CAD|AUD)\b", text, re.I)):
            return m.group().upper()
        return None

    @staticmethod
    def _infer_tax(raw_seg: Optional[str], subtotal: Optional[Decimal], discount: Decimal) -> Optional[Decimal]:
        if raw_seg and "%" in raw_seg and subtotal is not None:
            pct = Decimal(re.search(r"(\d+(?:\.\d+)?)", raw_seg).group(1))
            return (subtotal - discount) * (pct / 100)
        return None

    @staticmethod
    def _infer_subtotal(text: str) -> Optional[Decimal]:
        # very naive fallback: largest amount before 'total'
        prices = [Decimal(m.replace(",", "")) for m in re.findall(AMOUNT_RE, text)]
        return max(prices) if prices else None

    # ---- table items ------------------------------------------------------
    @staticmethod
    def _extract_items(lines: List[str]) -> List[Dict[str, Any]]:
        pat = re.compile(r"^(.*?)\s+(\d+)\s+([0-9,]+(?:\.\d{1,4})?)\s+([0-9,]+(?:\.\d{1,4})?)$")
        out = []
        for ln in lines:
            if (m := pat.match(ln.strip())):
                desc, qty, rate, amt = m.groups()
                out.append(dict(
                    item      = desc.strip(),
                    quantity  = int(qty),
                    rate      = Decimal(rate.replace(",", "")),
                    amount    = Decimal(amt.replace(",", "")),
                ))
        return out


class ParseError(RuntimeError):
    """Raised when invoice score < threshold or structure invalid."""