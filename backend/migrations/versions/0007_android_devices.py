"""add Android device authentication and rotating token families"""
from alembic import op
import sqlalchemy as sa

revision = "0007_android_devices"
down_revision = "0006_whisper_port"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("devices", sa.Column("installation_id", sa.String(length=128), nullable=True))
    op.add_column(
        "devices",
        sa.Column(
            "last_seen_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column("devices", sa.Column("revoked_at", sa.DateTime(), nullable=True))
    op.create_index("ix_devices_installation_id", "devices", ["installation_id"])
    op.create_index("ix_devices_revoked_at", "devices", ["revoked_at"])
    op.create_index(
        "uq_devices_user_installation",
        "devices",
        ["user_id", "installation_id"],
        unique=True,
    )

    op.create_table(
        "mobile_auth_sessions",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=40),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id",
            sa.String(length=40),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoke_reason", sa.String(length=80), nullable=True),
    )
    op.create_index("ix_mobile_auth_sessions_user_id", "mobile_auth_sessions", ["user_id"])
    op.create_index("ix_mobile_auth_sessions_device_id", "mobile_auth_sessions", ["device_id"])
    op.create_index("ix_mobile_auth_sessions_expires_at", "mobile_auth_sessions", ["expires_at"])
    op.create_index("ix_mobile_auth_sessions_revoked_at", "mobile_auth_sessions", ["revoked_at"])

    op.create_table(
        "mobile_access_tokens",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=40),
            sa.ForeignKey("mobile_auth_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_mobile_access_tokens_session_id", "mobile_access_tokens", ["session_id"])
    op.create_index("ix_mobile_access_tokens_token_hash", "mobile_access_tokens", ["token_hash"], unique=True)
    op.create_index("ix_mobile_access_tokens_expires_at", "mobile_access_tokens", ["expires_at"])
    op.create_index("ix_mobile_access_tokens_revoked_at", "mobile_access_tokens", ["revoked_at"])

    op.create_table(
        "mobile_refresh_tokens",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=40),
            sa.ForeignKey("mobile_auth_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            sa.String(length=40),
            sa.ForeignKey("mobile_refresh_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_mobile_refresh_tokens_session_id", "mobile_refresh_tokens", ["session_id"])
    op.create_index("ix_mobile_refresh_tokens_parent_id", "mobile_refresh_tokens", ["parent_id"])
    op.create_index("ix_mobile_refresh_tokens_token_hash", "mobile_refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_mobile_refresh_tokens_expires_at", "mobile_refresh_tokens", ["expires_at"])
    op.create_index("ix_mobile_refresh_tokens_consumed_at", "mobile_refresh_tokens", ["consumed_at"])
    op.create_index("ix_mobile_refresh_tokens_revoked_at", "mobile_refresh_tokens", ["revoked_at"])

    op.create_table(
        "mobile_auth_events",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("user_id", sa.String(length=40), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_id", sa.String(length=40), sa.ForeignKey("mobile_auth_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("device_id", sa.String(length=40), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_mobile_auth_events_user_id", "mobile_auth_events", ["user_id"])
    op.create_index("ix_mobile_auth_events_session_id", "mobile_auth_events", ["session_id"])
    op.create_index("ix_mobile_auth_events_device_id", "mobile_auth_events", ["device_id"])
    op.create_index("ix_mobile_auth_events_event_type", "mobile_auth_events", ["event_type"])
    op.create_index("ix_mobile_auth_events_created_at", "mobile_auth_events", ["created_at"])


def downgrade():
    op.drop_table("mobile_auth_events")
    op.drop_table("mobile_refresh_tokens")
    op.drop_table("mobile_access_tokens")
    op.drop_table("mobile_auth_sessions")
    op.drop_index("uq_devices_user_installation", table_name="devices")
    op.drop_index("ix_devices_revoked_at", table_name="devices")
    op.drop_index("ix_devices_installation_id", table_name="devices")
    op.drop_column("devices", "revoked_at")
    op.drop_column("devices", "last_seen_at")
    op.drop_column("devices", "installation_id")
