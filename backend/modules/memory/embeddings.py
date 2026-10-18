from botocore.config import Config
from langchain_aws import BedrockEmbeddings
from langgraph.store.postgres.base import PostgresIndexConfig

from core.config import MemorySettings

PRECEDENT_INDEX_FIELDS = ["content.situation", "content.lesson"]
COSINE_DISTANCE = "cosine"
EMBEDDING_TOTAL_ATTEMPTS = 3
ADAPTIVE_RETRY_MODE = "adaptive"


def build_memory_index(settings: MemorySettings) -> PostgresIndexConfig:
    embeddings = BedrockEmbeddings(
        model_id=settings.embedding_model,
        region_name=settings.aws_region,
        credentials_profile_name=settings.aws_profile,
        config=Config(
            retries={"total_max_attempts": EMBEDDING_TOTAL_ATTEMPTS, "mode": ADAPTIVE_RETRY_MODE}
        ),
    )
    return {
        "dims": settings.embedding_dims,
        "embed": embeddings,
        "fields": PRECEDENT_INDEX_FIELDS,
        "distance_type": COSINE_DISTANCE,
    }
