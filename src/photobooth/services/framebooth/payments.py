"""Payments of the kiosk: bank-transfer QR (VietQR), discount codes, automatic confirmation of transfers
and loyalty stamps.

A payment request ("intent") is created for every amount the guest has to pay (package, retake, extra
print copies). Its ``reference`` is written into the VietQR transfer note, so an incoming transfer can be
matched to it. Transfers are confirmed automatically when a SePay account is linked (``SEPAY_API_TOKEN``
in ``.env``, polled every few seconds, no public URL needed; or the SePay webhook with ``SEPAY_WEBHOOK_KEY``).
Without it the staff confirms with the PIN as before.

Amounts are always computed here from ``appconfig.framebooth``, never taken from the kiosk.
"""

import logging
import re
import secrets
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Literal

from ...appconfig import appconfig
from .. import credentials
from .ledger import ledger

logger = logging.getLogger(__name__)

Purpose = Literal["package", "retake", "copies"]
Status = Literal["pending", "partial", "paid", "cancelled"]

SEPAY_TOKEN_KEY = "SEPAY_API_TOKEN"
SEPAY_WEBHOOK_KEY = "SEPAY_WEBHOOK_KEY"
_SEPAY_LIST_URL = "https://my.sepay.vn/userapi/transactions/list"
_POLL_SECONDS = 4
_PHONE = re.compile(r"^0[35789][0-9]{8}$")


class PaymentError(ValueError):
    """Shown to the guest as is."""


# ───────── VietQR (EMVCo merchant-presented QR, NAPAS 247) ─────────


def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def _crc16(data: str) -> str:
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def vietqr_payload(bank_bin: str, account: str, amount: int, note: str) -> str:
    """Text of a VietQR code every Vietnamese banking app can scan, amount and note prefilled."""
    beneficiary = _tlv("00", bank_bin) + _tlv("01", account)
    merchant = _tlv("00", "A000000727") + _tlv("01", beneficiary) + _tlv("02", "QRIBFTTA")
    payload = (
        _tlv("00", "01")
        + _tlv("01", "12")
        + _tlv("38", merchant)
        + _tlv("53", "704")
        + _tlv("54", str(amount))
        + _tlv("58", "VN")
        + _tlv("62", _tlv("08", note))
        + "6304"
    )
    return payload + _crc16(payload)


def bank_qr_configured() -> bool:
    config = appconfig.framebooth
    return bool(config.bank_bin and config.bank_account_number)


def auto_confirm_available() -> bool:
    return bool(credentials.get_value(SEPAY_TOKEN_KEY) or credentials.get_value(SEPAY_WEBHOOK_KEY)) and bank_qr_configured()


# ───────── discount codes ─────────


@dataclass
class Discount:
    code: str
    amount: int
    label: str


def check_voucher(code: str, purpose: Purpose, list_amount: int) -> Discount:
    """Discount for ``code`` on an amount; raises PaymentError with a guest-friendly reason."""
    code = code.strip().upper()
    if not code:
        raise PaymentError("Hãy nhập mã giảm giá")
    if purpose != "package":
        raise PaymentError("Mã giảm giá chỉ áp dụng cho gói chụp")

    reward = ledger.reward_code(code)
    if reward:
        if reward["used_at"]:
            raise PaymentError("Mã này đã được dùng")
        if reward["valid_until"] < date.today().isoformat():
            raise PaymentError("Mã này đã hết hạn")
        return Discount(code, list_amount, "Quà khách quen · miễn phí")

    voucher = next((v for v in appconfig.framebooth.vouchers if v.code.upper() == code and v.enabled), None)
    if not voucher:
        raise PaymentError("Mã không đúng hoặc không còn hiệu lực")
    if voucher.valid_until and voucher.valid_until < date.today().isoformat():
        raise PaymentError("Mã này đã hết hạn")
    if voucher.max_uses and ledger.voucher_use_count(code) >= voucher.max_uses:
        raise PaymentError("Mã này đã hết lượt dùng")
    amount = list_amount * voucher.discount_percent // 100 if voucher.discount_percent else voucher.discount_amount
    amount = min(amount, list_amount)
    label = f"Giảm {voucher.discount_percent}%" if voucher.discount_percent else f"Giảm {amount:,}đ".replace(",", ".")
    return Discount(code, amount, label)


# ───────── payment requests ─────────


