"""private student cases and owner-scoped document/research records
Revision ID: d4ec2f9b7860
Revises: f18a3c42e917
"""
from alembic import op
import sqlalchemy as sa
revision = "d4ec2f9b7860"
down_revision = "f18a3c42e917"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("study_cases",
      sa.Column("id", sa.String(), primary_key=True),
      sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
      sa.Column("workflow", sa.String(24), nullable=False),
      sa.Column("nationality", sa.String(80), nullable=False),
      sa.Column("residence_country", sa.String(80), nullable=False),
      sa.Column("destination_country", sa.String(80), nullable=False),
      sa.Column("degree_level", sa.String(80), nullable=False),
      sa.Column("study_field", sa.String(120), nullable=False),
      sa.Column("intake", sa.String(80), nullable=False),
      sa.Column("notes", sa.Text(), nullable=False),
      sa.Column("stage", sa.String(32), nullable=False),
      sa.Column("checklist", sa.JSON(), nullable=False),
      sa.Column("created_at", sa.DateTime(), nullable=False),
      sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_study_cases_owner_updated","study_cases",["user_id","updated_at"])
    op.create_table("study_case_documents",
      sa.Column("case_id",sa.String(),sa.ForeignKey("study_cases.id",ondelete="CASCADE"),primary_key=True),
      sa.Column("document_id",sa.String(),sa.ForeignKey("documents.id",ondelete="CASCADE"),primary_key=True),
      sa.Column("checklist_key",sa.String(50),nullable=False))
    op.create_table("study_research_reports",
      sa.Column("id",sa.String(),primary_key=True),
      sa.Column("case_id",sa.String(),sa.ForeignKey("study_cases.id",ondelete="CASCADE"),nullable=False),
      sa.Column("topic",sa.String(32),nullable=False),
      sa.Column("question",sa.Text(),nullable=False),
      sa.Column("answer",sa.Text(),nullable=False),
      sa.Column("sources",sa.JSON(),nullable=False),
      sa.Column("searched_at",sa.DateTime(),nullable=False))
    op.create_index("ix_study_research_reports_case_id","study_research_reports",["case_id"])

def downgrade() -> None:
    op.drop_index("ix_study_research_reports_case_id",table_name="study_research_reports")
    op.drop_table("study_research_reports")
    op.drop_table("study_case_documents")
    op.drop_index("ix_study_cases_owner_updated",table_name="study_cases")
    op.drop_table("study_cases")
