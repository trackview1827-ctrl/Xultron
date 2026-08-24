"""hardening schema additions

Revision ID: 0002_hardening
Revises: 0001_initial
Create Date: 2026-08-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_hardening"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("idempotency_keys") as batch:
        batch.add_column(sa.Column("request_fingerprint", sa.String(length=64), nullable=True))
    op.create_table(
        "device_commands",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("user_id", sa.String(length=40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(length=40), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("executed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_device_commands_user_id", "device_commands", ["user_id"])
    op.create_index("ix_device_commands_device_id", "device_commands", ["device_id"])
    op.create_table(
        "device_events",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("user_id", sa.String(length=40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(length=40), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_device_events_user_id", "device_events", ["user_id"])
    op.create_index("ix_device_events_device_id", "device_events", ["device_id"])


def downgrade():
    op.drop_index("ix_device_events_device_id", table_name="device_events")
    op.drop_index("ix_device_events_user_id", table_name="device_events")
    op.drop_table("device_events")
    op.drop_index("ix_device_commands_device_id", table_name="device_commands")
    op.drop_index("ix_device_commands_user_id", table_name="device_commands")
    op.drop_table("device_commands")
    with op.batch_alter_table("idempotency_keys") as batch:
        batch.drop_column("request_fingerprint")
