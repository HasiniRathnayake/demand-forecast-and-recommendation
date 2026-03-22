# test_env.py
import os
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
database_url = os.getenv("DATABASE_URL")

print(f"SUPABASE_URL: {supabase_url}")
print(f"SUPABASE_KEY: {supabase_key[:20] if supabase_key else None}...")
print(f"DATABASE_URL: {database_url[:30] if database_url else None}...")