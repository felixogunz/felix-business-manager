from datetime import datetime, timedelta, timezone

from app.models.user import User

def test_health_endpoint(test_client):
    response = test_client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_and_list_clients(test_client):
    create_response = test_client.post(
        "/api/clients",
        json={
            "full_name": "Test Client",
            "email": "test@example.com",
            "company": "Example Ltd",
        },
    )

    assert create_response.status_code == 201
    assert create_response.json()["full_name"] == "Test Client"

    list_response = test_client.get("/api/clients")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["email"] == "test@example.com"


def test_create_project_for_client(test_client):
    client_response = test_client.post(
        "/api/clients",
        json={"full_name": "Project Owner"},
    )
    client_id = client_response.json()["id"]

    project_response = test_client.post(
        "/api/projects",
        json={
            "client_id": client_id,
            "title": "Website Development",
            "status": "in_progress",
            "budget": "250000.00",
        },
    )

    assert project_response.status_code == 201
    assert project_response.json()["title"] == "Website Development"
    assert project_response.json()["client_id"] == client_id


def test_reject_project_for_missing_client(test_client):
    response = test_client.post(
        "/api/projects",
        json={
            "client_id": 99999,
            "title": "Invalid Project",
        },
    )

    assert response.status_code == 404


def test_create_interaction(test_client):
    client_response = test_client.post(
        "/api/clients",
        json={"full_name": "Interaction Owner"},
    )
    client_id = client_response.json()["id"]

    response = test_client.post(
        "/api/interactions",
        json={
            "client_id": client_id,
            "interaction_type": "call",
            "subject": "Initial consultation",
            "details": "Discussed project requirements.",
        },
    )

    assert response.status_code == 201
    assert response.json()["subject"] == "Initial consultation"


def test_dashboard_counts(test_client):
    test_client.post(
        "/api/clients",
        json={"full_name": "Dashboard Client"},
    )

    response = test_client.get("/api/dashboard")

    assert response.status_code == 200

    data = response.json()
    assert data["clients"] == 1
    assert data["projects"] == 0
    assert data["interactions"] == 0
    assert data["active_projects"] == 0


def test_reject_empty_client_name(test_client):
    response = test_client.post(
        "/api/clients",
        json={"full_name": "   "},
    )
    assert response.status_code == 422


def test_reject_null_client_name_update(test_client):
    create_response = test_client.post(
        "/api/clients",
        json={"full_name": "Valid Client"},
    )
    assert create_response.status_code == 201

    client_id = create_response.json()["id"]

    update_response = test_client.patch(
        f"/api/clients/{client_id}",
        json={"full_name": None},
    )

    assert update_response.status_code == 422


def test_update_client(test_client):
    created = test_client.post(
        "/api/clients",
        json={"full_name": "Original Name"},
    )
    assert created.status_code == 201
    client_id = created.json()["id"]

    updated = test_client.patch(
        f"/api/clients/{client_id}",
        json={"full_name": "Updated Name"},
    )

    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Updated Name"


def test_reject_empty_project_title(test_client):
    response = test_client.post(
        "/api/clients",
        json={"full_name": "Project Client"},
    )
    client_id = response.json()["id"]

    result = test_client.post(
        "/api/projects",
        json={"client_id": client_id, "title": "   "},
    )

    assert result.status_code == 422


def test_reject_invalid_project_status(test_client):
    response = test_client.post(
        "/api/clients",
        json={"full_name": "Status Client"},
    )
    client_id = response.json()["id"]

    result = test_client.post(
        "/api/projects",
        json={
            "client_id": client_id,
            "title": "Test Project",
            "status": "invalid_status",
        },
    )

    assert result.status_code == 422


