from pathlib import Path

from src.database.db import get_session
from src.database.models import PlayerProfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def get_or_create_player_profile(session=None) -> PlayerProfile:
    """Return the single local player profile, creating it when needed."""
    owns_session = session is None
    session = session or get_session()
    try:
        profile = session.query(PlayerProfile).order_by(PlayerProfile.id).first()
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

    upload_dir.mkdir(parents=True, exist_ok=True)
    _remove_existing_avatar_files(upload_dir)

    avatar_path = upload_dir / f"avatar{extension}"
    avatar_path.write_bytes(content)
    try:
        stored_path = avatar_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        stored_path = str(avatar_path)

    owns_session = session is None
    session = session or get_session()
    try:
        profile = get_or_create_player_profile(session=session)
        profile.avatar_path = stored_path
        session.commit()
        return stored_path
    finally:
        if owns_session:
            session.close()


def remove_avatar(upload_dir: Path = DEFAULT_UPLOAD_DIR, session=None) -> None:
    """Remove the stored avatar file and clear the profile avatar path."""
    upload_dir.mkdir(parents=True, exist_ok=True)
    _remove_existing_avatar_files(upload_dir)

    owns_session = session is None
    session = session or get_session()
    try:
        profile = get_or_create_player_profile(session=session)
        profile.avatar_path = None
        session.commit()
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


def _remove_existing_avatar_files(upload_dir: Path) -> None:
    for extension in ALLOWED_AVATAR_EXTENSIONS:
        path = upload_dir / f"avatar{extension}"
        if path.exists():
            path.unlink()
