from __future__ import annotations

import os
from functools import lru_cache
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    data_json_path: str = Field(default="/app/data/videos.json", alias="DATA_JSON_PATH")

    llm_enabled: bool = Field(default=True, alias="LLM_ENABLED")
    gigachat_auth_key: str | None = Field(default=None, alias="GIGACHAT_AUTH_KEY")
    gigachat_scope: str = Field(default="GIGACHAT_API_PERS", alias="GIGACHAT_SCOPE")
    gigachat_model: str = Field(default="GigaChat-2", alias="GIGACHAT_MODEL")
    gigachat_oauth_url: str = Field(
        default="https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        alias="GIGACHAT_OAUTH_URL",
    )
    gigachat_api_base_url: str = Field(
        default="https://gigachat.devices.sberbank.ru/api/v1",
        alias="GIGACHAT_API_BASE_URL",
    )
    gigachat_verify_ssl: bool = Field(default=True, alias="GIGACHAT_VERIFY_SSL")


@lru_cache
def get_settings() -> Settings:
    return Settings.model_validate(os.environ)
