from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str = Field(..., description="Role of the message sender (system, user, assistant)")
    content: Union[str, List[Dict[str, Any]]] = Field(..., description="Message content")


class ChatRequest(BaseModel):
    model: Optional[str] = Field(None, description="Model to use for completion")
    messages: List[Message] = Field(..., description="List of messages in the conversation")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum number of tokens to generate")
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    frequency_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0, description="Presence penalty")
    stream: Optional[bool] = Field(False, description="Whether to stream the response")
    stop: Optional[Union[str, List[str]]] = Field(None, description="Stop sequences")
    user: Optional[str] = Field(None, description="User identifier")
    
    class Config:
        extra = "allow"