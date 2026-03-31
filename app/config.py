from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_api_key: str = ""
    base_url: str = "http://localhost:8000"
    secret_key: str = "change-me"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
