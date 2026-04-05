import pandas as pd
from openpyxl.styles import Alignment, Font

data = [
    # Stock Replenishment
    ['TC-SR01', 'Approve ML Recommendation', 'Verify approving an ML recommendation generates a Purchase Order.', 'Admin logged in; Pending ML recommendation exists', '1. Open Stock Replenishment \n2. Select Supplier \n3. Click Approve', 'Product: PRD-1001\nSupplier: SUP-001', 'Status changes to APPROVED; PO generated in system', 'Status changed to APPROVED; PO dynamically appeared in Generated Purchase Orders tab', 'Pass'],
    ['TC-SR02', 'Quantity Anomaly Override Warning', 'Verify overriding suggested quantity by >20% triggers anomaly warning popup.', 'Same as TC-SR01', '1. Change suggested qty from 20 to 100\n2. Click Approve', 'Suggested Qty: 20\nManual Qty: 100', 'Anomaly Override confirmation dialog appears requesting justification', 'Anomaly Override confirmation dialog appeared requesting justification', 'Pass'],
    ['TC-SR03', 'Override Log Saved', 'Verify supplying a justification saves the override log.', 'Anomaly dialog is open', '1. Enter override reason \n2. Click "Yes, I am sure"', 'Reason: "Demand spike expected"', 'PO is generated; Override reasoning is permanently logged', 'PO generated; Override reasoning logged in override_logs table', 'Pass'],
    ['TC-PO01', 'Cancel Pending Purchase Order', 'Verify cancelling an un-shipped PO irreversibly deletes it and reverts ML status.', 'Pending Dispatch PO exists', '1. Open Generated POs tab \n2. Click Cancel on a PO', 'PO ID: 5A0CDFB7', 'PO is deleted; original ML recommendation status reverted to CANCELLED', 'PO deleted; ML recommendation status successfully reverted to CANCELLED', 'Pass'],
    ['TC-PO02', 'Mark PO as Sent', 'Verify admin can transition PO to Sent status.', 'Pending Dispatch PO exists', '1. Open Generated POs tab \n2. Click Send', 'PO ID: 01F931F7', 'Status badge updates to Sent to Supplier', 'Status badge dynamically updated to Sent to Supplier', 'Pass'],
    
    # Short Shipment (Delivery)
    ['TC-SS01', 'Auto-fill Pending PO Details', 'Verify selecting a Pending PO auto-fills delivery form fields.', 'Sent PO exists in system', '1. Open Record Delivery tab \n2. Select PO from dropdown', 'Dropdown: PO 01F931F7', 'Order Number, Supplier, Product, and Ordered Qty fields are auto-populated', 'Fields accurately auto-populated directly from ML PO records', 'Pass'],
    ['TC-SS02', 'Record Delivery Closes PO', 'Verify saving a delivery automatically completes the linked PO.', 'System fields auto-filled from PO', '1. Enter Actual Received Qty \n2. Click Save Delivery', 'Ordered Qty: 50 \nReceived Qty: 50', 'Delivery logged; Original PO status updated to DELIVERED', 'Delivery logged; PO status automatically updated to DELIVERED in database', 'Pass'],
    
    # Smart Stock Audit (Cycle Counting)
    ['TC-IA01', 'Cycle Count Match', 'Verify matching physical count logs zero shrinkage.', 'Product catalog exists; ML stock level tracked', '1. Open Smart Stock Audit \n2. Select Product \n3. Enter exact matching physical count \n4. Click Validate', 'System Expects: 150 \nActual: 150', 'Audit Verified success message; No anomaly thrown', 'Audit Verified success message surfaced; Logged without anomaly', 'Pass'],
    ['TC-IA02', 'Shrinkage Anomaly Catch', 'Verify entering a physical count lower than ML system stock throws a Shrinkage Anomaly.', 'System expects 150 units', '1. Open Smart Stock Audit \n2. Select Product \n3. Enter 120 as physical count \n4. Click Validate', 'System Expects: 150 \nActual: 120', 'SHRINKAGE ANOMALY block generated; Requires remarks to proceed', 'SHRINKAGE ANOMALY explicitly blocked submission until damage remarks were provided', 'Pass']
]

columns = [
    'TC ID', 'Test Title', 'Description', 'Preconditions', 
    'Test Steps', 'Test Data', 'Expected Output', 'Actual Output', 'Status'
]

df = pd.DataFrame(data, columns=columns)

# Write to Excel
file_path = 'Test_Cases_Report_Stock_Replenishment.xlsx'
writer = pd.ExcelWriter(file_path, engine='openpyxl')
df.to_excel(writer, sheet_name='Stock System Test Cases', index=False)

# Formatting
workbook = writer.book
worksheet = writer.sheets['Stock System Test Cases']

# Adjust column widths
col_widths = {'A': 10, 'B': 25, 'C': 35, 'D': 25, 'E': 35, 'F': 25, 'G': 35, 'H': 35, 'I': 10}
for col, width in col_widths.items():
    worksheet.column_dimensions[col].width = width

# Enable text wrap
for row in worksheet.iter_rows(min_row=1, max_row=len(df)+1):
    for cell in row:
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        if cell.row == 1:
            cell.font = Font(bold=True)

writer.close()
print(f"Successfully generated Excel file at {file_path}")
