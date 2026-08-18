# ParametricFlightDelayClaim

Standalone GenLayer Intelligent Contract for parametric flight-delay claims.

## Purpose
Create a claim with flight number, date, delay threshold and a public status URL. Calling resolve() fetches live web evidence, extracts structured facts with an LLM, and reaches consensus on approved or rejected.

## Consensus
Leader and validators independently render the status URL and run the same extraction. A custom validator (gl.vm.run_nondet_unsafe) accepts only when:
- binary decision matches
- flight_status matches
- delay_minutes is within ±30 minutes

## Deployed (Testnet Bradbury)
0x6e1df4E9De7E0D541a6b7923FEf10cd750659EE4

Example: BA287 on 2026-08-15 resolved as REJECTED (on time, 180 min threshold not met).

## Methods
- get_claim_info()
- get_status()
- is_resolved()
- resolve()

## License
MIT
