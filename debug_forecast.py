#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from config.settings import SUPABASE_URL, SUPABASE_KEY
import requests, json

h = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}

# Check what dates are available
print('=== FORECAST DATES ===')
r = requests.get(f'{SUPABASE_URL}/rest/v1/demand_forecasts?select=forecast_date&order=forecast_date.desc&limit=100', headers=h)
if r.status_code == 200:
    dates = sorted(set(row.get('forecast_date') for row in r.json() if row.get('forecast_date')), reverse=True)
    print(f'Available dates ({len(dates)} unique): {dates[:10]}')
else:
    print(f'Error fetching dates: {r.status_code}')

# Check sample forecast row with details
print('\n=== SAMPLE FORECAST ROWS ===')
r = requests.get(f'{SUPABASE_URL}/rest/v1/demand_forecasts?select=*&order=forecast_date.desc&limit=5', headers=h)
if r.status_code == 200:
    for row in r.json():
        print(f"Code: {row.get('product_code')} | Date: {row.get('forecast_date')} | Demand: {row.get('predicted_demand')} | Model: {row.get('model_version')}")

# Check product catalog
print('\n=== PRODUCT CATALOG ===')
r = requests.get(f'{SUPABASE_URL}/rest/v1/product_catalog?select=product_code&limit=50', headers=h)
if r.status_code == 200:
    codes = [row.get('product_code') for row in r.json()]
    print(f'Catalog products: {len(codes)}')
    print(f'Sample: {codes[:5]}')

# Check if forecast products match catalog
print('\n=== OVERLAP CHECK ===')
r_forecast = requests.get(f'{SUPABASE_URL}/rest/v1/demand_forecasts?select=product_code&order=product_code.asc&limit=1000', headers=h)
r_catalog = requests.get(f'{SUPABASE_URL}/rest/v1/product_catalog?select=product_code', headers=h)

if r_forecast.status_code == 200 and r_catalog.status_code == 200:
    forecast_codes = set(row.get('product_code') for row in r_forecast.json())
    catalog_codes = set(row.get('product_code') for row in r_catalog.json())
    overlap = forecast_codes & catalog_codes
    print(f'Forecast codes: {len(forecast_codes)}')
    print(f'Catalog codes: {len(catalog_codes)}')
    print(f'Overlap: {len(overlap)} ({len(overlap)/len(catalog_codes)*100:.1f}%)')
    if len(overlap) < 10:
        print(f'Overlapping codes: {list(overlap)[:10]}')
