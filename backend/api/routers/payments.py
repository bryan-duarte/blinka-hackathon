from uuid import UUID

from fastapi import APIRouter, status

from api.deps import ClientsDep, CurrentUserDep
from contracts.bills import UPLOAD_SOURCE_REF_PREFIX, BillSourceType
from contracts.guardrails import GuardrailCheckRequest
from contracts.payments import PaymentRunAccepted, PaymentRunStatus, UploadRunRequest

payments_router = APIRouter(prefix="/payments", tags=["payments"])


@payments_router.post(
    "/runs", response_model=PaymentRunAccepted, status_code=status.HTTP_202_ACCEPTED
)
async def trigger_run(
    request: UploadRunRequest, user: CurrentUserDep, clients: ClientsDep
) -> PaymentRunAccepted:
    guardrail_context = f"payment run for file {request.file_id}"
    await clients.guardrails.require_allowed(GuardrailCheckRequest(context=guardrail_context))
    return await clients.payments.start_file_run(
        user, request.file_id, BillSourceType.UPLOAD, f"{UPLOAD_SOURCE_REF_PREFIX}{request.file_id}"
    )


@payments_router.get("/runs/{run_id}", response_model=PaymentRunStatus)
async def get_run(run_id: UUID, user: CurrentUserDep, clients: ClientsDep) -> PaymentRunStatus:
    return await clients.payments.get_run(run_id, user)
