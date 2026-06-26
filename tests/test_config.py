from backend.app.core.config import Settings


def test_default_model_settings() -> None:
    settings = Settings()

    assert settings.embedding_model == "BAAI/bge-m3"
    assert settings.embedding_dim == 1024
    assert settings.reranker_model == "BAAI/bge-reranker-v2-m3"
    assert settings.llm_model == "Qwen3.6-27B-GGUF:Q4_K_M"
    assert settings.milvus_collection == "feishu_chunks_v1"


def test_service_urls_are_normalized() -> None:
    settings = Settings(EMBEDDING_BASE_URL="http://127.0.0.1:8002/")

    assert settings.embedding_base_url == "http://127.0.0.1:8002"
