# add conversation projects
# Revision ID: d4b7c9a1e2f3
# Revises: 9f4c2b1d7e6a
# Create Date: 2026-08-25

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4b7c9a1e2f3"
down_revision: Union[
    str,
    Sequence[str],
    None,
] = "9f4c2b1d7e6a"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "mode IN ('normal', 'knowledge')",
            name="ck_projects_mode",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_projects_user_mode_updated_at",
        "projects",
        ["user_id", "mode", "updated_at"],
        unique=False,
    )

    op.add_column(
        "conversations",
        sa.Column(
            "project_id",
            sa.String(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_conversations_project_id_projects",
        "conversations",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_conversations_project_id",
        "conversations",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversations_project_id",
        table_name="conversations",
    )
    op.drop_constraint(
        "fk_conversations_project_id_projects",
        "conversations",
        type_="foreignkey",
    )
    op.drop_column(
        "conversations",
        "project_id",
    )
    op.drop_index(
        "ix_projects_user_mode_updated_at",
        table_name="projects",
    )
    op.drop_table("projects")
