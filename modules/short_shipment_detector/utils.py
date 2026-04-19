# utils.py
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# ============================================
# VALIDATION FUNCTIONS
# ============================================

def validate_email(email):
    """
    Validate email address format
    Returns: (is_valid, error_message)
    """
    if not email or email.strip() == "":
        return True, None  # Email is optional
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(pattern, email):
        return True, None
    else:
        return False, " Invalid email format. Example: name@company.com"


def validate_phone(phone):
    """
    Validate phone number format
    - Must be 10 digits after removing dashes and spaces
    - Supports Sri Lankan format: 077-1234567, 0771234567, +94771234567
    Returns: (is_valid, error_message, formatted_phone)
    """
    if not phone or phone.strip() == "":
        return True, None, phone  # Phone is optional
    
    # Remove spaces and dashes for validation
    cleaned = re.sub(r'[\s\-]', '', phone)
    
    # Check if it's a valid Sri Lankan number with country code
    if cleaned.startswith('+94') or cleaned.startswith('94'):
        digits_only = cleaned.replace('+', '')
        if len(digits_only) == 11 and digits_only[2:].isdigit():
            # Format as +94XXXXXXXXX
            formatted = f"+94 {digits_only[2:5]}-{digits_only[5:8]}-{digits_only[8:]}"
            return True, None, formatted
        else:
            return False, " Invalid phone number. Must be 10 digits after country code.", phone
    
    # Check if it's a 10-digit local number
    elif len(cleaned) == 10 and cleaned.isdigit():
        # Format as 077-1234567
        formatted = f"{cleaned[:3]}-{cleaned[3:]}"
        return True, None, formatted
    
    # Check if it's a 9-digit number (missing leading 0)
    elif len(cleaned) == 9 and cleaned.isdigit():
        # Add leading 0 and format
        formatted = f"0{cleaned[:2]}-{cleaned[2:]}"
        return True, None, formatted
    
    else:
        # Show appropriate error message
        if len(cleaned) < 10:
            return False, f" Phone number too short. Need 10 digits (got {len(cleaned)})", phone
        elif len(cleaned) > 11:
            return False, f"Phone number too long. Maximum 10 digits (got {len(cleaned)})", phone
        else:
            return False, " Invalid phone number. Example: 077-1234567 or 0771234567", phone

def validate_supplier_id(supplier_id, existing_ids=None):
    """
    Validate supplier ID format
    Returns: (is_valid, error_message)
    """
    if not supplier_id or not supplier_id.strip():
        return False, " Supplier ID is required"
    
    if not re.match(r'^[A-Za-z0-9\-]{3,20}$', supplier_id):
        return False, " Supplier ID should contain only letters, numbers, and hyphens (3-20 characters)"
    
    if existing_ids and supplier_id in existing_ids:
        return False, f" Supplier ID '{supplier_id}' already exists"
    
    return True, None


def validate_product_code(product_code, existing_codes=None):
    """
    Validate product code format
    Returns: (is_valid, error_message)
    """
    if not product_code or not product_code.strip():
        return False, " Product Code is required"
    
    if not re.match(r'^[A-Za-z0-9\-]{3,20}$', product_code):
        return False, " Product Code should contain only letters, numbers, and hyphens (3-20 characters)"
    
    if existing_codes and product_code in existing_codes:
        return False, f" Product Code '{product_code}' already exists"
    
    return True, None


# ============================================
# FORMATTING FUNCTIONS
# ============================================

def format_currency(amount):
    """Format number as currency"""
    return f"LKR {amount:,.2f}"


def format_percentage(value):
    """Format as percentage"""
    return f"{value:.1f}%"


def get_status_color(status):
    """Return color code for status"""
    colors = {
        ' Accurate': 'green',
        ' Short Shipped': 'orange',
        ' Over Delivered': 'blue'
    }
    return colors.get(status, 'gray')


# ============================================
# CHART FUNCTIONS
# ============================================

def create_discrepancy_chart(df):
    """Create a bar chart of discrepancies"""
    if df.empty:
        return None
        
    fig = px.bar(
        df,
        x='delivery_date',
        y='discrepancy_quantity',
        color='status',
        title='Shipment Discrepancies Over Time',
        color_discrete_map={
            ' Accurate': 'green',
            'Short Shipped': 'red',
            ' Over Delivered': 'blue'
        }
    )
    return fig