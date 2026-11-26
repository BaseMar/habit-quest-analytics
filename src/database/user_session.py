from sqlalchemy import Select, event, inspect
from sqlalchemy.orm import Session, with_loader_criteria

from src.database.models import Achievement, UserOwned


_SCOPED_OPERATIONS = "Account sessions require ORM reads and writes through mapped objects."


class UserSession(Session):
    """A session bound to one immutable application account."""

    def __init__(self, *, user_id: int, **kwargs):
        super().__init__(**kwargs)
        self._user_id = user_id

    @property
    def user_id(self) -> int:
        return self._user_id

    def _reject_legacy_bulk_write(self, *args, **kwargs):
        # These APIs bypass both ORM execution events and per-object flush validation.
        raise PermissionError(_SCOPED_OPERATIONS)

    bulk_insert_mappings = _reject_legacy_bulk_write
    bulk_update_mappings = _reject_legacy_bulk_write
    bulk_save_objects = _reject_legacy_bulk_write


@event.listens_for(UserSession, "do_orm_execute")
def scope_queries(execution):
    # A supplied from_statement() query cannot be rewritten with ownership criteria.
    if not (execution.is_orm_statement and isinstance(execution.statement, Select)):
        raise PermissionError(_SCOPED_OPERATIONS)
    if any(not issubclass(mapper.class_, (UserOwned, Achievement)) for mapper in execution.all_mappers):
        raise PermissionError("This data is unavailable in an account session.")
    user_id = execution.session.user_id
    execution.statement = execution.statement.options(
        with_loader_criteria(
            UserOwned, lambda model: model.user_id == user_id, include_aliases=True,
        )
    )


@event.listens_for(UserSession, "before_flush")
def scope_writes(session, _flush_context, _instances):
    for row in session.new:
        if not isinstance(row, UserOwned) or row.user_id not in (None, session.user_id):
            raise PermissionError("Cannot create data for a different account.")
        row.user_id = session.user_id
    for row in session.dirty.union(session.deleted):
        if (
            not isinstance(row, UserOwned)
            or row.user_id != session.user_id
            or inspect(row).attrs.user_id.history.has_changes()
        ):
            raise PermissionError("Cannot modify data belonging to a different account.")
