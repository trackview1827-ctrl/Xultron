"""add encrypted Codex OAuth credentials

Revision ID: 0003_codex_oauth
Revises: 0002_hardening
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_codex_oauth"
down_revision = "0002_hardening"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("provider_credentials") as batch:
        batch.add_column(sa.Column("encrypted_access_token", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("encrypted_refresh_token", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("encrypted_id_token", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("oauth_account_id", sa.String(length=160), nullable=True))
        batch.add_column(sa.Column("oauth_expires_at", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("oauth_scopes", sa.JSON(), nullable=False, server_default="[]"))


def downgrade():
    with op.batch_alter_table("provider_credentials") as batch:
        batch.drop_column("oauth_scopes")
        batch.drop_column("oauth_expires_at")
        batch.drop_column("oauth_account_id")
        batch.drop_column("encrypted_id_token")
        batch.drop_column("encrypted_refresh_token")
        batch.drop_column("encrypted_access_token")
