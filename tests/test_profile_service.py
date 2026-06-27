from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, PlayerProfile
from src.services.profile_service import get_or_create_player_profile, remove_avatar, resolve_avatar_path, save_avatar


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


def test_get_or_create_player_profile_creates_default_profile(session):
    profile = get_or_create_player_profile(session=session)

    assert profile.id is not None
    assert profile.character_name == "Adventurer"
    assert profile.avatar_path is None
    assert session.query(PlayerProfile).count() == 1


def test_save_avatar_persists_path_and_replaces_existing_file(session, tmp_path):
    upload_dir = tmp_path / "uploads"

    first_path = save_avatar("portrait.png", b"first-image", upload_dir=upload_dir, session=session)
    second_path = save_avatar("portrait.jpg", b"second-image", upload_dir=upload_dir, session=session)
    profile = session.query(PlayerProfile).one()

    assert Path(first_path).exists() is False
    assert Path(second_path).read_bytes() == b"second-image"
    assert profile.avatar_path == second_path


def test_save_avatar_rejects_unsupported_file_type(session, tmp_path):
    with pytest.raises(ValueError):
        save_avatar("portrait.gif", b"image", upload_dir=tmp_path, session=session)


def test_remove_avatar_clears_path_and_file(session, tmp_path):
    upload_dir = tmp_path / "uploads"
    saved_path = save_avatar("portrait.jpeg", b"image", upload_dir=upload_dir, session=session)

    remove_avatar(upload_dir=upload_dir, session=session)
    profile = session.query(PlayerProfile).one()

    assert Path(saved_path).exists() is False
    assert profile.avatar_path is None


def test_resolve_avatar_path_returns_existing_absolute_path(tmp_path):
    avatar_path = tmp_path / "avatar.png"
    avatar_path.write_bytes(b"image")

    assert resolve_avatar_path(str(avatar_path)) == avatar_path
    assert resolve_avatar_path(str(tmp_path / "missing.png")) is None
