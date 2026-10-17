from fastapi import APIRouter, Depends

from api.deps import get_current_user
from api.routers import auth, chat, files, payments

api_router = APIRouter()


@api_router.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


api_router.include_router(auth.auth_router)
api_router.include_router(chat.chat_router, dependencies=[Depends(get_current_user)])
api_router.include_router(files.files_router, dependencies=[Depends(get_current_user)])
api_router.include_router(payments.payments_router, dependencies=[Depends(get_current_user)])
