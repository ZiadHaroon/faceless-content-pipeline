import pytest

from src.domain.models import TopicTag
from src.infrastructure.database import Database
from src.repositories.topic import SQLiteTopicRepository


@pytest.fixture
def repo():
    db = Database(":memory:")
    db.migrate()
    return SQLiteTopicRepository(db)


def test_create_returns_topic(repo):
    topic = repo.create("How does Face ID work", TopicTag.device)
    assert topic.id is not None
    assert topic.topic == "How does Face ID work"
    assert topic.tag == TopicTag.device
    assert topic.used is False


def test_create_defaults_to_other_tag(repo):
    topic = repo.create("Some topic")
    assert topic.tag == TopicTag.other


def test_get_by_id_returns_correct_topic(repo):
    created = repo.create("VPN Explainer", TopicTag.security)
    fetched = repo.get_by_id(created.id)
    assert fetched.id == created.id
    assert fetched.tag == TopicTag.security


def test_get_by_id_returns_none_for_missing(repo):
    assert repo.get_by_id(9999) is None


def test_get_all_returns_all_topics(repo):
    repo.create("Topic A", TopicTag.AI)
    repo.create("Topic B", TopicTag.device)
    assert len(repo.get_all()) == 2


def test_get_all_unused_only(repo):
    t1 = repo.create("Used topic", TopicTag.AI)
    repo.create("Unused topic", TopicTag.device)
    repo.mark_used(t1.id)

    unused = repo.get_all(unused_only=True)
    assert len(unused) == 1
    assert unused[0].topic == "Unused topic"


def test_mark_used_sets_flag(repo):
    topic = repo.create("Encryption Explained", TopicTag.security)
    repo.mark_used(topic.id)
    fetched = repo.get_by_id(topic.id)
    assert fetched.used is True


def test_delete_removes_topic(repo):
    topic = repo.create("To Be Deleted")
    repo.delete(topic.id)
    assert repo.get_by_id(topic.id) is None
