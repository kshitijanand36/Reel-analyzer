from pydantic import BaseModel


class ScrapeRequest(BaseModel):
    url: str


class Comment(BaseModel):
    user: str
    text: str


class ScrapeResponse(BaseModel):
    caption: str | None = None
    geotags: list[str] = []
    comments: list[Comment] = []
    owner: str | None = None
    likes: int | None = None
    date: str | None = None
    error: str | None = None
