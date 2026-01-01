"""PostgreSQL database configuration."""

from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def connection_string(self) -> PostgresDsn:
        """Get synchronous connection string for psycopg."""
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.user,
            password=quote_plus(self.password),
            host=self.host,
            port=self.port,
            path=self.database,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def connection_string_async(self) -> PostgresDsn:
        """Get asynchronous connection string for asyncpg."""
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.user,
            password=quote_plus(self.password),
            host=self.host,
            port=self.port,
            path=self.database,
        )


def create_skill_engine(  # noqa: PLR0913
    config: PostgresConfig | None = None,
    pool_pre_ping: bool = True,
    pool_recycle: int = 3600,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_timeout: int = 30,
    connect_args: dict | None = None,
    echo: bool = False,
) -> AsyncEngine:
    """Create a properly configured async engine for skill database operations.

    This helper creates an AsyncEngine with connection pool settings optimized for
    reliability in long-running skill processes. It includes connection health
    checking and automatic connection recycling to handle PostgreSQL timeouts
    and network interruptions.

    Args:
        config: PostgresConfig instance. If None, creates one from environment variables.
        pool_pre_ping: Test connections before use to detect stale connections.
            Prevents "connection is closed" errors. Default: True.
        pool_recycle: Recycle connections after this many seconds. Prevents
            issues with database-side connection timeouts. Default: 3600 (1 hour).
        pool_size: Number of connections to keep in the pool. Default: 5.
        max_overflow: Maximum overflow connections beyond pool_size. Default: 10.
        pool_timeout: Seconds to wait for a connection from pool. Default: 30.
        connect_args: Additional arguments passed to the asyncpg driver.
            Default: {"command_timeout": 60} for operation timeout.
        echo: Enable SQL statement logging. Default: False.

    Returns:
        Configured AsyncEngine instance ready for use with SQLModel/SQLAlchemy.

    Example:
        >>> from private_assistant_commons.database import PostgresConfig, create_skill_engine
        >>>
        >>> # Use defaults (recommended for most skills)
        >>> engine = create_skill_engine()
        >>>
        >>> # Or with custom configuration
        >>> config = PostgresConfig(host="db.example.com")
        >>> engine = create_skill_engine(
        ...     config=config,
        ...     pool_size=10,
        ...     echo=True  # for debugging
        ... )
    """
    if config is None:
        config = PostgresConfig()

    if connect_args is None:
        connect_args = {"command_timeout": 60}

    return create_async_engine(
        str(config.connection_string_async),
        pool_pre_ping=pool_pre_ping,
        pool_recycle=pool_recycle,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        connect_args=connect_args,
        echo=echo,
    )
