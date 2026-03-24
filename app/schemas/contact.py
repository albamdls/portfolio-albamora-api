from pydantic import BaseModel, Field


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    message: str = Field(min_length=1, max_length=5000)


class ContactResponse(BaseModel):
    success: bool
    message: str
