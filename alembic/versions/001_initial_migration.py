from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'trades',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('direction', sa.String(), nullable=False),
        sa.Column('entry_price', sa.Numeric(20, 8), nullable=False),
        sa.Column('exit_price', sa.Numeric(20, 8), nullable=True),
        sa.Column('quantity', sa.Numeric(20, 8), nullable=False),
        sa.Column('pnl', sa.Numeric(20, 8), nullable=True),
        sa.Column('pnl_pct', sa.Numeric(10, 4), nullable=True),
        sa.Column('strategy_name', sa.String(), nullable=False),
        sa.Column('regime', sa.String(), nullable=False),
        sa.Column('close_reason', sa.String(), nullable=True),
        sa.Column('opened_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('is_open', sa.Boolean(), default=True)
    )
    op.create_table(
        'performance_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('balance', sa.Numeric(20, 8), nullable=False),
        sa.Column('equity', sa.Numeric(20, 8), nullable=False),
        sa.Column('daily_pnl', sa.Numeric(20, 8), nullable=False),
        sa.Column('win_rate', sa.Numeric(10, 4), nullable=False),
        sa.Column('total_trades', sa.Integer(), nullable=False)
    )
    op.create_table(
        'regime_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('regime', sa.String(), nullable=False),
        sa.Column('confidence', sa.Numeric(10, 4), nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('ended_at', sa.DateTime(), nullable=True)
    )

def downgrade() -> None:
    op.drop_table('regime_history')
    op.drop_table('performance_snapshots')
    op.drop_table('trades')
