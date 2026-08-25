from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now_naive
from app.models.project import Project


def create_project(
    *,
    db: Session,
    user_id: str,
    name: str,
    mode: str,
) -> Project:
    project = Project(
        user_id=user_id,
        name=name,
        mode=mode,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project_for_user(
    *,
    db: Session,
    user_id: str,
    project_id: str,
) -> Project | None:
    statement = select(Project).where(
        Project.id == project_id,
        Project.user_id == user_id,
    )
    return db.scalar(statement)


def list_projects_for_user(
    *,
    db: Session,
    user_id: str,
    mode: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Project]:
    statement = select(Project).where(
        Project.user_id == user_id
    )

    if mode is not None:
        statement = statement.where(
            Project.mode == mode
        )

    statement = (
        statement
        .order_by(
            Project.updated_at.desc(),
            Project.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def update_project(
    *,
    db: Session,
    project: Project,
    name: str,
) -> Project:
    project.name = name
    project.updated_at = utc_now_naive()
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def delete_project(
    *,
    db: Session,
    project: Project,
) -> None:
    db.delete(project)
    db.commit()
