"""Integration tests for the MFA branch of ``authenticate_operator``.

Covers happy + sad paths for TOTP and recovery codes, MFA-required
without code, MFA-required without enrollment, single-use recovery
codes, and the ±1 step drift window.
"""

from __future__ import annotations

import pyotp
import pytest
import pytest_asyncio
from freezegun import freeze_time
from sqlalchemy import select

import app.db as app_db
from app.models import Operator, OperatorRecoveryCode, OperatorRole, OperatorStatus
from app.services import mfa_totp, operator_auth

pytestmark = pytest.mark.asyncio


STRONG_PWD = "C0ckpit-S3cret-Founder!2026"


async def _seed_operator_with_mfa(
    *,
    email: str,
    mfa_secret: str | None,
    mfa_required: bool = True,
    recovery_codes: list[str] | None = None,
) -> Operator:
    async with app_db.AsyncSessionLocal() as session:
        op = Operator(
            email=email,
            hashed_password=operator_auth.operator_password_hash(STRONG_PWD),
            role=OperatorRole.FOUNDER.value,
            status=OperatorStatus.ACTIVE.value,
            mfa_required=mfa_required,
            mfa_secret=mfa_secret,
        )
        session.add(op)
        await session.flush()
        for code in recovery_codes or []:
            session.add(
                OperatorRecoveryCode(
                    operator_id=op.id,
                    code_hash=mfa_totp.hash_recovery_code(code),
                )
            )
        await session.commit()
        await session.refresh(op)
        return op


@pytest_asyncio.fixture(autouse=True)
async def _engine(_test_engine):  # type: ignore[no-untyped-def]
    yield _test_engine


async def test_login_with_valid_totp_succeeds() -> None:
    secret = mfa_totp.generate_secret()
    await _seed_operator_with_mfa(email="mfa-ok@once.dev", mfa_secret=secret)
    code = pyotp.TOTP(secret).now()
    async with app_db.AsyncSessionLocal() as session:
        op, access, refresh, expires_in = await operator_auth.authenticate_operator(
            session,
            email="mfa-ok@once.dev",
            password=STRONG_PWD,
            ip="127.0.0.1",
            user_agent="pytest",
            totp_code=code,
        )
        await session.commit()
    assert op.email == "mfa-ok@once.dev"
    assert access and refresh
    assert expires_in == operator_auth.ACCESS_TTL_MINUTES * 60


async def test_login_with_wrong_totp_rejected() -> None:
    secret = mfa_totp.generate_secret()
    await _seed_operator_with_mfa(email="mfa-bad@once.dev", mfa_secret=secret)
    async with app_db.AsyncSessionLocal() as session:
        with pytest.raises(operator_auth.OperatorAuthError) as exc:
            await operator_auth.authenticate_operator(
                session,
                email="mfa-bad@once.dev",
                password=STRONG_PWD,
                ip="127.0.0.1",
                user_agent="pytest",
                totp_code="000000",
            )
    assert exc.value.code == "invalid_mfa"
    assert exc.value.status_code == 403


async def test_login_mfa_required_without_code() -> None:
    secret = mfa_totp.generate_secret()
    await _seed_operator_with_mfa(email="mfa-empty@once.dev", mfa_secret=secret)
    async with app_db.AsyncSessionLocal() as session:
        with pytest.raises(operator_auth.OperatorAuthError) as exc:
            await operator_auth.authenticate_operator(
                session,
                email="mfa-empty@once.dev",
                password=STRONG_PWD,
                ip=None,
                user_agent=None,
                totp_code=None,
            )
    assert exc.value.code == "mfa_required"
    assert exc.value.status_code == 403


async def test_login_mfa_required_but_unenrolled() -> None:
    await _seed_operator_with_mfa(
        email="mfa-noenroll@once.dev", mfa_secret=None, mfa_required=True
    )
    async with app_db.AsyncSessionLocal() as session:
        with pytest.raises(operator_auth.OperatorAuthError) as exc:
            await operator_auth.authenticate_operator(
                session,
                email="mfa-noenroll@once.dev",
                password=STRONG_PWD,
                ip=None,
                user_agent=None,
                totp_code="123456",
            )
    assert exc.value.code == "mfa_not_enrolled"
    assert exc.value.status_code == 403


async def test_login_with_recovery_code_succeeds_then_marks_used() -> None:
    secret = mfa_totp.generate_secret()
    recovery = ["RECOVR2345A", "BACKUPCODE2"]
    await _seed_operator_with_mfa(
        email="mfa-rec@once.dev",
        mfa_secret=secret,
        recovery_codes=recovery,
    )
    async with app_db.AsyncSessionLocal() as session:
        op, access, _refresh, _expires = await operator_auth.authenticate_operator(
            session,
            email="mfa-rec@once.dev",
            password=STRONG_PWD,
            ip="127.0.0.1",
            user_agent="pytest",
            totp_code="RECOVR2345A",
        )
        await session.commit()
    assert access

    # The code is now consumed.
    async with app_db.AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(OperatorRecoveryCode).where(
                    OperatorRecoveryCode.operator_id == op.id
                )
            )
        ).scalars().all()
        used = [r for r in rows if r.used_at is not None]
        assert len(used) == 1
        assert used[0].code_hash == mfa_totp.hash_recovery_code("RECOVR2345A")


