from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=9)

lines = """SUPPLY CHAIN & PROCUREMENT STATUS REPORT
Project: Hyperscale Data Centre - Chennai Campus
Document No: PROC-STATUS-001  Rev 1  Date: June 2026
Prepared by: Procurement Manager

1. CRITICAL EQUIPMENT PROCUREMENT STATUS

1.1 UPS Systems (2N Redundancy)
Manufacturer: Eaton 9PX Series
Quantity: 8 units (4 per power train)
PO: PO-2026-001  Supplier: Eaton India Pvt Ltd, Pune
Lead Time: 18 weeks   Order Date: 15 Feb 2026
Expected Delivery: 20 June 2026
Status: IN PRODUCTION - Week 16 of 18
Risk Level: HIGH - Only 2 weeks buffer before installation window (Week 16-20)
Action: Expedite factory acceptance test. Confirm transport logistics.

1.2 Diesel Generators (2N+1)
Manufacturer: Cummins C2000D5
Quantity: 3 units (2000 kVA each)
PO: PO-2026-002  Supplier: Cummins India Ltd, Pune
Lead Time: 20 weeks   Order Date: 1 Feb 2026
Expected Delivery: 24 June 2026
Status: IN PRODUCTION - Week 18 of 20
Risk Level: MEDIUM - On schedule but FAT not yet scheduled
Action: Schedule FAT for Week 19. Arrange heavy transport permits.

1.3 Switchgear - 33kV HV
Manufacturer: ABB UniGear ZS1
Quantity: 2 panels
PO: PO-2026-003  Supplier: ABB India, Vadodara
Status: DELIVERED WITH DAMAGE - Transit damage to one panel
Replacement Panel ETA: 30 June 2026
Risk Level: CRITICAL - 2-week delay already impacted civil works
Impact: Commissioning pushed from Week 22 to Week 24
Action: Daily status update from ABB. Expedite replacement.

1.4 CRAH Units
Manufacturer: Stulz CyberAir 3PRO
Quantity: 12 units (3 batches of 4)
Supplier: Stulz India Pvt Ltd, Mumbai
Batch 1: DELIVERED - 4 units on site (1 Apr 2026)
Batch 2: DELAYED 6 WEEKS - Was 15 May, now 30 June 2026
Batch 3: ON SCHEDULE - Expected 30 July 2026
Risk Level: HIGH - Only 4 of 12 CRAH units on site
Impact: Cooling commissioning blocked until 8+ units installed
Action: Accelerate Batch 2. Evaluate alternative supplier for Batch 3.

1.5 Cooling Towers
Manufacturer: Baltimore Aircoil Company (BAC)
Quantity: 4 units
PO: PO-2026-005  Supplier: BAC India, Chennai
Lead Time: 12 weeks  Order Date: 1 Apr 2026
Expected Delivery: 24 June 2026
Status: IN FABRICATION - Week 8 of 12
Risk Level: LOW - On schedule. Local supplier.

1.6 Chillers
Manufacturer: Carrier AquaForce 30XW
Quantity: 4 units
Status: DELIVERED AND INSTALLED (15 Apr 2026)
Risk Level: LOW - Installed and pressure tested.

2. SUPPLY CHAIN RISK SUMMARY

CRITICAL: ABB Switchgear replacement panel - ETA 30 June 2026
HIGH: UPS Systems - 2-week buffer only, FAT not confirmed
HIGH: CRAH Units Batch 2 - 6-week delay, cooling commissioning blocked
MEDIUM: Generators - FAT not scheduled, heavy transport permits pending
LOW: Cooling Towers - On schedule
LOW: Chillers - Delivered and installed

3. CRITICAL PATH IMPACT

ABB switchgear damage (CRITICAL) blocks:
- HV cable termination
- Electrical commissioning (pushed Week 22 to Week 24)
- Overall project at risk of 2-4 week delay to Tier III audit

CRAH delay (HIGH) blocks:
- Cooling commissioning (needs 8+ units)
- IT load testing (needs cooling operational)

4. OPEN PROCUREMENT ACTIONS

PA-001: ABB switchgear replacement status - Due 20 Jun - Procurement Manager
PA-002: Eaton UPS FAT scheduling - Due 18 Jun - Procurement Manager
PA-003: Cummins generator FAT scheduling - Due 22 Jun - MEP Contractor
PA-004: Stulz CRAH Batch 2 acceleration - Due 20 Jun - Procurement Manager
PA-005: Evaluate alternate CRAH supplier for Batch 3 - Due 25 Jun - Project Director
""".split("\n")

for line in lines:
    pdf.cell(0, 4.5, txt=line, ln=True)

pdf.output("supply_chain.pdf")
print("supply_chain.pdf created successfully")
