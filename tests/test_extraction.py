import pytest
from unittest.mock import patch, AsyncMock
from services.ai_extractor import ExtractedMaintenanceData, PartExtracted
from main import Asset, InventoryItem, MaintenanceReport, ExtractionTask


@patch("services.ai_extractor.AIExtractorService.extract", new_callable=AsyncMock)
def test_async_extraction_pipeline(mock_extract, client, db_session):
    """
    Verifies that POSTing to /api/v1/extract immediately returns a 202 status and a task UUID.
    Validates that the background processing completes correctly and persists all structured side effects
    (Asset records, Maintenance logs, and Inventory quantities) to the database.
    """
    # 1. Configure the mock extractor output
    mock_extract.return_value = ExtractedMaintenanceData(
        asset_name="Main Engine Turbocharger",
        condition="Cracked",
        recommended_action="Replace O-ring seal and inspect brackets",
        urgency="High",
        parts_identified=[
            PartExtracted(part_name="O-ring seal", part_number="OR-992-G", quantity=2)
        ]
    )

    # 2. Submit technician notes to endpoint
    notes = "Main engine turbocharger housing showing minor cracking. Need 2 replacement O-ring seals (Part #OR-992-G) immediately."
    response = client.post(
        "/api/v1/extract", 
        json={"field_notes": notes}
    )
    
    assert response.status_code == 202
    task_data = response.json()
    assert "task_id" in task_data
    assert task_data["status"] == "pending"
    task_id = task_data["task_id"]

    # 3. Retrieve task status (FastAPI TestClient processes background tasks inline before returning)
    poll_response = client.get(f"/api/v1/extract/tasks/{task_id}")
    assert poll_response.status_code == 200
    poll_data = poll_response.json()
    assert poll_data["status"] == "completed"
    
    extracted = poll_data["extracted_data"]
    assert extracted["asset_name"] == "Main Engine Turbocharger"
    assert extracted["condition"] == "Cracked"
    assert extracted["urgency"] == "High"
    assert len(extracted["parts_identified"]) == 1
    assert extracted["parts_identified"][0]["part_number"] == "OR-992-G"
    assert extracted["parts_identified"][0]["quantity"] == 2

    # 4. Assert all database side effects were written successfully
    # Asset should be auto-created and set to 'Offline' due to High urgency
    db_asset = db_session.query(Asset).filter(Asset.name == "Main Engine Turbocharger").first()
    assert db_asset is not None
    assert db_asset.condition == "Cracked"
    assert db_asset.status == "Offline"

    # Maintenance report should be created and linked to the asset
    db_report = db_session.query(MaintenanceReport).filter(MaintenanceReport.asset_id == db_asset.id).first()
    assert db_report is not None
    assert db_report.urgency == "High"
    assert "cracking" in db_report.description

    # Spare parts should be added to inventory catalog
    db_part = db_session.query(InventoryItem).filter(InventoryItem.part_number == "OR-992-G").first()
    assert db_part is not None
    assert db_part.part_name == "O-ring seal"
    assert db_part.quantity == 2


@patch("services.ai_extractor.AIExtractorService.extract", new_callable=AsyncMock)
def test_extraction_task_failure_handling(mock_extract, client, db_session):
    """
    Verifies that if the extraction service throws an exception, the background worker
    handles it cleanly, updating the task status to 'failed' and logging the error.
    """
    # Force mock extractor to raise exception
    mock_extract.side_effect = Exception("LLM connection timeout")

    notes = "Generators showing high wear."
    response = client.post(
        "/api/v1/extract", 
        json={"field_notes": notes}
    )
    assert response.status_code == 202
    task_id = response.json()["task_id"]

    # Poll status
    poll_response = client.get(f"/api/v1/extract/tasks/{task_id}")
    assert poll_response.status_code == 200
    poll_data = poll_response.json()
    assert poll_data["status"] == "failed"
    assert "LLM connection timeout" in poll_data["extracted_data"]["error"]
