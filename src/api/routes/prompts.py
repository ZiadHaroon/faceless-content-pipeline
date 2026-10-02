from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_prompt_repo
from src.domain.models import Prompt
from src.repositories.prompt import SQLitePromptRepository

router = APIRouter(prefix="/prompts", tags=["prompts"])


class CreatePromptRequest(BaseModel):
    name: str
    template: str


@router.get("", response_model=list[Prompt])
def list_prompts(repo: SQLitePromptRepository = Depends(get_prompt_repo)):
    return repo.get_all()


@router.post("", response_model=Prompt, status_code=201)
def create_prompt(
    body: CreatePromptRequest,
    repo: SQLitePromptRepository = Depends(get_prompt_repo),
):
    return repo.create(name=body.name, template=body.template)


@router.delete("/{prompt_id}", status_code=204)
def delete_prompt(
    prompt_id: int,
    repo: SQLitePromptRepository = Depends(get_prompt_repo),
):
    if repo.get_by_id(prompt_id) is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    repo.delete(prompt_id)