@dataclass
class PaymentIntent:
    reference: str
    session_id: str
    purpose: Purpose
    quantity: int  # slot count, retake shots or extra copies
    list_amount: int
    discount: int
    voucher_code: str | None
    amount: int
    expires_at: float
    received: int = 0
    status: Status = "pending"
    method: str | None = None
    created_at: float = field(default_factory=time.time)

    @property
    def remaining(self) -> int:
        return max(0, self.amount - self.received)

    def public(self) -> dict:
        config = appconfig.framebooth
        qr = None
        if bank_qr_configured() and self.remaining > 0:
            qr = vietqr_payload(config.bank_bin, config.bank_account_number, self.remaining, self.reference)
        return {
            **{key: value for key, value in asdict(self).items() if key not in ("created_at",)},
            "remaining": self.remaining,
            "expires_in": max(0, round(self.expires_at - time.time())),
            "expired": self.status in ("pending", "partial") and time.time() > self.expires_at,
            "qr_payload": qr,
            "bank_account_name": config.bank_account_name if qr else "",
            "auto_confirm": auto_confirm_available(),
        }


def list_amount(purpose: Purpose, quantity: int) -> int:
    config = appconfig.framebooth
    if purpose == "retake":
        return quantity * config.retake_price
    if purpose == "copies":
        return quantity * config.extra_copy_price
    price = next((tier.price for tier in config.pricing if tier.slot_count == quantity), None)
    if price is None:
        raise PaymentError("Gói chụp không tồn tại")
    return price


def normalize_note(text: str) -> str:
    """Banks strip spaces and punctuation from transfer notes; compare on upper-case letters and digits only."""
    return re.sub(r"[^A-Z0-9]", "", text.upper())


