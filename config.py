from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
  database_url: str = Field(alias="DATABASE_URL")
  postgres_user: str = Field(alias="POSTGRES_USER")
  postgres_password: str = Field(alias="POSTGRES_PASSWORD")
  postgres_db: str = Field(alias="POSTGRES_DB")
  postgres_host: str = Field(default="localhost",alias="POSTGRES_HOST")
  postgres_port: int = Field(default=5432,alias="POSTGRES_PORT")
  class Config:
    env_file = ".env"
    env_file_encoding = "utf-8"

@lru_cache()
def get_settings():
  return Settings()