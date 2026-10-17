from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.deps import ClientsDep, CurrentUserDep
from contracts.chat import ChatRequest, ChatResponse, ChatStreamEvent
from contracts.guardrails import GuardrailCheckRequest

chat_router = APIRouter(tags=["chat"])


@chat_router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: CurrentUserDep, clients: ClientsDep) -> ChatResponse:
    await clients.guardrails.require_allowed(GuardrailCheckRequest(context=request.message))
    prepared = await clients.orchestrator.prepare(user, request)
    return await clients.orchestrator.chat(user, prepared, request.message)


@chat_router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest, user: CurrentUserDep, clients: ClientsDep
) -> StreamingResponse:
    await clients.guardrails.require_allowed(GuardrailCheckRequest(context=request.message))
    prepared = await clients.orchestrator.prepare(user, request)
    event_stream = _sse_frames(clients.orchestrator.stream_chat(user, prepared, request.message))
    return StreamingResponse(event_stream, media_type="text/event-stream")


async def _sse_frames(events: AsyncIterator[ChatStreamEvent]) -> AsyncIterator[str]:
    async for event in events:
        yield f"event: message\ndata: {event.model_dump_json()}\n\n"