class PaymentBook:
    def __init__(self) -> None:
        self._intents: dict[str, PaymentIntent] = {}
        self._lock = threading.Lock()
        self._poller: threading.Thread | None = None
        self._stop = threading.Event()

    # ── create / read ──

    def create(self, session_id: str, purpose: Purpose, quantity: int, voucher_code: str | None = None) -> PaymentIntent:
        config = appconfig.framebooth
        if purpose == "retake" and not 1 <= quantity <= config.retake_max_shots:
            raise PaymentError("Số lần chụp lại không hợp lệ")
        if purpose == "copies" and not 1 <= quantity < config.max_print_copies:
            raise PaymentError("Số bản in không hợp lệ")

        base = list_amount(purpose, quantity)
        discount = check_voucher(voucher_code, purpose, base) if voucher_code else None
        with self._lock:
            self._purge()
            # same session and purpose: replace the older (e.g. expired or re-priced) request
            for reference, old in list(self._intents.items()):
                if old.session_id == session_id and old.purpose == purpose and old.status in ("pending", "partial") and not old.received:
                    del self._intents[reference]
            reference = self._new_reference(session_id, purpose)
            intent = PaymentIntent(
                reference=reference,
                session_id=session_id,
                purpose=purpose,
                quantity=quantity,
                list_amount=base,
                discount=discount.amount if discount else 0,
                voucher_code=discount.code if discount else None,
                amount=base - (discount.amount if discount else 0),
                expires_at=time.time() + config.payment_qr_expiry_seconds,
            )
            self._intents[reference] = intent

        if intent.amount == 0:  # free with a voucher / loyalty reward: nothing to pay
            self._settle(intent, "voucher")
        else:
            self._ensure_poller()
        return intent

    def get(self, reference: str) -> PaymentIntent | None:
        with self._lock:
            return self._intents.get(reference)

    def renew(self, reference: str) -> PaymentIntent | None:
        """New QR lifetime for an expired request (the reference stays, so a late transfer still matches)."""
        with self._lock:
            intent = self._intents.get(reference)
            if intent and intent.status in ("pending", "partial"):
                intent.expires_at = time.time() + appconfig.framebooth.payment_qr_expiry_seconds
        if intent:
            self._ensure_poller()
        return intent

    def cancel(self, reference: str) -> None:
        with self._lock:
            intent = self._intents.get(reference)
            if intent and intent.status in ("pending", "partial") and not intent.received:
                intent.status = "cancelled"

    def confirm_by_staff(self, reference: str) -> PaymentIntent | None:
        """The staff typed the PIN: everything still open counts as paid at the counter."""
        intent = self.get(reference)
        if intent and intent.status in ("pending", "partial"):
            self._settle(intent, "pin")
        return intent

    # ── transfers ──

    def apply_transfer(self, tx_id: str, amount: int, content: str) -> PaymentIntent | None:
        """Credit an incoming bank transfer to the request named in its note. Idempotent per transaction id."""
        note = normalize_note(content)
        with self._lock:
            intent = next(
                (i for i in self._intents.values() if normalize_note(i.reference) in note and i.status != "cancelled"),
                None,
            )
        if not ledger.record_transfer(tx_id, amount, content, intent.reference if intent else None):
            return intent  # seen before
        if not intent:
            logger.info(f"bank transfer {tx_id} of {amount} did not match any open payment: {content!r}")
            return None
        if intent.status == "paid":
            logger.warning(f"extra transfer {tx_id} of {amount} for already paid {intent.reference}")
            return intent

        with self._lock:
            intent.received += amount
            paid = intent.received >= intent.amount
            if not paid:
                intent.status = "partial"
                intent.expires_at = max(intent.expires_at, time.time() + appconfig.framebooth.payment_qr_expiry_seconds)
        logger.info(f"bank transfer {tx_id}: {amount} for {intent.reference} ({intent.received}/{intent.amount})")
        if paid:
            self._settle(intent, "transfer")
        return intent

    # ── internals ──

    def _new_reference(self, session_id: str, purpose: Purpose) -> str:
        base = "TSL" + normalize_note(session_id)[-8:]
        suffix = {"package": "", "retake": "R", "copies": "C"}[purpose]
        reference = base + suffix
        counter = 2
        while reference in self._intents:
            reference = f"{base}{suffix}{counter}"
            counter += 1
        return reference

    def _settle(self, intent: PaymentIntent, method: str) -> None:
        with self._lock:
            if intent.status == "paid":
                return
            intent.status = "paid"
            intent.method = method
        try:
            book_method = "transfer" if method == "transfer" else ("voucher" if method == "voucher" else "pin")
            if intent.purpose == "package":
                if intent.voucher_code and ledger.reward_code(intent.voucher_code):
                    ledger.use_reward_code(intent.voucher_code, intent.session_id)
                ledger.record_package_paid(intent.session_id, intent.quantity, intent.list_amount, intent.discount, intent.voucher_code, book_method)
            elif intent.purpose == "retake":
                ledger.record_retake_paid(intent.session_id, intent.quantity, intent.amount)
            else:
                ledger.record_copies_paid(intent.session_id, intent.quantity, intent.amount)
        except Exception as exc:
            logger.error(f"could not write kiosk ledger: {exc}")

    def _purge(self) -> None:
        cutoff = time.time() - 6 * 3600
        for reference in [r for r, i in self._intents.items() if i.created_at < cutoff]:
            del self._intents[reference]

    def _open_requests(self) -> bool:
        with self._lock:
            return any(i.status in ("pending", "partial") and time.time() < i.expires_at + 120 for i in self._intents.values())

    def _ensure_poller(self) -> None:
        if not credentials.get_value(SEPAY_TOKEN_KEY) or (self._poller and self._poller.is_alive()):
            return
        self._stop.clear()
        self._poller = threading.Thread(target=self._poll_loop, name="sepay-poller", daemon=True)
        self._poller.start()

    def _poll_loop(self) -> None:
        """Ask SePay for the latest incoming transfers while a payment is open, then stop."""
        while not self._stop.is_set() and self._open_requests():
            try:
                self.poll_sepay()
            except Exception as exc:
                logger.warning(f"SePay polling failed: {exc}")
            self._stop.wait(_POLL_SECONDS)

    def poll_sepay(self) -> None:
        import requests  # noqa: PLC0415

        token = credentials.get_value(SEPAY_TOKEN_KEY)
        params = {"limit": 20}
        if appconfig.framebooth.bank_account_number:
            params["account_number"] = appconfig.framebooth.bank_account_number
        response = requests.get(_SEPAY_LIST_URL, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=8)
        response.raise_for_status()
        for tx in response.json().get("transactions") or []:
            amount_in = int(float(tx.get("amount_in") or 0))
            if amount_in > 0:
                self.apply_transfer(f"sepay-{tx.get('id')}", amount_in, str(tx.get("transaction_content") or ""))

    def stop(self) -> None:
        self._stop.set()


payments = PaymentBook()


# ───────── loyalty ─────────


def add_loyalty_stamp(phone: str, session_id: str) -> dict:
    config = appconfig.framebooth
    phone = re.sub(r"\D", "", phone)
    if not _PHONE.match(phone):
        raise PaymentError("Số điện thoại chưa đúng")
    code = "FREE-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
    valid_until = date.today() + timedelta(days=config.loyalty_reward_valid_days)
    result = ledger.add_loyalty_stamp(phone, session_id, config.loyalty_stamps_for_reward, code, valid_until)
    return {
        **result,
        "target": config.loyalty_stamps_for_reward,
        "reward_valid_until": valid_until.isoformat() if result["reward_code"] else None,
    }
