import pytest

from src.domain.models import PipelineStage, Platform, Slide
from src.infrastructure.database import Database
from src.repositories.video import SQLiteVideoRepository


@pytest.fixture
def repo():
    db = Database(":memory:")
    db.migrate()
    return SQLiteVideoRepository(db)


def test_create_returns_video_at_idea_stage(repo):
    video = repo.create("How Face ID Works")
    assert video.id is not None
    assert video.title == "How Face ID Works"
    assert video.stage == PipelineStage.idea
    assert video.slides == []
    assert video.script_approved is False


def test_get_by_id_returns_correct_video(repo):
    created = repo.create("Battery Degradation")
    fetched = repo.get_by_id(created.id)
    assert fetched.id == created.id
    assert fetched.title == "Battery Degradation"


def test_get_by_id_returns_none_for_missing(repo):
    assert repo.get_by_id(9999) is None


def test_get_all_returns_all_videos(repo):
    repo.create("Video A")
    repo.create("Video B")
    videos = repo.get_all()
    assert len(videos) == 2


def test_get_all_filtered_by_stage(repo):
    v1 = repo.create("Video A")
    v2 = repo.create("Video B")

    v1 = repo.get_by_id(v1.id)
    v1 = v1.model_copy(update={"stage": PipelineStage.script})
    repo.update(v1)

    ideas = repo.get_all(stage=PipelineStage.idea)
    scripts = repo.get_all(stage=PipelineStage.script)

    assert len(ideas) == 1
    assert ideas[0].id == v2.id
    assert len(scripts) == 1
    assert scripts[0].id == v1.id


def test_update_persists_stage_change(repo):
    video = repo.create("VPN Explainer")
    video = video.model_copy(update={"stage": PipelineStage.script, "script_approved": True})
    updated = repo.update(video)
    assert updated.stage == PipelineStage.script
    assert updated.script_approved is True


def test_update_persists_slides(repo):
    video = repo.create("Quantum Computing")
    slide = Slide(slide_number=1, narration="Quantum bits exist in superposition.", search_query="quantum computer chip")
    video = video.model_copy(update={"slides": [slide]})
    updated = repo.update(video)
    assert len(updated.slides) == 1
    assert updated.slides[0].narration == "Quantum bits exist in superposition."
    assert updated.slides[0].search_query == "quantum computer chip"


def test_update_persists_platforms(repo):
    video = repo.create("5G Myths")
    video = video.model_copy(update={"platforms": [Platform.youtube, Platform.tiktok]})
    updated = repo.update(video)
    assert Platform.youtube in updated.platforms
    assert Platform.tiktok in updated.platforms


def test_delete_removes_video(repo):
    video = repo.create("To Be Deleted")
    repo.delete(video.id)
    assert repo.get_by_id(video.id) is None


def test_delete_nonexistent_does_not_raise(repo):
    repo.delete(9999)  # should not raise