def test_reject_interaction_for_wrong_client_project(test_client):
    first_client = test_client.post(
        "/api/clients",
        json={"full_name": "First Client"},
    ).json()

    second_client = test_client.post(
        "/api/clients",
        json={"full_name": "Second Client"},
    ).json()

    project = test_client.post(
        "/api/projects",
        json={
            "client_id": first_client["id"],
            "title": "First Client Project",
        },
    ).json()

    response = test_client.post(
        "/api/interactions",
        json={
            "client_id": second_client["id"],
            "project_id": project["id"],
            "interaction_type": "call",
            "subject": "Incorrect project association",
        },
    )

    assert response.status_code == 422


def test_clients_endpoint_requires_authentication(test_client):
    test_client.headers.pop("Authorization", None)

    response = test_client.get("/api/clients")

    assert response.status_code == 401


def test_dashboard_requires_authentication(test_client):
    test_client.headers.pop("Authorization", None)

    response = test_client.get("/api/dashboard")

    assert response.status_code == 401


def test_register_login_and_access_clients(test_client):
    registration = test_client.post(
        "/api/auth/register",
        json={
            "full_name": "Test Administrator",
            "email": "admin@example.com",
            "password": "SecureTestPassword123",
        },
    )

    assert registration.status_code == 201
    assert "hashed_password" not in registration.json()

    login = test_client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.com",
            "password": "SecureTestPassword123",
        },
    )

    assert login.status_code == 200
    token = login.json()["access_token"]

    clients_response = test_client.get(
        "/api/clients",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert clients_response.status_code == 200


def test_login_rejects_wrong_password(test_client):
    test_client.post(
        "/api/auth/register",
        json={
            "full_name": "Test Administrator",
            "email": "admin@example.com",
            "password": "SecureTestPassword123",
        },
    )

    response = test_client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.com",
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401


def authenticate_as_guest(test_client):
    """Create a guest account and authenticate the test client."""

    response = test_client.post("/api/auth/guest")

    assert response.status_code == 201, response.text

    result = response.json()
    token = result["access_token"]

    test_client.headers.update({
        "Authorization": f"Bearer {token}"
    })

    return result


def test_create_guest_session(test_client):
    result = authenticate_as_guest(test_client)

    assert result["user"]["is_guest"] is True
    assert result["user"]["trial_started_at"] is not None
    assert result["user"]["trial_expires_at"] is not None
    assert result["token_type"] == "bearer"


def test_guest_client_limit(test_client):
    authenticate_as_guest(test_client)

    for number in range(10):
        response = test_client.post(
            "/api/clients",
            json={
                "full_name": f"Guest Client {number + 1}"
            },
        )
        assert response.status_code == 201, response.text

    rejected = test_client.post(
        "/api/clients",
        json={"full_name": "Eleventh Guest Client"},
    )

    assert rejected.status_code == 403


def test_guest_project_limit(test_client):
    authenticate_as_guest(test_client)

    client_response = test_client.post(
        "/api/clients",
        json={"full_name": "Guest Project Client"},
    )

    assert client_response.status_code == 201
    client_id = client_response.json()["id"]

    for number in range(5):
        response = test_client.post(
            "/api/projects",
            json={
                "client_id": client_id,
                "title": f"Guest Project {number + 1}",
            },
        )
        assert response.status_code == 201, response.text

    rejected = test_client.post(
        "/api/projects",
        json={
            "client_id": client_id,
            "title": "Sixth Guest Project",
        },
    )

    assert rejected.status_code == 403


def test_guest_interaction_limit(test_client):
    authenticate_as_guest(test_client)

    client_response = test_client.post(
        "/api/clients",
        json={"full_name": "Guest Interaction Client"},
    )

    assert client_response.status_code == 201
    client_id = client_response.json()["id"]

    for number in range(20):
        response = test_client.post(
            "/api/interactions",
            json={
                "client_id": client_id,
                "interaction_type": "call",
                "subject": f"Guest Interaction {number + 1}",
                "details": "Automated guest trial test.",
            },
        )
        assert response.status_code == 201, response.text

    rejected = test_client.post(
        "/api/interactions",
        json={
            "client_id": client_id,
            "interaction_type": "call",
            "subject": "Twenty-first interaction",
            "details": "This should be rejected.",
        },
    )

    assert rejected.status_code == 403

def test_expired_guest_cannot_access_workspace(test_client):
    result = authenticate_as_guest(test_client)
    guest_id = result["user"]["id"]

    # Simulate a trial that expired one second ago.
    with test_client.testing_session_local() as db:
        guest = db.get(User, guest_id)

        assert guest is not None

        guest.trial_expires_at = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        )

        db.commit()

    response = test_client.get("/api/clients")

    assert response.status_code == 403
    assert "trial has ended" in response.json()["detail"].lower()


