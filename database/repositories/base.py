"""Generic SQLAlchemy repository helpers.

TODO: Keep CRUD behavior generic so domain-specific logic stays in the service layer.
"""

from __future__ import annotations

from typing import Any, ClassVar, Generic, TypeVar

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session


ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """Provide minimal, reusable CRUD operations for SQLAlchemy models."""

    model: ClassVar[type[ModelT]]

    def __init__(self, session: Session) -> None:
        """Store the active SQLAlchemy session used by this repository."""

        self.session = session

    def create(self, **data: Any) -> ModelT:
        """Create a new model instance and flush it to the database session."""

        instance = self.model(**data)
        self.session.add(instance)
        self.session.flush()
        self.session.refresh(instance)
        return instance

    def get(self, object_id: Any) -> ModelT | None:
        """Return one model instance by primary key if it exists."""

        return self.session.get(self.model, object_id)

    def get_one_by(self, **filters: Any) -> ModelT | None:
        """Return the first model instance matching the provided filters."""

        statement = select(self.model).filter_by(**filters)
        return self.session.scalars(statement).first()

    def list(self, offset: int = 0, limit: int = 100) -> list[ModelT]:
        """Return a paginated list of model instances."""

        statement: Select[tuple[ModelT]] = select(self.model).offset(offset).limit(limit)
        return list(self.session.scalars(statement))

    def update(self, instance: ModelT, **changes: Any) -> ModelT:
        """Apply attribute changes to an existing model instance and flush them."""

        for key, value in changes.items():
            setattr(instance, key, value)
        self.session.flush()
        self.session.refresh(instance)
        return instance

    def delete(self, instance: ModelT) -> None:
        """Delete a model instance from the current session."""

        self.session.delete(instance)
        self.session.flush()

    def delete_where(self, **filters: Any) -> int:
        """Delete rows matching the provided filters and return the affected count."""

        conditions = [getattr(self.model, key) == value for key, value in filters.items()]
        statement = delete(self.model).where(*conditions)
        result = self.session.execute(statement)
        self.session.flush()
        return int(result.rowcount or 0)

    def count(self) -> int:
        """Return the total number of rows for the repository model."""

        statement = select(func.count()).select_from(self.model)
        return int(self.session.scalar(statement) or 0)

