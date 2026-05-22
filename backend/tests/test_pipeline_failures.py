"""Tests for the submission pipeline's failure classification.

Exercises ``app.services.submission_pipeline._classify_failure`` directly so
we don't depend on a real submitter implementation, and additionally runs
``process_submission`` end-to-end with a monkeypatched submitter that raises
each exception type to confirm DB state transitions.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.models import PortalPlatform, SubmissionStatus
from app.services import submission_pipeline as pipeline
from app.services.exceptions import (
    ConsentMissing,
    OnceError,
    PortalCaptcha,
    PortalPermanentError,
    PortalRateLimited,
    PortalTransientError,
    PortalUnsupported,
    SubmissionNotClaimable,
    SubmitterNotFound,
)
from app.services.submission_pipeline import (
    MAX_ATTEMPTS,
    _classify_failure,
    process_submission,
)
from tests.factories import (
    make_consent,
    make_portal,
    make_submission,
    make_supplier,
    make_tenant,
)


# ---------------------------------------------------------------------------
# Pure classification table
# ---------------------------------------------------------------------------


class TestClassifyFailure:
    @pytest.mark.parametrize(
        "exc,attempt,expected",
        [
            (PortalCaptcha("captcha"), 1, SubmissionStatus.BLOCKED),
            (PortalCaptcha("captcha"), MAX_ATTEMPTS, SubmissionStatus.BLOCKED),
            (PortalRateLimited("rl"), 1, SubmissionStatus.RETRYING),
            (PortalTransientError("t"), 2, SubmissionStatus.RETRYING),
            (PortalRateLimited("rl"), MAX_ATTEMPTS, SubmissionStatus.FAILED),
            (PortalTransientError("t"), MAX_ATTEMPTS, SubmissionStatus.FAILED),
            (PortalUnsupported("u"), 1, SubmissionStatus.PLATFORM_UNSUPPORTED),
            (PortalPermanentError("p"), 1, SubmissionStatus.FAILED),
            (ConsentMissing("c"), 1, SubmissionStatus.FAILED),
            (SubmitterNotFound("s"), 1, SubmissionStatus.FAILED),
        ],
    )
    def test_known_exception_mappings(
        self, exc: BaseException, attempt: int, expected: SubmissionStatus
    ) -> None:
        status, msg = _classify_failure(exc, attempt)
        assert status is expected
        assert isinstance(msg, str)
        assert msg

    def test_generic_oncerror_maps_to_failed(self) -> None:
        class CustomOnce(OnceError):
            pass

        status, _ = _classify_failure(CustomOnce("x"), 1)
        assert status is SubmissionStatus.FAILED

    def test_unknown_exception_maps_to_failed(self) -> None:
        status, msg = _classify_failure(RuntimeError("boom"), 1)
        assert status is SubmissionStatus.FAILED
        assert "RuntimeError" in msg

    def test_max_attempts_message_includes_counts(self) -> None:
        _, msg = _classify_failure(PortalRateLimited("rl"), MAX_ATTEMPTS)
        assert "max_attempts_exceeded" in msg
        assert str(MAX_ATTEMPTS) in msg


# ---------------------------------------------------------------------------
# process_submission end-to-end (with monkeypatched submitter)
# ---------------------------------------------------------------------------


async def _seed(async_session) -> str:
    tenant = await make_tenant(async_session)
    supplier = await make_supplier(async_session, tenant)
    portal = await make_portal(async_session, platform=PortalPlatform.AMTRUST)
    consent = await make_consent(async_session, supplier=supplier, portal=portal)
    submission = await make_submission(
        async_session, supplier=supplier, portal=portal, consent=consent
    )
    await async_session.commit()
    return submission.id


def _raising_submitter(exc: BaseException) -> Any:
    class _S:
        async def submit(self, **_: Any) -> None:
            raise exc

    return _S()


class TestProcessSubmission:
    async def test_captcha_marks_blocked(
        self, async_session, signing_key, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            pipeline,
            "_get_submitter",
            lambda _platform: _raising_submitter(PortalCaptcha("captcha")),
        )
        sid = await _seed(async_session)
        result = await process_submission(sid, async_session)
        assert result.status is SubmissionStatus.BLOCKED

    async def test_rate_limited_marks_retrying(
        self, async_session, signing_key, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            pipeline,
            "_get_submitter",
            lambda _platform: _raising_submitter(PortalRateLimited("rl")),
        )
        sid = await _seed(async_session)
        result = await process_submission(sid, async_session)
        assert result.status is SubmissionStatus.RETRYING

    async def test_permanent_marks_failed(
        self, async_session, signing_key, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            pipeline,
            "_get_submitter",
            lambda _platform: _raising_submitter(PortalPermanentError("p")),
        )
        sid = await _seed(async_session)
        result = await process_submission(sid, async_session)
        assert result.status is SubmissionStatus.FAILED

    async def test_unsupported_marks_platform_unsupported(
        self, async_session, signing_key, monkeypatch
    ) -> None:
        def _no_submitter(_platform: PortalPlatform) -> Any:
            raise PortalUnsupported("nope", platform=_platform.value)

        monkeypatch.setattr(pipeline, "_get_submitter", _no_submitter)
        sid = await _seed(async_session)
        result = await process_submission(sid, async_session)
        assert result.status is SubmissionStatus.PLATFORM_UNSUPPORTED

    async def test_submitter_not_found_marks_failed(
        self, async_session, signing_key, monkeypatch
    ) -> None:
        def _no_submitter(_platform: PortalPlatform) -> Any:
            raise SubmitterNotFound("no", platform=_platform.value)

        monkeypatch.setattr(pipeline, "_get_submitter", _no_submitter)
        sid = await _seed(async_session)
        result = await process_submission(sid, async_session)
        assert result.status is SubmissionStatus.FAILED

    async def test_double_claim_raises_not_claimable(
        self, async_session, signing_key, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            pipeline,
            "_get_submitter",
            lambda _platform: _raising_submitter(PortalPermanentError("p")),
        )
        sid = await _seed(async_session)
        await process_submission(sid, async_session)
        # Re-running should fail to claim — submission is now FAILED, not in
        # {QUEUED, RETRYING}.
        with pytest.raises(SubmissionNotClaimable):
            await process_submission(sid, async_session)

    async def test_success_path_signs_receipt(
        self, async_session, signing_key, monkeypatch
    ) -> None:
        class _OkSubmitter:
            async def submit(self, **_: Any) -> dict[str, str]:
                return {"status": "ok"}

        monkeypatch.setattr(
            pipeline, "_get_submitter", lambda _p: _OkSubmitter()
        )
        sid = await _seed(async_session)
        result = await process_submission(sid, async_session)
        assert result.status is SubmissionStatus.COMPLETED
        assert result.receipt_id is not None
