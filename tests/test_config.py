from backend.app.core.config import Settings


def test_default_model_settings() -> None:
    settings = Settings(_env_file=None)

    assert settings.embedding_model == "BAAI/bge-m3"
    assert settings.embedding_dim == 1024
    assert settings.reranker_model == "BAAI/bge-reranker-v2-m3"
    assert settings.llm_model == "gemma-4-12b-it-qat-q4_0"
    assert settings.milvus_collection == "feishu_chunks_v2"
    assert settings.milvus_legacy_collection == "feishu_chunks_v1"


def test_service_urls_are_normalized() -> None:
    settings = Settings(EMBEDDING_BASE_URL="http://127.0.0.1:8010/", _env_file=None)

    assert settings.embedding_base_url == "http://127.0.0.1:8010"


def test_feishu_accounts_json_is_parsed_without_exposing_secret() -> None:
    settings = Settings(
        _env_file=None,
        FEISHU_ACCOUNTS_JSON=(
            '[{"account_id":"default","tenant_name":"当前企业","app_id":"cli_1",'
            '"app_secret":"secret_1","enabled":true},'
            '{"account_id":"tenant_2","tenant_name":"新企业","app_id":"",'
            '"app_secret":"","enabled":false}]'
        )
    )

    accounts = settings.feishu_accounts
    assert [account.account_id for account in accounts] == ["default", "tenant_2"]
    assert settings.feishu_credentials_configured is True
    assert settings.public_feishu_accounts[0] == {
        "account_id": "default",
        "tenant_name": "当前企业",
        "enabled": True,
        "configured": True,
    }
    assert "secret_1" not in str(settings.public_feishu_accounts)


def test_legacy_single_feishu_config_builds_default_account() -> None:
    settings = Settings(
        FEISHU_APP_ID="cli_1",
        FEISHU_APP_SECRET="secret_1",
        FEISHU_ACCOUNTS_JSON="",
        _env_file=None,
    )

    assert len(settings.feishu_accounts) == 1
    assert settings.feishu_accounts[0].account_id == "default"
    assert settings.feishu_accounts[0].tenant_name == "当前企业"
    assert settings.feishu_credentials_configured is True
