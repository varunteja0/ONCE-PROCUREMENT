"""CLI: create the first cockpit operator.

Usage::

    python -m scripts.create_operator --email founder@once.dev --role founder --grant-all

Prompts for the password interactively (via :mod:`getpass`) and rejects
weak secrets via the same B8 ``evaluate_secret`` policy enforced
elsewhere.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from collections.abc import Sequence

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import Operator, OperatorRole, OperatorTenantGrant, Tenant
from app.services.operator_auth import (
    OperatorAuthError,
    evaluate_operator_password,
    operator_password_hash,
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Once cockpit operator.")
    parser.add_argument("--email", required=True, help="Operator email address.")
    parser.add_argument(
        "--role",
        choices=[r.value for r in OperatorRole],
        default=OperatorRole.SUPPORT.value,
    )
    parser.add_argument(
        "--grant-all",
        action="store_true",
        help="Grant this operator write access to all existing tenants.",
    )
    parser.add_argument(
        "--mfa-required",
        action="store_true",
        help="Mark this operator as requiring MFA at login.",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Set the password non-interactively (use only in CI).",
    )
    return parser.parse_args(argv)


async def _create(
    *,
    email: str,
    password: str,
    role: str,
    mfa_required: bool,
    grant_all: bool,
) -> str:
    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(Operator).where(Operator.email == email.strip().lower())
        )
        if existing.scalar_one_or_none() is not None:
            raise SystemExit(f"Operator {email!r} already exists.")

        evaluate_operator_password(password)
        operator = Operator(
            email=email.strip().lower(),
            hashed_password=operator_password_hash(password),
            role=role,
            mfa_required=mfa_required,
        )
        session.add(operator)
        await session.flush()

        if grant_all and role != OperatorRole.FOUNDER.value:
            tenants = (await session.execute(select(Tenant))).scalars().all()
            for tenant in tenants:
                session.add(
                    OperatorTenantGrant(
                        operator_id=operator.id,
                        tenant_id=tenant.id,
                        permission="write",
                    )
                )
        await session.commit()
        return operator.id


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    password = args.password or getpass.getpass("Operator password: ")
    if not args.password:
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 2

    try:
        operator_id = asyncio.run(
            _create(
                email=args.email,
                password=password,
                role=args.role,
                mfa_required=args.mfa_required,
                grant_all=args.grant_all,
            )
        )
    except OperatorAuthError as exc:
        print(f"error: {exc.code}: {exc.message}", file=sys.stderr)
        return 3

    print(f"Created operator {args.email} (id={operator_id}, role={args.role}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
