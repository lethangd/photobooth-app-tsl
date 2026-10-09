from pathlib import Path

import pytest

from photobooth.appconfig import appconfig
from photobooth.services.config.groups.framebooth import FramebootVoucher
from photobooth.services.framebooth import payments as payments_module
from photobooth.services.framebooth.ledger import KioskLedger
from photobooth.services.framebooth.payments import PaymentBook, PaymentError, check_voucher, vietqr_payload


@pytest.fixture
def book(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PaymentBook:
    isolated = KioskLedger(tmp_path / "ledger.sqlite")
    monkeypatch.setattr(payments_module, "ledger", isolated)
    appconfig.framebooth.bank_bin = "970436"
    appconfig.framebooth.bank_account_number = "0123456789"
    return PaymentBook()


def test_vietqr_payload_is_valid_emv():
    payload = vietqr_payload("970436", "0123456789", 70000, "TSLPB123456")
    assert payload.startswith("000201010212")
    assert "0010A000000727" in payload and "QRIBFTTA" in payload
    assert "540570000" in payload and "5802VN" in payload and "0811TSLPB123456" in payload
    # CRC-16/CCITT-FALSE over everything up to and including "6304"
    body, crc = payload[:-4], payload[-4:]
    assert body.endswith("6304") and crc == payments_module._crc16(body)
    # known vector of CRC-16/CCITT-FALSE
    assert payments_module._crc16("123456789") == "29B1"


def test_package_payment_with_voucher_and_partial_transfer(book: PaymentBook):
    appconfig.framebooth.vouchers = [FramebootVoucher(code="TSL-HALLO", discount_amount=10_000)]
    intent = book.create("PB123456", "package", 3, "tsl-hallo")
    public = intent.public()
    assert public["amount"] == 60_000 and public["discount"] == 10_000 and public["qr_payload"]
    assert intent.reference == "TSLPB123456"

    book.apply_transfer("tx1", 50_000, "MBVCB.123 TSLPB123456 chuyen tien")
    assert intent.status == "partial" and intent.remaining == 10_000
    assert "5405" + "10000" in intent.public()["qr_payload"]  # the new QR asks only for the rest

    book.apply_transfer("tx1", 50_000, "TSLPB123456")  # same transaction again: ignored
    assert intent.remaining == 10_000
    book.apply_transfer("tx2", 10_000, "tsl pb123456")
    assert intent.status == "paid" and intent.method == "transfer"

    session = payments_module.ledger.session("PB123456")
    assert session["total"] == 60_000 and session["payment_method"] == "transfer" and session["voucher_code"] == "TSL-HALLO"
    assert payments_module.ledger.voucher_use_count("TSL-HALLO") == 1


def test_voucher_rules(book: PaymentBook):
    appconfig.framebooth.vouchers = [
        FramebootVoucher(code="HALF", discount_amount=0, discount_percent=50),
        FramebootVoucher(code="OLD", valid_until="2000-01-01"),
        FramebootVoucher(code="OFF", enabled=False),
    ]
    assert check_voucher("half", "package", 70_000).amount == 35_000
    for code in ("OLD", "OFF", "NOPE"):
        with pytest.raises(PaymentError):
            check_voucher(code, "package", 70_000)
    with pytest.raises(PaymentError):
        check_voucher("HALF", "retake", 10_000)


def test_staff_pin_confirms_retake_and_copies(book: PaymentBook):
    retake = book.create("PB999", "retake", 2)
    assert retake.amount == 2 * appconfig.framebooth.retake_price and retake.reference.endswith("R")
    book.confirm_by_staff(retake.reference)
    copies = book.create("PB999", "copies", 1)
    book.confirm_by_staff(copies.reference)
    session = payments_module.ledger.session("PB999")
    assert session["retake_shots"] == 2 and session["copies"] == 2
    assert session["total"] == 2 * appconfig.framebooth.retake_price + appconfig.framebooth.extra_copy_price


def test_loyalty_reward_is_a_free_session(book: PaymentBook):
    appconfig.framebooth.loyalty_stamps_for_reward = 2
    first = payments_module.add_loyalty_stamp("0912 345 678", "S1")
    again = payments_module.add_loyalty_stamp("0912345678", "S1")  # same session counts once
    assert first["stamps"] == 1 and not again["new_stamp"]
    second = payments_module.add_loyalty_stamp("0912345678", "S2")
    code = second["reward_code"]
    assert code and code.startswith("FREE-") and second["stamps"] == 2

    free = book.create("S3", "package", 2, code)
    assert free.amount == 0 and free.status == "paid" and free.method == "voucher"
    with pytest.raises(PaymentError):
        book.create("S4", "package", 2, code)  # single use
    with pytest.raises(PaymentError):
        payments_module.add_loyalty_stamp("12345", "S5")
