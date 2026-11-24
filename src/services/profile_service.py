from pathlib import Path
from uuid import uuid4

from src.database.db import get_session
from src.database.models import PlayerProfile
from src.database.user_session import UserSession


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def get_or_create_player_profile(session=None, *, for_update: bool = False) -> PlayerProfile:
    """Return the active profile, creating it when needed."""
    owns_session = session is None
    session = session or get_session()
    try:
        query = session.query(PlayerProfile).order_by(PlayerProfile.id)
        profile = (query.with_for_update() if for_update else query).first()
        if profile is None:
            profile = PlayerProfile(character_name="Adventurer")
            session.add(profile)
            session.commit()
            session.refresh(profile)
        return profile
    finally:
        if owns_session:
            session.close()


def save_avatar(
    filename: str,
    content: bytes,
    upload_dir: Path = DEFAULT_UPLOAD_DIR,
    session=None,
) -> str:
    """Persist a single profile avatar and return the stored relative path."""
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_AVATAR_EXTENSIONS:
        raise ValueError("Avatar must be a PNG, JPG, or JPEG image.")
    if not content:
        raise ValueError("Avatar file cannot be empty.")

    owns_session = session is None
    session = session or get_session()
    try:
        profile = get_or_create_player_profile(session=session, for_update=True)
        previous_path = profile.avatar_path
        directory = _avatar_directory(upload_dir, session)
        directory.mkdir(parents=True, exist_ok=True)
        avatar_path = directory / f"{uuid4().hex}{extension}"
        stored_path = str(avatar_path)
        if avatar_path.is_relative_to(PROJECT_ROOT):
            stored_path = avatar_path.relative_to(PROJECT_ROOT).as_posix()
        try:
            avatar_path.write_bytes(content)
            profile.avatar_path = stored_path
            session.commit()
        except Exception:
            session.rollback()
            avatar_path.unlink(missing_ok=True)
            raise
        _remove_managed_avatar(previous_path, directory)
        return stored_path
    finally:
        if owns_session:
            session.close()


def remove_avatar(upload_dir: Path = DEFAULT_UPLOAD_DIR, session=None) -> None:
    """Remove the stored avatar file and clear the profile avatar path."""
    owns_session = session is None
    session = session or get_session()
    try:
        profile = get_or_create_player_profile(session=session, for_update=True)
        previous_path = profile.avatar_path
        profile.avatar_path = None
        session.commit()
        _remove_managed_avatar(previous_path, _avatar_directory(upload_dir, session))
    finally:
        if owns_session:
            session.close()


def resolve_avatar_path(avatar_path: str | None) -> Path | None:
    """Return an existing absolute avatar path for display."""
    if not avatar_path:
        return None

    path = Path(avatar_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path if path.exists() else None


def _avatar_directory(upload_dir: Path, session) -> Path:
    if isinstance(session, UserSession):
        return (upload_dir / "users" / str(session.user_id)).resolve()
    return upload_dir.resolve()


def _remove_managed_avatar(stored_path: str | None, directory: Path) -> None:
    avatar = resolve_avatar_path(stored_path)
    if avatar is not None and avatar.resolve().parent == directory:
        avatar.unlink(missing_ok=True)
