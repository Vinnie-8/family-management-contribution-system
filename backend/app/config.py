from urilib.parse import quote_plus
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    db_user : str
    db_password : str
    db_host : str
    db_port : int = 5432
    db_name : str
    
    redis_url: str = "redis://localhost:6379/0"
    
    
    jwt_secret_key : str
    jwt_algorithm :str = "HS256"
    access_token_expire_minutes:int
    refresh_token_expire_days : int
    temp_password_expiry_hours : int
    temp_password_length : int
    
    
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding = "utf-8",
        case_sensitive = False,
    )
 
 
settings = Settings()
    
         