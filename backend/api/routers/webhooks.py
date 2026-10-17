from fastapi import APIRouter, Request, status

from api.deps import ClientsDep
from contracts.mail_gateway import WebhookAccepted

webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@webhooks_router.post("/mail", response_model=WebhookAccepted, status_code=status.HTTP_202_ACCEPTED)
async def mail_webhook(request: Request, clients: ClientsDep) -> WebhookAccepted:
    await clients.inbox.ingest_webhook(await request.body(), request.headers)
    return WebhookAccepted()
