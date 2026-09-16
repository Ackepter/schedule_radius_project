from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Расписание Центра Детских Занятий"
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/children_center"
    cors_origins: str = "http://localhost:5173,http://localhost:5174"
    seed_on_startup: bool = False

    # Границы рабочего времени центра (время 09:00-20:00 по умолчанию)
    center_open_hour: int = 9
    center_close_hour: int = 20

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()