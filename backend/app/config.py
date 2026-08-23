from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    environment: str = Field(default="development", alias="ENVIRONMENT")
    port: int = Field(default=8000, alias="PORT")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./havenkeep.db", 
        alias="DATABASE_URL"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    
    # Provider API Keys & Custom Base URLs
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_base_url: Optional[str] = Field(default=None, alias="ANTHROPIC_BASE_URL")
    
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(default=None, alias="OPENAI_BASE_URL")
    
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    google_base_url: Optional[str] = Field(default=None, alias="GOOGLE_BASE_URL")
    
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_base_url: Optional[str] = Field(default=None, alias="GROQ_BASE_URL")
    
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")

    # Budget Enforcement Limits (USD)
    session_soft_budget_usd: float = Field(default=0.50, alias="DEFAULT_SESSION_SOFT_BUDGET")
    session_hard_budget_usd: float = Field(default=2.00, alias="DEFAULT_SESSION_HARD_BUDGET")
    task_hard_budget_usd: float = Field(default=1.00, alias="DEFAULT_TASK_HARD_BUDGET")
    
    # Provider & Optional Model overrides per role
    supervisor_provider: str = Field(default="ollama", alias="SUPERVISOR_PROVIDER")
    supervisor_model: Optional[str] = Field(default=None, alias="SUPERVISOR_MODEL")
    
    planner_provider: str = Field(default="anthropic", alias="PLANNER_PROVIDER")
    planner_model: Optional[str] = Field(default=None, alias="PLANNER_MODEL")
    
    worker_provider: str = Field(default="openai", alias="WORKER_PROVIDER")
    worker_model: Optional[str] = Field(default=None, alias="WORKER_MODEL")
    
    critic_provider: str = Field(default="ollama", alias="CRITIC_PROVIDER")
    critic_model: Optional[str] = Field(default=None, alias="CRITIC_MODEL")

    executor_provider: str = Field(default="openai", alias="EXECUTOR_PROVIDER")
    executor_model: Optional[str] = Field(default=None, alias="EXECUTOR_MODEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
