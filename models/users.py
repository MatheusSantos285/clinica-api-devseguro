from typing import Optional
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: str = Field(primary_key=True)
    email: Optional[str] = Field(default=None, unique=True, index=True)
    hashed_password: str
    role: str
    mfa_secret: Optional[str] = None
    scopes: Optional[str] = None
    is_m2m: bool = False