import pytest

def test_create_asset(client):
    """Verify that creating a new asset works correctly and returns status 201."""
    response = client.post(
        "/api/v1/assets",
        json={
            "name": "Thruster Alpha",
            "condition": "Brand New",
            "status": "Operational"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Thruster Alpha"
    assert data["condition"] == "Brand New"
    assert data["status"] == "Operational"
    assert "id" in data


def test_get_asset_by_id(client):
    """Verify that retrieving a created asset by ID returns status 200 with matching details."""
    create_response = client.post(
        "/api/v1/assets",
        json={
            "name": "Propulsion Unit B",
            "condition": "Worn",
            "status": "Maintenance Required"
        }
    )
    asset_id = create_response.json()["id"]

    # Query the specific asset
    response = client.get(f"/api/v1/assets/{asset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == asset_id
    assert data["name"] == "Propulsion Unit B"
    assert data["condition"] == "Worn"


def test_get_nonexistent_asset(client):
    """Verify that querying a non-existent asset ID returns status 404."""
    response = client.get("/api/v1/assets/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found"


def test_create_inventory_item(client):
    """Verify that creating an inventory item parses correctly and returns status 201."""
    response = client.post(
        "/api/v1/inventory",
        json={
            "part_name": "Neoprene O-Ring size 4B",
            "part_number": "OR-4B-NEO",
            "quantity": 15,
            "location": "Locker A-1"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["part_name"] == "Neoprene O-Ring size 4B"
    assert data["part_number"] == "OR-4B-NEO"
    assert data["quantity"] == 15


def test_create_inventory_duplicate_part_number(client):
    """Verify that adding a part with an already existing part number yields status 400."""
    payload = {
        "part_name": "Check Valve 2 Inch",
        "part_number": "CV-200",
        "quantity": 3,
        "location": "Shelf B-2"
    }
    # First post succeeds
    res1 = client.post("/api/v1/inventory", json=payload)
    assert res1.status_code == 201

    # Second post with duplicate part number fails
    res2 = client.post("/api/v1/inventory", json=payload)
    assert res2.status_code == 400
    assert res2.json()["detail"] == "Part number already exists in inventory"
