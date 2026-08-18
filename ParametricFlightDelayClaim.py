# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json
import typing


class ParametricFlightDelayClaim(gl.Contract):
    """
    Parametric Flight Delay Claim primitive.

    A reusable Intelligent Contract that settles a flight-delay claim using
    live web evidence + LLM extraction, with thoughtful Equivalence Principle
    consensus. Validators independently re-fetch and re-extract, then accept
    only if the decision fields match (with numeric tolerance on minutes).

    This is intentionally a clean primitive (no full product/frontend) so other
    builders can reuse or extend it.
    """

    # --- State ---
    flight_number: str
    flight_date: str
    delay_threshold_minutes: u256
    status_url: str
    claimant: Address

    has_resolved: bool
    status: str                  # "open" | "approved" | "rejected"
    delay_minutes: u256
    flight_status: str           # "delayed" | "cancelled" | "on_time" | "unknown"
    resolution_note: str

    def __init__(
        self,
        flight_number: str,
        flight_date: str,
        delay_threshold_minutes: int,
        status_url: str,
    ):
        self.flight_number = flight_number
        self.flight_date = flight_date
        self.delay_threshold_minutes = u256(delay_threshold_minutes)
        self.status_url = status_url
        self.claimant = gl.message.sender_address

        self.has_resolved = False
        self.status = "open"
        self.delay_minutes = u256(0)
        self.flight_status = ""
        self.resolution_note = ""

    # --- Views ---

    @gl.public.view
    def get_claim_info(self) -> dict:
        return {
            "flight_number": self.flight_number,
            "flight_date": self.flight_date,
            "delay_threshold_minutes": int(self.delay_threshold_minutes),
            "status_url": self.status_url,
            "claimant": str(self.claimant),
            "has_resolved": self.has_resolved,
            "status": self.status,
            "delay_minutes": int(self.delay_minutes),
            "flight_status": self.flight_status,
            "resolution_note": self.resolution_note,
        }

    @gl.public.view
    def get_status(self) -> str:
        return self.status

    @gl.public.view
    def is_resolved(self) -> bool:
        return self.has_resolved

    # --- Core resolution with real consensus ---

    @gl.public.write
    def resolve(self) -> dict:
        if self.has_resolved:
            return {
                "ok": False,
                "message": "Already resolved",
                "status": self.status,
            }

        threshold = int(self.delay_threshold_minutes)
        flight_number = self.flight_number
        flight_date = self.flight_date
        status_url = self.status_url

        def leader_fn() -> dict:
            # 1. Fetch live status page
            page = gl.nondet.web.render(status_url, mode="text")

            # 2. Ask LLM for strict structured extraction
            prompt = f"""
You are extracting flight status facts for a parametric insurance claim.

Flight number: {flight_number}
Flight date: {flight_date}
Page content:
{page[:12000]}

Extract ONLY these fields. Respond with valid JSON and nothing else:
{{
  "flight_status": "delayed" | "cancelled" | "on_time" | "unknown",
  "delay_minutes": <integer or 0 if unknown/on_time>,
  "note": "<one short sentence of evidence from the page>"
}}

Rules:
- If the flight is cancelled, set flight_status to "cancelled" and delay_minutes to 0.
- If clearly delayed, put the best estimate of delay in minutes.
- If on time or landed on schedule, use "on_time" and 0.
- If you cannot tell, use "unknown" and 0.
- Do not invent numbers that are not supported by the page.
"""
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                # fallback if response_format is ignored
                raw = json.loads(str(raw).replace("```json", "").replace("```", "").strip())

            status = str(raw.get("flight_status", "unknown")).lower().strip()
            if status not in ("delayed", "cancelled", "on_time", "unknown"):
                status = "unknown"

            try:
                minutes = int(raw.get("delay_minutes", 0))
            except Exception:
                minutes = 0
            if minutes < 0:
                minutes = 0

            note = str(raw.get("note", ""))[:300]

            # Decision: approved if cancelled OR delay meets/exceeds threshold
            approved = (status == "cancelled") or (status == "delayed" and minutes >= threshold)

            return {
                "flight_status": status,
                "delay_minutes": minutes,
                "note": note,
                "approved": approved,
            }

        def validator_fn(leader_result) -> bool:
            # Must be a successful return
            if not isinstance(leader_result, gl.vm.Return):
                return False

            leader = leader_result.calldata
            if not isinstance(leader, dict):
                return False

            # Re-run independently
            mine = leader_fn()

            # Decision fields must match
            if mine["approved"] != leader.get("approved"):
                return False
            if mine["flight_status"] != leader.get("flight_status"):
                return False

            # Numeric tolerance on delay minutes (±30)
            leader_mins = int(leader.get("delay_minutes", 0))
            my_mins = int(mine["delay_minutes"])
            if abs(leader_mins - my_mins) > 30:
                return False

            return True

        # Run consensus
        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        # Persist outcome
        self.has_resolved = True
        self.flight_status = str(result["flight_status"])
        self.delay_minutes = u256(int(result["delay_minutes"]))
        self.resolution_note = str(result.get("note", ""))[:300]

        if result["approved"]:
            self.status = "approved"
        else:
            self.status = "rejected"

        return {
            "ok": True,
            "status": self.status,
            "flight_status": self.flight_status,
            "delay_minutes": int(self.delay_minutes),
            "note": self.resolution_note,
        }
