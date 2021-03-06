"""Add comments

Revision ID: 96922536e019
Revises: 29985c21159d
Create Date: 2018-05-15 13:43:05.961759

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '96922536e019'
down_revision = '29985c21159d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('comment',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('package_id', sa.BigInteger(), nullable=False),
    sa.Column('author', sa.String(length=64), nullable=False),
    sa.Column('created', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('contents', sa.String(length=10240), nullable=False),
    sa.ForeignKeyConstraint(['package_id'], ['package.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comment_created'), 'comment', ['created'], unique=False)
    op.create_index(op.f('ix_comment_package_id'), 'comment', ['package_id'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_comment_package_id'), table_name='comment')
    op.drop_index(op.f('ix_comment_created'), table_name='comment')
    op.drop_table('comment')
    # ### end Alembic commands ###
