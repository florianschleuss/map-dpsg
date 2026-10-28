"""Always restore the full current schema after historical migration assertions."""
from django.db.migrations.executor import MigrationExecutor


def migrate_latest(connection):
    executor=MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
