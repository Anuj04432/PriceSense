import os
from dotenv import load_dotenv, find_dotenv

print("Current working directory:", os.getcwd())

dotenv_path = find_dotenv(usecwd=True)
print("find_dotenv() found:", repr(dotenv_path))

loaded = load_dotenv(dotenv_path)
print("load_dotenv() success:", loaded)

key = os.getenv("SERPAPI_KEY")
print("SERPAPI_KEY value:", repr(key))

print("\n--- Raw .env file bytes ---")
try:
    with open(".env", "rb") as f:
        print(f.read())
except FileNotFoundError as e:
    print("FileNotFoundError:", e)