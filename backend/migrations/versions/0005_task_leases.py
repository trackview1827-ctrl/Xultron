"""add task worker leases"""
from alembic import op
import sqlalchemy as sa

revision = "0005_task_leases"
down_revision = "0004_tasks"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("tasks", sa.Column("worker_id", sa.String(length=120), nullable=True))
    op.add_column("tasks", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
    op.create_index("ix_tasks_worker_id", "tasks", ["worker_id"])
    op.create_index("ix_tasks_lease_expires_at", "tasks", ["lease_expires_at"])

def downgrade():
    op.drop_index("ix_tasks_lease_expires_at", table_name="tasks")
    op.drop_index("ix_tasks_worker_id", table_name="tasks")
    op.drop_column("tasks", "lease_expires_at")
    op.drop_column("tasks", "worker_id")
