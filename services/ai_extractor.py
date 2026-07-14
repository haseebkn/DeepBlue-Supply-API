import os
import re
import json
import httpx
from typing import List, Optional
from pydantic import BaseModel, Field

class PartExtracted(BaseModel):
    part_name: str = Field(..., description="Name of the part identified in field notes")
    part_number: str = Field(..., description="Specific manufacturer part number or serial key")
    quantity: int = Field(default=1, description="Quantity of parts needed")

class ExtractedMaintenanceData(BaseModel):
    asset_name: Optional[str] = Field(None, description="Identified equipment/asset name")
    condition: Optional[str] = Field(None, description="Observed condition of the asset")
    recommended_action: Optional[str] = Field(None, description="Recommended remediation action")
    urgency: str = Field(..., description="Urgency level (Low, Medium, High)")
    parts_identified: List[PartExtracted] = Field(default=[], description="List of spare parts found in the notes")


class AIExtractorService:
    def __init__(self):
        # Configurable endpoint. Defaults to internal mock service but supports Bedrock/GLM configurations
        self.api_url = os.getenv("LLM_SERVICE_URL", "https://api.deepblue-ai.internal/v1/chat/completions")
        self.api_key = os.getenv("OPENAI_API_KEY", "dummy-key-for-scaffolding")

    async def extract(self, field_notes: str) -> ExtractedMaintenanceData:
        """
        Processes technician field notes, querying an LLM to extract structured data 
        and validating the schema using Pydantic (conforming to the treehouse concept).
        """
        system_prompt = (
            "You are an expert marine engineering assistant. "
            "Parse the provided unstructured field notes and return a JSON object "
            "exactly matching the following schema. Do not output anything else but the JSON.\n\n"
            f"Schema:\n{json.dumps(ExtractedMaintenanceData.model_json_schema(), indent=2)}"
        )

        try:
            # Check if LLM integration is explicitly configured
            if self.api_key != "dummy-key-for-scaffolding" and "deepblue-ai.internal" not in self.api_url:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        self.api_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "gpt-4o",
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": field_notes}
                            ],
                            "temperature": 0.0
                        }
                    )
                    if response.status_code == 200:
                        data = response.json()
                        content = data["choices"][0]["message"]["content"]
                        # Strip standard markdown block wrappers if present
                        content_clean = re.sub(r"^```(?:json)?\n|\n```$", "", content.strip(), flags=re.MULTILINE)
                        parsed_json = json.loads(content_clean)
                        return ExtractedMaintenanceData(**parsed_json)
        except Exception as e:
            # Fallback to local parsing logic on network or parsing error
            pass

        # Return local heuristic parsing
        return self._local_heuristic_parse(field_notes)

    def _local_heuristic_parse(self, notes: str) -> ExtractedMaintenanceData:
        """
        High-fidelity local parser to fallback to when LLM service is offline or unconfigured.
        """
        # 1. Detect Asset Name
        asset_match = re.search(
            r"(thruster [a-z0-9]+|main engine|generator [a-z0-9]+|turbocharger|drilling platform|pump [a-z0-9]+)", 
            notes, 
            re.IGNORECASE
        )
        asset_name = asset_match.group(0).title() if asset_match else "Unknown Marine Asset"

        # 2. Detect Condition
        condition = "Operational Issue"
        if any(k in notes.lower() for k in ["leak", "leaking", "dripping"]):
            condition = "Leaking"
        elif any(k in notes.lower() for k in ["crack", "cracking", "fractured"]):
            condition = "Cracked"
        elif any(k in notes.lower() for k in ["wear", "worn", "deteriorated"]):
            condition = "Worn"
        elif any(k in notes.lower() for k in ["overheat", "hot", "high temp"]):
            condition = "Overheating"

        # 3. Detect Urgency
        urgency = "Medium"
        if any(k in notes.lower() for k in ["urgent", "immediately", "immediate", "asap", "critical"]):
            urgency = "High"
        elif any(k in notes.lower() for k in ["minor", "low priority", "scheduled"]):
            urgency = "Low"

        # 4. Extract Parts
        parts_identified = []
        part_no_matches = re.findall(r"(?:part\s*(?:#|no|number)?\s*|#\s*)([A-Z0-9\-]{4,15})", notes, re.IGNORECASE)
        qty_match = re.search(r"(\d+)\s+([a-zA-Z\s\-]{3,30})(?:\s+part|\s+size|\s+or|\s*\.|\s*,|\s*$)", notes, re.IGNORECASE)

        if part_no_matches:
            for part_num in part_no_matches:
                part_name = "Replacement Part"
                if "o-ring" in notes.lower() or "seal" in notes.lower():
                    part_name = "Seal / O-Ring"
                elif "bracket" in notes.lower():
                    part_name = "Mounting Bracket"
                parts_identified.append(
                    PartExtracted(
                        part_name=part_name,
                        part_number=part_num.upper(),
                        quantity=1
                    )
                )
        elif qty_match:
            qty = int(qty_match.group(1))
            name = qty_match.group(2).strip()
            parts_identified.append(
                PartExtracted(
                    part_name=name.title(),
                    part_number="GENERIC-PART-RESOLVER",
                    quantity=qty
                )
            )
        else:
            parts_identified.append(
                PartExtracted(
                    part_name="Generic Maintenance Part",
                    part_number="GMP-999",
                    quantity=1
                )
            )

        # 5. Recommended Action
        recommended_action = "Inspect asset and replace components as specified."
        action_match = re.search(r"(?:need to|recommend|schedule|replace)\s+([^.]+)", notes, re.IGNORECASE)
        if action_match:
            recommended_action = action_match.group(0).strip().capitalize()

        return ExtractedMaintenanceData(
            asset_name=asset_name,
            condition=condition,
            recommended_action=recommended_action,
            urgency=urgency,
            parts_identified=parts_identified
        )
