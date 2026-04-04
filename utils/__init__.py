import re

def validate_email(email):
    """Validate email format"""
    if not email:
        return True
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format"""
    if not phone:
        return True
    pattern = r'^(\+94|0)?7[0-9]{8}$'
    return re.match(pattern, phone) is not None

def validate_supplier_id(supplier_id):
    """Validate supplier ID format"""
    if not supplier_id:
        return True
    pattern = r'^SUP[0-9]{3}$'
    return re.match(pattern, supplier_id) is not None

def validate_product_code(product_code):
    """Validate product code format"""
    if not product_code:
        return True
    pattern = r'^[A-Z0-9]{3,10}$'
    return re.match(pattern, product_code) is not None 