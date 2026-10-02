import pytest

from src.infrastructure.database import Database
from src.repositories.prompt import SQLitePromptRepository


@pytest.fixture
def repo():
    db = Database(":memory:")
    db.migrate()
    return SQLitePromptRepository(db)


def test_create_returns_prompt(repo):
    prompt = repo.create("Default Template", "Write a script about [TOPIC].")
    assert prompt.id is not None
    assert prompt.name == "Default Template"
    assert prompt.template == "Write a script about [TOPIC]."


def test_get_by_id_returns_correct_prompt(repo):
    created = repo.create("Hook Template", "Start with a shocking fact about [TOPIC].")
    fetched = repo.get_by_id(created.id)
    assert fetched.id == created.id
    assert fetched.name == "Hook Template"


def test_get_by_id_returns_none_for_missing(repo):
    assert repo.get_by_id(9999) is None


def test_get_all_returns_all_prompts(repo):
    repo.create("Template A", "Content A")
    repo.create("Template B", "Content B")
    assert len(repo.get_all()) == 2


def test_delete_removes_prompt(repo):
    prompt = repo.create("To Be Deleted", "Some template.")
    repo.delete(prompt.id)
    assert repo.get_by_id(prompt.id) is None


def test_get_all_empty_returns_empty_list(repo):
    assert repo.get_all() == []
