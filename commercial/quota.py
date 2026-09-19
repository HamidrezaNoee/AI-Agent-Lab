"""Atomic test-only SQL request reservations. No direct table writes or client tenant IDs.

Stored procedures enforce verified tenant session, DB membership, subscription,
request limits, and serialization across concurrent requests. Failed model calls
still consume one monthly request slot (provider costs may still have incurred).
"""
from dataclasses import dataclass
from uuid import UUID

from .security import Principal


class QuotaExceeded(Exception):
    pass


class ChatAccessDenied(Exception):
    pass


class QuotaUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Reservation:
    request_id: UUID
    used_this_month: int
    monthly_limit: int


def reserve_request(con, principal: Principal, request_id: UUID, model_name: str) -> Reservation:
    try:
        cur = con.cursor()
        cur.execute(
            """
            EXEC AgentProduct.ReserveChatRequest
             @TenantID=?, @SubjectID=?, @RequestID=?, @ModelName=?
            """,
            str(principal.tenant_id), principal.subject,
            str(request_id), model_name,
        )
        row = cur.fetchone()
        if row is None or str(row[0]).lower() != str(request_id).lower():
            raise QuotaUnavailable("Reservation returned an unexpected request ID")
        return Reservation(
            request_id=request_id,
            used_this_month=int(row[1]),
            monthly_limit=int(row[2]),
        )
    except Exception as exc:
        if isinstance(exc, QuotaUnavailable):
            raise
        # Use error NUMBER from the SQL Server driver, not the provider message.
        message = " ".join(str(arg) for arg in getattr(exc, "args", ()))
        if "56806" in message:
            raise QuotaExceeded("Monthly request limit reached") from exc
        if "56804" in message:
            raise ChatAccessDenied("Membership or subscription inactive") from exc
        raise QuotaUnavailable("Could not reserve a chat request") from exc


def finalize_request(con, principal: Principal, request_id: UUID,
                     completed: bool, input_tokens: int | None = None,
                     output_tokens: int | None = None) -> None:
    if any(value is not None and (not isinstance(value, int) or value < 0)
           for value in (input_tokens, output_tokens)):
        raise ValueError("Invalid usage counts")
    try:
        con.cursor().execute(
            """
            EXEC AgentProduct.FinalizeChatRequest
             @TenantID=?, @RequestID=?, @State=?,
             @InputTokens=?, @OutputTokens=?
            """,
            str(principal.tenant_id), str(request_id),
            "Completed" if completed else "Failed",
            input_tokens, output_tokens,
        )
    except Exception as exc:
        raise QuotaUnavailable("Could not finalize a chat request") from exc
