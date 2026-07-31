from typing import Literal

from pydantic import BaseModel


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    thread_id: str
    root_dir: str
    authorized: bool = False
    model: str | None = None
    temperature: float | None = None