def test_guest_registration_preserves_existing_data(test_client):
    # Start a guest session.
    guest = authenticate_as_guest(test_client)
    guest_id = guest["user"]["id"]

    # Create a client as the guest.
    client_response = test_client.post(
        "/api/clients",
        json={
            "full_name": "Preserved Guest Client",
            "email": "preserved@example.com",
        },
    )

    assert client_response.status_code == 201
    client_id = client_response.json()["id"]

    # Create a project belonging to that client.
    project_response = test_client.post(
        "/api/projects",
        json={
            "client_id": client_id,
            "title": "Preserved Guest Project",
        },
    )

    assert project_response.status_code == 201

    # Create an interaction belonging to that client.
    interaction_response = test_client.post(
        "/api/interactions",
        json={
            "client_id": client_id,
            "interaction_type": "call",
            "subject": "Preserved Guest Interaction",
            "details": "This record must survive registration.",
        },
    )

    assert interaction_response.status_code == 201

    # Convert the guest account into a permanent account.
    registration = test_client.post(
        "/api/auth/register",
        json={
            "full_name": "Converted Guest User",
            "email": "converted@example.com",
            "password": "SecureConvertedPassword123",
        },
    )

    assert registration.status_code == 201, registration.text

    converted_user = registration.json()["user"]

    # Confirm the original user account was updated, not replaced.
    assert converted_user["id"] == guest_id
    assert converted_user["is_guest"] is False
    assert converted_user["trial_started_at"] is None
    assert converted_user["trial_expires_at"] is None

    # Authenticate using the new permanent account token.
    new_token = registration.json()["access_token"]

    test_client.headers.update({
        "Authorization": f"Bearer {new_token}"
    })

    # Confirm that all guest data is still accessible.
    clients = test_client.get("/api/clients")
    projects = test_client.get("/api/projects")
    interactions = test_client.get("/api/interactions")

    assert clients.status_code == 200
    assert projects.status_code == 200
    assert interactions.status_code == 200

    assert any(
        item["id"] == client_id
        for item in clients.json()
    )

    assert any(
        item["title"] == "Preserved Guest Project"
        for item in projects.json()
    )

    assert any(
        item["subject"] == "Preserved Guest Interaction"
        for item in interactions.json()
    )


def test_registered_users_are_not_subject_to_guest_limits(test_client):
    # The test_client fixture authenticates a normal registered user.

    # Verify that registered users can create more than 10 clients.
    for number in range(11):
        response = test_client.post(
            "/api/clients",
            json={
                "full_name": f"Registered Client {number + 1}"
            },
        )
        assert response.status_code == 201, response.text

    # Create a client for the projects and interactions.
    client_response = test_client.post(
        "/api/clients",
        json={"full_name": "Registered Project Client"},
    )
    assert client_response.status_code == 201

    client_id = client_response.json()["id"]

    # Verify that registered users can create more than 5 projects.
    for number in range(6):
        response = test_client.post(
            "/api/projects",
            json={
                "client_id": client_id,
                "title": f"Registered Project {number + 1}",
            },
        )
        assert response.status_code == 201, response.text

    # Verify that registered users can create more than 20 interactions.
    for number in range(21):
        response = test_client.post(
            "/api/interactions",
            json={
                "client_id": client_id,
                "interaction_type": "call",
                "subject": f"Registered Interaction {number + 1}",
                "details": "Registered account limit test.",
            },
        )
        assert response.status_code == 201, response.text
