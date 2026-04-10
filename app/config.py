from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "data/refrigerator.db"
    chroma_persist_dir: str = "data/chroma"
    chroma_collection_name: str = "items"
    ask_base_url: str = "http://localhost:1234/v1"
    ask_model: str = "gemma-4-26b-a4b-it-GGUF"
    ask_max_tokens: int = 1024

    @property
    def database_path(self) -> Path:
        path = Path(self.database_url)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
