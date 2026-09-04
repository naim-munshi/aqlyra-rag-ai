"""add verified identities

Revision ID: e7a9c3d5f1b2
Revises: d4b7c9a1e2f3
Create Date: 2026-09-04

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7a9c3d5f1b2"
down_revision: Union[
    str,
    Sequence[str],
    None,
] = "d4b7c9a1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified_at",
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "google_subject",
            sa.String(length=255),
            nullable=True,
        ),
    )

    # Existing accounts were already able to authenticate before
    # verification existed. Preserve their access during rollout.
    op.execute(
        sa.text(
            "UPDATE users "
            "SET email_verified_at = "
            "COALESCE(updated_at, created_at, NOW())"
        )
    )

    op.create_index(
        "ix_users_google_subject",
        "users",
        ["google_subject"],
        unique=True,
    )

    op.create_table(
        "email_verification_codes",
        sa.Column(
            "id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "code_digest",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "failed_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "consumed_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_verification_codes_user_created_at",
        "email_verification_codes",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_verification_codes_user_created_at",
        table_name="email_verification_codes",
    )
    op.drop_table(
        "email_verification_codes"
    )
    op.drop_index(
        "ix_users_google_subject",
        table_name="users",
    )
    op.drop_column(
        "users",
        "google_subject",
    )
    op.drop_column(
        "users",
        "email_verified_at",
    )
