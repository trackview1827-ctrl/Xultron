"""add durable agent tasks"""
from alembic import op
import sqlalchemy as sa

revision = "0004_tasks"
down_revision = "0003_codex_oauth"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("tasks",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("user_id", sa.String(length=40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("result", sa.JSON(), nullable=True), sa.Column("error", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

def downgrade():
    op.drop_table("tasks")
