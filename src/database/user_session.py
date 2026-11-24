from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, with_loader_criteria

from src.database.models import Achievement, UserOwned


class UserSession(Session):
    """A session bound to one immutable application account."""

    def __init__(self, *, user_id: int, **kwargs):
        super().__init__(**kwargs)
        self._user_id = user_id

    @property
    def user_id(self) -> int:
        return self._user_id


@event.listens_for(UserSession, "do_orm_execute")
def scope_queries(execution):
    # Bulk writes and Core SQL bypass the per-object ownership checks below.
    if not (execution.is_orm_statement and execution.is_select):
        raise PermissionError("Account sessions require ORM reads and writes through mapped objects.")
    if any(not issubclass(mapper.class_, (UserOwned, Achievement)) for mapper in execution.all_mappers):
        raise PermissionError("This data is unavailable in an account session.")
    user_id = execution.session.user_id
    execution.statement = execution.statement.options(
        with_loader_criteria(
            UserOwned, lambda model: model.user_id == user_id, include_aliases=True, propagate_to_loaders=False,
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
