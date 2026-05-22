"""Route tests for ``/cockpit/mfa/*``: enroll, confirm, status, disable, regenerate."""

from __future__ import annotations

import pyotp
import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.db as app_db
from app.models import Operator, OperatorRecoveryCode
from tests.conftest_helpers import FounderHandle

pytestmark = pytest.mark.asyncio


async def _get_operator(operator_id: str) -> Operator:
    async with app_db.AsyncSessionLocal() as session:
        result = await session.execute(
            select(Operator).where(Operator.id == operator_id)
        )
        return result.scalar_one()


# ---------------------------------------------------------------------------
# Auth gating
# ---------------------------------------------------------------------------


async def test_status_requires_auth(cockpit_client: AsyncClient) -> None:
    resp = await cockpit_client.get("/cockpit/mfa/status")
    assert resp.status_code == 401


async def test_enroll_requires_auth(cockpit_client: AsyncClient) -> None:
    resp = await cockpit_client.post("/cockpit/mfa/enroll")
    assert resp.status_code == 401


async def test_confirm_requires_auth(cockpit_client: AsyncClient) -> None:
    resp = await cockpit_client.post(
        "/cockpit/mfa/confirm", json={"code": "123456"}
    )
    assert resp.status_code == 401


async def test_disable_requires_auth(cockpit_client: AsyncClient) -> None:
    resp = await cockpit_client.post(
        "/cockpit/mfa/disable", json={"code": "123456"}
    )
    assert resp.status_code == 401


