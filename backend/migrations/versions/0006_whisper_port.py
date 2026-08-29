"""move legacy local whisper providers to the active port"""
from alembic import op
import sqlalchemy as sa

revision = "0006_whisper_port"
down_revision = "0005_task_leases"
branch_labels = None
depends_on = None


def upgrade():
    providers = sa.table(
        "providers",
        sa.column("adapter", sa.String()),
        sa.column("base_url", sa.String()),
    )
    op.execute(
        providers.update()
        .where(providers.c.adapter == "whisper_cpp")
        .where(providers.c.base_url == "http://127.0.0.1:8765")
        .values(base_url="http://127.0.0.1:8766")
    )


def downgrade():
    # Do not rewrite user-edited provider URLs during downgrade.
    pass
