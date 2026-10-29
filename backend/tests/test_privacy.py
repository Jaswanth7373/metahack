from app.services.privacy import PrivacyEngine, RulesDetector, Vault

TEXT = """Customer: Jordan Ellis
Service address: 12 Harbor View Road, Apt 4, Lakeside, WA 98001
Account number: 5520-1199-0044
Phone: (206) 555-0177   Email: jordan.ellis@example.com
Date of birth: 03/05/1988   SSN: 123-45-6789
Dear Mr. Ellis, please contact Customer Service."""


def redact(text=TEXT):
    v = Vault()
    return PrivacyEngine("rules").redact(text, v), v


def test_detects_every_pii_type():
    types = {s.type for s in RulesDetector().detect(TEXT)}
    assert {"NAME", "ADDRESS", "ACCOUNT", "PHONE", "EMAIL", "DOB", "ID"} <= types


def test_placeholders_replace_all_values_and_are_stable():
    red, v = redact()
    for original in v.originals():
        assert original not in red
    assert red.count("[NAME_1]") == 2  # full name and "Mr. Ellis" share one placeholder
    assert "Customer Service" in red  # organisations are not people
    again = PrivacyEngine("rules").redact("Call Jordan Ellis at (206) 555-0177", v)
    assert again == "Call [NAME_1] at [PHONE_1]"


def test_restore_round_trip_is_local():
    red, v = redact()
    assert v.restore("[NAME_1] / [ACCOUNT_1]") == "Jordan Ellis / 5520-1199-0044"
    assert "Jordan Ellis" in v.restore(red)


def test_leak_counter():
    _, v = redact()
    assert v.leaked_values('{"content": "[NAME_1]"}') == 0
    assert v.leaked_values('{"content": "hi Jordan  Ellis 5520-1199-0044"}') == 2


def test_unreachable_glimmer_falls_back_to_rules_and_says_so():
    eng = PrivacyEngine("local", "http://127.0.0.1:9", "muse-glimmer")
    assert eng.info()["mode"] == "rules"
    assert "fallback" in eng.info()["label"].lower()