async def test_login_with_reused_recovery_code_rejected() -> None:
    secret = mfa_totp.generate_secret()
    await _seed_operator_with_mfa(
        email="mfa-rec2@once.dev",
        mfa_secret=secret,
        recovery_codes=["ONESHOTAB2"],
    )
    async with app_db.AsyncSessionLocal() as session:
        await operator_auth.authenticate_operator(
            session,
            email="mfa-rec2@once.dev",
            password=STRONG_PWD,
            ip=None,
            user_agent=None,
            totp_code="ONESHOTAB2",
        )
        await session.commit()

    async with app_db.AsyncSessionLocal() as session:
        with pytest.raises(operator_auth.OperatorAuthError) as exc:
            await operator_auth.authenticate_operator(
                session,
                email="mfa-rec2@once.dev",
                password=STRONG_PWD,
                ip=None,
                user_agent=None,
                totp_code="ONESHOTAB2",
            )
    assert exc.value.code == "invalid_mfa"


async def test_login_recovery_code_normalized_dashes_and_lowercase() -> None:
    secret = mfa_totp.generate_secret()
    await _seed_operator_with_mfa(
        email="mfa-rec3@once.dev",
        mfa_secret=secret,
        recovery_codes=["NORMALCDE2"],
    )
    async with app_db.AsyncSessionLocal() as session:
        op, access, _r, _e = await operator_auth.authenticate_operator(
            session,
            email="mfa-rec3@once.dev",
            password=STRONG_PWD,
            ip=None,
            user_agent=None,
            totp_code="normal-cde2",
        )
        await session.commit()
    assert access
    assert op.email == "mfa-rec3@once.dev"


async def test_login_recovery_code_from_other_operator_rejected() -> None:
    """A valid recovery code belonging to a *different* operator must not work."""

    secret_a = mfa_totp.generate_secret()
    secret_b = mfa_totp.generate_secret()
    await _seed_operator_with_mfa(
        email="op-a@once.dev",
        mfa_secret=secret_a,
        recovery_codes=["OPACODE234"],
    )
    await _seed_operator_with_mfa(
        email="op-b@once.dev",
        mfa_secret=secret_b,
        recovery_codes=[],
    )
    async with app_db.AsyncSessionLocal() as session:
        with pytest.raises(operator_auth.OperatorAuthError) as exc:
            await operator_auth.authenticate_operator(
                session,
                email="op-b@once.dev",
                password=STRONG_PWD,
                ip=None,
                user_agent=None,
                totp_code="OPACODE234",
            )
    assert exc.value.code == "invalid_mfa"


async def test_login_totp_drift_within_window_accepted() -> None:
    secret = mfa_totp.generate_secret()
    await _seed_operator_with_mfa(email="drift@once.dev", mfa_secret=secret)
    with freeze_time("2026-06-01T12:00:00Z") as frozen:
        code = pyotp.TOTP(secret).now()
        frozen.tick(delta=31)
        async with app_db.AsyncSessionLocal() as session:
            op, access, _r, _e = await operator_auth.authenticate_operator(
                session,
                email="drift@once.dev",
                password=STRONG_PWD,
                ip=None,
                user_agent=None,
                totp_code=code,
            )
            await session.commit()
    assert access
    assert op.email == "drift@once.dev"


async def test_login_totp_drift_outside_window_rejected() -> None:
    secret = mfa_totp.generate_secret()
    await _seed_operator_with_mfa(email="drift2@once.dev", mfa_secret=secret)
    with freeze_time("2026-06-01T12:00:00Z") as frozen:
        code = pyotp.TOTP(secret).now()
        frozen.tick(delta=180)  # well outside ±1 step
        async with app_db.AsyncSessionLocal() as session:
            with pytest.raises(operator_auth.OperatorAuthError) as exc:
                await operator_auth.authenticate_operator(
                    session,
                    email="drift2@once.dev",
                    password=STRONG_PWD,
                    ip=None,
                    user_agent=None,
                    totp_code=code,
                )
    assert exc.value.code == "invalid_mfa"


async def test_login_without_mfa_still_works() -> None:
    """Regression: operator with ``mfa_required=False`` is unaffected."""

    async with app_db.AsyncSessionLocal() as session:
        op = Operator(
            email="nomfa@once.dev",
            hashed_password=operator_auth.operator_password_hash(STRONG_PWD),
            role=OperatorRole.FOUNDER.value,
            status=OperatorStatus.ACTIVE.value,
            mfa_required=False,
        )
        session.add(op)
        await session.commit()

    async with app_db.AsyncSessionLocal() as session:
        op, access, _r, _e = await operator_auth.authenticate_operator(
            session,
            email="nomfa@once.dev",
            password=STRONG_PWD,
            ip=None,
            user_agent=None,
            totp_code=None,
        )
        await session.commit()
    assert access
