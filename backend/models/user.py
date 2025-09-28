from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class UserModel(BaseModel):
    """User model for basic user information"""
    id: str = Field(..., description="User ID")
    email: Optional[str] = Field(None, description="User email")
    name: Optional[str] = Field(None, description="User display name")
    created_at: Optional[datetime] = Field(None, description="User creation timestamp")
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="User preferences")

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat()}