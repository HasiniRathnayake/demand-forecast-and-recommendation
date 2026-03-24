import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print(f"URL: {url}")
print(f"KEY: {key[:20]}...")

try:
    client = create_client(url, key)
    result = client.table("users").select("username, role").limit(5).execute()
    print(f"\n✅ Connected! Users found: {len(result.data)}")
    for u in result.data:
        print(f"  - {u['username']} ({u['role']})")
except Exception as e:
    print(f"\n❌ Connection failed: {e}")