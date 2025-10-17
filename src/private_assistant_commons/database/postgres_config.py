"""PostgreSQL database configuration."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresConfig(BaseSettings):
    """PostgreSQL database connection configuration.

    Automatically loads configuration from environment variables with POSTGRES_ prefix:
    - POSTGRES_USER (default: postgres)
    - POSTGRES_PASSWORD (default: postgres)
    - POSTGRES_HOST (default: localhost)
    - POSTGRES_PORT (default: 5432)
    - POSTGRES_DB (default: postgres)

    Example:
        >>> # Automatically loads from environment variables
        >>> config = PostgresConfig()
        >>>
        >>> # Or override with explicit values
        >>> config = PostgresConfig(user="myuser", host="db.example.com")
    """

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    user: str = Field(default="postgres", description="Database user")
    password: str = Field(default="postgres", description="Database password")
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(
        default="postgres",
        description="Database name",
        validation_alias=AliasChoices("database", "POSTGRES_DB"),
    )

    @property
    def connection_string(self) -> str:
        """Get synchronous connection string for psycopg."""
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def connection_string_async(self) -> str:
        """Get asynchronous connection string for asyncpg."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
