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

