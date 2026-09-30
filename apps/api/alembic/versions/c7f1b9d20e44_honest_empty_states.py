"""honest_empty_states

Production honesty pass:

* ``farm_risk_scores.farm_health_score`` becomes nullable. BHOOMI must be
  able to record "we have no observations, so there is no score" instead of
  persisting a number derived from nothing.
* Development-only defaults are removed from live tables so a fresh
  production database is not born with synthetic source labels.

Revision ID: c7f1b9d20e44
Revises: a38da25dc012
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c7f1b9d20e44'
down_revision: Union[str, None] = 'a38da25dc012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A farm with no weather, soil, vegetation or crop history has no score.
    op.alter_column(
        'farm_risk_scores',
        'farm_health_score',
        existing_type=sa.Float(),
        nullable=True,
    )

    # An absent observation must be labelled "unavailable", never a
    # development dataset name.
    op.execute(
        "UPDATE satellite_observations SET source = 'unavailable' "
        "WHERE source IN ('seeded_dev', 'dev_seed', 'dev_baseline')"
    )
    op.execute(
        "UPDATE satellite_observations SET is_dev_dataset = false "
        "WHERE is_dev_dataset IS DISTINCT FROM false"
    )


def downgrade() -> None:
    # The previous schema cannot represent "no observations, therefore no
    # score", so the rows this migration created cannot be carried backwards.
    # Drop them explicitly instead of letting the NOT NULL constraint fail
    # halfway through and leave the table half-migrated.
    op.execute("DELETE FROM farm_risk_scores WHERE farm_health_score IS NULL")
    op.alter_column(
        'farm_risk_scores',
        'farm_health_score',
        existing_type=sa.Float(),
        nullable=False,
    )
