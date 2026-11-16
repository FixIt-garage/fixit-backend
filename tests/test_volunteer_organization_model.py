import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.user import User, UserRole
from app.models.volunteer import VolunteerOrganization


def make_owner(db, email: str = "org@example.com") -> User:
    user = User(
        email=email,
        password_hash="hashed-password",
        first_name="Test",
        last_name="Organization",
        role=UserRole.VOLUNTEER_ORGANIZATION,
    )
    db.add(user)
    db.flush()
    return user


def test_new_organization_is_not_verified(test_session_factory) -> None:
    with test_session_factory() as db:
        owner = make_owner(db)
        organization = VolunteerOrganization(owner_user_id=owner.id, name="Тепла хата")
        db.add(organization)
        db.commit()
        db.refresh(organization)

        assert organization.is_verified is False
        assert organization.owner.id == owner.id


def test_each_user_can_have_only_one_organization(test_session_factory) -> None:
    with test_session_factory() as db:
        owner = make_owner(db)
        db.add(VolunteerOrganization(owner_user_id=owner.id, name="First"))
        db.commit()
        owner_id = owner.id

    with test_session_factory() as db, pytest.raises(IntegrityError):
        db.add(VolunteerOrganization(owner_user_id=owner_id, name="Second"))
        db.commit()


def test_different_users_have_their_own_organizations(test_session_factory) -> None:
    with test_session_factory() as db:
        first = make_owner(db, "first@example.com")
        second = make_owner(db, "second@example.com")
        db.add_all(
            [
                VolunteerOrganization(owner_user_id=first.id, name="First"),
                VolunteerOrganization(owner_user_id=second.id, name="Second"),
            ]
        )
        db.commit()

        total = db.scalar(select(func.count()).select_from(VolunteerOrganization))
        assert total == 2


from alembic import command  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from tests.test_migrations import (  # noqa: E402
    _alembic_config,
    _assert_connected_to,
    disposable_database,
    requires_db,
)

PRE_REVISION = "232d55a844e1"


@requires_db
def test_migration_stops_on_an_owner_with_two_organizations() -> None:
    with disposable_database() as url:
        _assert_connected_to(url)
        config = _alembic_config(url)
        command.upgrade(config, PRE_REVISION)
        engine = create_engine(url)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO users (email, password_hash, first_name, last_name) "
                        "VALUES ('org@example.com', 'hash', 'Test', 'Owner')"
                    )
                )
                owner_id = conn.execute(text("SELECT id FROM users")).scalar_one()
                for name in ("First", "Second"):
                    conn.execute(
                        text(
                            "INSERT INTO volunteer_organizations (owner_user_id, name) "
                            "VALUES (:owner, :name)"
                        ),
                        {"owner": owner_id, "name": name},
                    )
                first_id = conn.execute(
                    text("SELECT id FROM volunteer_organizations WHERE name = 'First'")
                ).scalar_one()
                conn.execute(
                    text(
                        "INSERT INTO volunteer_requests (organization_id, title, description) "
                        "VALUES (:org, 'Help', 'Needed')"
                    ),
                    {"org": first_id},
                )

            with pytest.raises(Exception, match="more than one volunteer organization"):
                command.upgrade(config, "head")

            with engine.connect() as conn:
                organizations = conn.execute(
                    text("SELECT count(*) FROM volunteer_organizations")
                ).scalar_one()
                requests = conn.execute(
                    text("SELECT count(*) FROM volunteer_requests")
                ).scalar_one()
            assert (organizations, requests) == (2, 1)
        finally:
            engine.dispose()


@requires_db
def test_generated_sql_contains_the_duplicate_check(capsys) -> None:
    with disposable_database() as url:
        command.upgrade(_alembic_config(url), f"{PRE_REVISION}:0ed6e40fadf3", sql=True)
        script = capsys.readouterr().out

    assert "more than one volunteer organization" in script
    assert script.index("DO $$") < script.index("ADD COLUMN is_verified")
    assert "uq_volunteer_organizations_owner_user_id" in script
