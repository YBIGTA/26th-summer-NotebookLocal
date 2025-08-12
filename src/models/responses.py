from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Usage(BaseModel):
    prompt_tokens: int = Field(..., description="Number of tokens in the prompt")
    completion_tokens: int = Field(..., description="Number of tokens in the completion")
    total_tokens: int = Field(..., description="Total number of tokens")


class Message(BaseModel):
    role: str = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Message content")


class Choice(BaseModel):
    index: int = Field(..., description="Index of the choice")
    message: Message = Field(..., description="Message content")
    finish_reason: Optional[str] = Field(None, description="Reason for finishing")


class ChatResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the response")
    object: str = Field("chat.completion", description="Object type")
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="Model used for completion")
    choices: List[Choice] = Field(..., description="List of completion choices")
    usage: Usage = Field(..., description="Token usage information")
    
    class Config:
        extra = "allow"


class StreamChoice(BaseModel):
    index: int = Field(..., description="Index of the choice")
    delta: Dict[str, Any] = Field(..., description="Delta content")
    finish_reason: Optional[str] = Field(None, description="Reason for finishing")


class ChatStreamResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the response")
    object: str = Field("chat.completion.chunk", description="Object type")
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="Model used for completion")
    choices: List[StreamChoice] = Field(..., description="List of streaming choices")
    
    class Config:
        extra = "allow"