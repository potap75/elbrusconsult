import pytest


@pytest.fixture
def seeded_db(db):
    """Run the `seed` management command once per test that depends on content."""
    from django.core.management import call_command

    call_command("seed")
    return db
