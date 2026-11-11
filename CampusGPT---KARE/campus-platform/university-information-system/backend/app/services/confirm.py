"""Second confirmation for an action that cannot be undone."""
from fastapi import HTTPException
from pydantic import BaseModel


class PhraseIn(BaseModel):
    confirm: str = ""


def require_phrase(given: str, expected: str) -> None:
    phrase = (expected or "").strip()
    typed = (given or "").strip()
    if not phrase or typed.casefold() != phrase.casefold():
        raise HTTPException(
            status_code=400,
            detail=f"Second confirmation failed. Type {phrase} to continue.",
        )
