from fpdf import FPDF  # pyright: ignore[reportMissingModuleSource]

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=9)

lines = """COMMISSIONING & QUALITY ASSURANCE REPORT
Project: Hyperscale Data Centre - Chennai Campus
Document No: CX-QA-001  Rev 2  Date: June 2026
Standard: TIA-942-B / Uptime Institute Tier III

1. TEST STATUS SUMMARY
Total Tests Planned: 48  Completed: 31  Passed: 27  Failed: 3  Pending: 1
Non-Conformances: 4 total (2 Open, 2 Closed)

2. POWER SYSTEMS COMMISSIONING

Test CX-PWR-001: UPS Load Bank Test at 100% Load
Standard: TIA-942 Section 6.1 - UPS must sustain 100% load for 4 hours
Result: FAIL - UPS Unit 2 tripped at 87% load after 2.1 hours
NCR-001 (OPEN): UPS Unit 2 overload protection mis-set. Severity: HIGH
Action: Eaton engineer on site 22 June 2026. Retest: 25 June 2026

Test CX-PWR-002: Generator Auto-Start and Load Transfer Test
Standard: Tier III - Generator must start and accept load within 10 seconds
Result: PASS - All 3 generators started within 8 seconds. Tested: 10 June 2026

Test CX-PWR-003: 2N UPS Redundancy Test
Standard: Tier III - Single UPS failure must not impact IT load
Result: PASS - IT load transferred to standby UPS within 20ms. Tested: 12 June 2026

Test CX-PWR-004: Battery Autonomy Test at Full Load
Standard: TIA-942 - Minimum 15 minutes battery backup at full load
Result: PASS - 18.5 minutes achieved at 100% load. Tested: 11 June 2026

Test CX-PWR-005: HV Switchgear Interlock Test
Standard: IE Rules 1956 - Interlock must prevent unsafe switching
Result: PENDING - Waiting for ABB replacement panel (ETA 30 June 2026)

Test CX-PWR-006: Earth Resistance Test
Standard: IS 3043 - Earth resistance less than 1 ohm
Result: PASS - 0.4 ohm measured at main earth pit. Tested: 5 June 2026

3. COOLING SYSTEMS COMMISSIONING

Test CX-COOL-001: Chiller Efficiency Test at Design Load
Standard: MECH-SPEC-002 - COP minimum 6.0 at design conditions
Result: PASS - COP 6.4 measured at 95% load. Tested: 8 June 2026

Test CX-COOL-002: Cooling Redundancy Test N+1
Standard: Tier III - Single chiller failure must not impact cooling
Result: PASS - Standby chiller started automatically in 45 seconds. Tested: 9 June 2026

Test CX-COOL-003: CRAH Unit Airflow and Temperature Test
Standard: ASHRAE A2 - Inlet temperature must not exceed 35 degrees C
Result: FAIL - Hot aisle reached 38 degrees C at 60% IT load
NCR-002 (OPEN): Blanking panels missing in rack rows 3 and 4. Severity: HIGH
Action: Install blanking panels by 20 June 2026. Retest: 22 June 2026

Test CX-COOL-004: Water Leak Detection System Test
Standard: Alarm must trigger within 30 seconds
Result: PASS - Alarm in 12 seconds. Tested: 6 June 2026

4. FIRE SUPPRESSION COMMISSIONING

Test CX-FIRE-001: FM200 Gas Suppression Discharge Test
Standard: NFPA 2001 - Agent concentration 8% within 10 seconds
Result: PASS - Simulation confirmed. Tested: 14 June 2026

Test CX-FIRE-002: Fire Alarm Integration with BMS
Result: PASS - HVAC shutdown in 3 seconds. Tested: 14 June 2026

5. NON-CONFORMANCE REGISTER

NCR-001: UPS Unit 2 Overload Trip (OPEN) - HIGH
UPS Unit 2 tripped at 87% load. Overload protection threshold mis-set.
TIA-942 requires 100% load for 4 hours. Retest: 25 June 2026

NCR-002: CRAH Hot Aisle Temperature Exceedance (OPEN) - HIGH
Hot aisle 38 degrees C at 60% load. Blanking panels missing rows 3 and 4.
ASHRAE A2 max inlet 35 degrees C. Retest: 22 June 2026

NCR-003: Switchgear Transit Damage (CLOSED) - CRITICAL
ABB switchgear panel damaged in transit. Replacement ordered ETA 30 June 2026.

NCR-004: Generator Exhaust Temperature Alarm (CLOSED) - MEDIUM
Generator 2 faulty thermocouple replaced by Cummins. Closed: 28 May 2026

6. TIER III CERTIFICATION READINESS

Criteria Met: 18 of 22
Outstanding:
- UPS Unit 2 overload test (NCR-001) retest 25 June 2026
- CRAH airflow test (NCR-002) retest 22 June 2026
- HV Switchgear interlock (CX-PWR-005) pending panel replacement
- 48-hour integrated systems run not yet scheduled
Estimated Tier III Audit Readiness: 15 July 2026""".split("\n")

for line in lines:
    pdf.cell(0, 4.5, txt=line, ln=True)

pdf.output("commissioning_qa.pdf")
print("commissioning_qa.pdf created successfully")