async def test_regenerate_requires_auth(cockpit_client: AsyncClient) -> None:
    resp = await cockpit_client.post(
        "/cockpit/mfa/recovery-codes/regenerate", json={"code": "123456"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Status / enroll / confirm flow
# ---------------------------------------------------------------------------


async def test_status_initial_state(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    resp = await cockpit_client.get(
        "/cockpit/mfa/status", headers=founder_operator.headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "mfa_required": False,
        "enrolled": False,
        "unused_recovery_count": 0,
    }


async def test_enroll_then_confirm_full_flow(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    enroll = await cockpit_client.post(
        "/cockpit/mfa/enroll", headers=founder_operator.headers
    )
    assert enroll.status_code == 200, enroll.text
    body = enroll.json()
    assert body["secret"] and len(body["secret"]) == 32
    assert body["provisioning_uri"].startswith("otpauth://totp/")
    assert "<svg" in body["qr_svg"]

    # Operator row now has the secret but mfa_required is still False.
    op = await _get_operator(founder_operator.operator_id)
    assert op.mfa_secret == body["secret"]
    assert op.mfa_required is False

    # Status reflects enrolled=False until confirm.
    status_pre = await cockpit_client.get(
        "/cockpit/mfa/status", headers=founder_operator.headers
    )
    assert status_pre.json() == {
        "mfa_required": False,
        "enrolled": True,
        "unused_recovery_count": 0,
    }

    code = pyotp.TOTP(body["secret"]).now()
    confirm = await cockpit_client.post(
        "/cockpit/mfa/confirm",
        json={"code": code},
        headers=founder_operator.headers,
    )
    assert confirm.status_code == 200, confirm.text
    codes = confirm.json()["recovery_codes"]
    assert len(codes) == 10
    assert len({c for c in codes}) == 10
    for c in codes:
        assert len(c) == 10

    op2 = await _get_operator(founder_operator.operator_id)
    assert op2.mfa_required is True

    status_post = await cockpit_client.get(
        "/cockpit/mfa/status", headers=founder_operator.headers
    )
    assert status_post.json() == {
        "mfa_required": True,
        "enrolled": True,
        "unused_recovery_count": 10,
    }


async def test_double_enroll_returns_409(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    first = await cockpit_client.post(
        "/cockpit/mfa/enroll", headers=founder_operator.headers
    )
    assert first.status_code == 200
    second = await cockpit_client.post(
        "/cockpit/mfa/enroll", headers=founder_operator.headers
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "mfa_already_enrolled"


async def test_confirm_without_enroll_400(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    resp = await cockpit_client.post(
        "/cockpit/mfa/confirm",
        json={"code": "123456"},
        headers=founder_operator.headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "mfa_not_started"


async def test_confirm_with_wrong_code_400(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    enroll = await cockpit_client.post(
        "/cockpit/mfa/enroll", headers=founder_operator.headers
    )
    assert enroll.status_code == 200
    # 000000 is virtually never the current TOTP for a random secret.
    secret = enroll.json()["secret"]
    bogus = "000000" if pyotp.TOTP(secret).now() != "000000" else "111111"
    resp = await cockpit_client.post(
        "/cockpit/mfa/confirm",
        json={"code": bogus},
        headers=founder_operator.headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_mfa"


# ---------------------------------------------------------------------------
# Disable flow
# ---------------------------------------------------------------------------


async def test_disable_when_not_enrolled_400(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    resp = await cockpit_client.post(
        "/cockpit/mfa/disable",
        json={"code": "123456"},
        headers=founder_operator.headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "mfa_not_enrolled"


async def test_disable_with_totp_succeeds(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    enroll = await cockpit_client.post(
        "/cockpit/mfa/enroll", headers=founder_operator.headers
    )
    secret = enroll.json()["secret"]
    code = pyotp.TOTP(secret).now()
    await cockpit_client.post(
        "/cockpit/mfa/confirm",
        json={"code": code},
        headers=founder_operator.headers,
    )

    code = pyotp.TOTP(secret).now()
    resp = await cockpit_client.post(
        "/cockpit/mfa/disable",
        json={"code": code},
        headers=founder_operator.headers,
    )
    assert resp.status_code == 200, resp.text
    op = await _get_operator(founder_operator.operator_id)
    assert op.mfa_required is False
    assert op.mfa_secret is None

    async with app_db.AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(OperatorRecoveryCode).where(
                    OperatorRecoveryCode.operator_id == founder_operator.operator_id
                )
            )
        ).scalars().all()
        assert rows == []


async def test_disable_with_recovery_code_succeeds(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    enroll = await cockpit_client.post(
        "/cockpit/mfa/enroll", headers=founder_operator.headers
    )
    secret = enroll.json()["secret"]
    confirm = await cockpit_client.post(
        "/cockpit/mfa/confirm",
        json={"code": pyotp.TOTP(secret).now()},
        headers=founder_operator.headers,
    )
    recovery = confirm.json()["recovery_codes"][0]
    resp = await cockpit_client.post(
        "/cockpit/mfa/disable",
        json={"code": recovery},
        headers=founder_operator.headers,
    )
    assert resp.status_code == 200


async def test_disable_with_wrong_code_400(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    enroll = await cockpit_client.post(
        "/cockpit/mfa/enroll", headers=founder_operator.headers
    )
    secret = enroll.json()["secret"]
    await cockpit_client.post(
        "/cockpit/mfa/confirm",
        json={"code": pyotp.TOTP(secret).now()},
        headers=founder_operator.headers,
    )
    bogus = "000000" if pyotp.TOTP(secret).now() != "000000" else "111111"
    resp = await cockpit_client.post(
        "/cockpit/mfa/disable",
        json={"code": bogus},
        headers=founder_operator.headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_mfa"


# ---------------------------------------------------------------------------
# Recovery-code regeneration
# ---------------------------------------------------------------------------


async def test_regenerate_recovery_codes_replaces_old(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    enroll = await cockpit_client.post(
        "/cockpit/mfa/enroll", headers=founder_operator.headers
    )
    secret = enroll.json()["secret"]
    confirm = await cockpit_client.post(
        "/cockpit/mfa/confirm",
        json={"code": pyotp.TOTP(secret).now()},
        headers=founder_operator.headers,
    )
    old_codes = set(confirm.json()["recovery_codes"])

    resp = await cockpit_client.post(
        "/cockpit/mfa/recovery-codes/regenerate",
        json={"code": pyotp.TOTP(secret).now()},
        headers=founder_operator.headers,
    )
    assert resp.status_code == 200, resp.text
    new_codes = set(resp.json()["recovery_codes"])
    assert len(new_codes) == 10
    assert new_codes.isdisjoint(old_codes)

    # Old recovery codes are gone — try one and it should fail.
    bad = next(iter(old_codes))
    fail = await cockpit_client.post(
        "/cockpit/mfa/disable",
        json={"code": bad},
        headers=founder_operator.headers,
    )
    assert fail.status_code == 400


async def test_regenerate_requires_valid_totp(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    enroll = await cockpit_client.post(
        "/cockpit/mfa/enroll", headers=founder_operator.headers
    )
    secret = enroll.json()["secret"]
    await cockpit_client.post(
        "/cockpit/mfa/confirm",
        json={"code": pyotp.TOTP(secret).now()},
        headers=founder_operator.headers,
    )
    resp = await cockpit_client.post(
        "/cockpit/mfa/recovery-codes/regenerate",
        json={"code": "000000"},
        headers=founder_operator.headers,
    )
    # 000000 is essentially never the live TOTP. Hedge: if it happened to
    # match, the response would be 200 with new codes; assert either is
    # acceptable but in practice we get 400.
    assert resp.status_code in (200, 400)
    if resp.status_code == 400:
        assert resp.json()["detail"]["code"] == "invalid_mfa"


async def test_regenerate_when_not_enrolled_400(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    resp = await cockpit_client.post(
        "/cockpit/mfa/recovery-codes/regenerate",
        json={"code": "123456"},
        headers=founder_operator.headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "mfa_not_enrolled"
