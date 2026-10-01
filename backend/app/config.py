from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    database_url: str = "postgresql+psycopg2://stallspan:stallspan@localhost:5448/stallspan"
    seed_on_empty: bool = True


settings = Settings()
