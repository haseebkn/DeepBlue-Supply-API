"""Initial schema

Revision ID: 7cbe912a52ef
Revises: 
Create Date: 2026-07-09 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cbe912a52ef'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- assets table ---
    op.create_table(
        'assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('condition', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assets_id'), 'assets', ['id'], unique=False)

    # --- inventory table ---
    op.create_table(
        'inventory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('part_name', sa.String(length=100), nullable=False),
        sa.Column('part_number', sa.String(length=50), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_id'), 'inventory', ['id'], unique=False)
    op.create_index(op.f('ix_inventory_part_number'), 'inventory', ['part_number'], unique=True)

    # --- maintenance_reports table ---
    op.create_table(
        'maintenance_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('action_taken', sa.Text(), nullable=True),
        sa.Column('urgency', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_maintenance_reports_id'), 'maintenance_reports', ['id'], unique=False)

    # --- extraction_tasks table ---
    op.create_table(
        'extraction_tasks',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('field_notes', sa.Text(), nullable=False),
        sa.Column('extracted_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('extraction_tasks')
    op.drop_index(op.f('ix_maintenance_reports_id'), table_name='maintenance_reports')
    op.drop_table('maintenance_reports')
    op.drop_index(op.f('ix_inventory_part_number'), table_name='inventory')
    op.drop_index(op.f('ix_inventory_id'), table_name='inventory')
    op.drop_table('inventory')
    op.drop_index(op.f('ix_assets_id'), table_name='assets')
    op.drop_table('assets')
