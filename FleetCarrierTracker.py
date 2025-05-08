import requests
import json
import time
import pandas as pd
from tabulate import tabulate

# === CONFIGURATION ===
CLIENT_ID = '76f2a525-a260-44b6-86a7-63a793381966'
CLIENT_SECRET = 'YOUR_CLIENT_SECRET'
REDIRECT_URI = 'https://jr-hub-dev.github.io/FleetTracker/'
AUTH_URL = 'https://auth.frontierstore.net/oauth/authorize'
TOKEN_URL = 'https://auth.frontierstore.net/token'
API_BASE_URL = 'https://companion.orerve.net'
CSV_FILE = 'materials_needed.csv'
TOKENS_FILE = 'tokens.json'

def get_authorization_url():
    return (
        f"{AUTH_URL}?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=capi"
    )

def exchange_code_for_token(code):
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    response = requests.post(TOKEN_URL, data=data)
    return response.json()

def refresh_access_token(refresh_token):
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    response = requests.post(TOKEN_URL, data=data)
    return response.json()

def save_tokens(tokens):
    with open(TOKENS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tokens, f, indent=4)
    print("[INFO] Tokens saved.")

def load_tokens():
    try:
        with open(TOKENS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def load_materials_needed():
    df = pd.read_csv(CSV_FILE, sep=';', encoding='utf-8')
    return {row['Materiau'].strip().upper(): row['Quantite_Demandee'] for idx, row in df.iterrows()}

def fetch_fleet_carrier_status(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(f"{API_BASE_URL}/v4/profile", headers=headers)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        print("[WARN] Token expired or invalid.")
    else:
        print(f"[ERROR] API Error: {response.status_code} {response.text}")
    return None

def display_progress(inventory, materials_needed):
    tracked_cargo = {item['name'].strip().upper(): item['quantity'] for item in inventory}
    table = []
    for mat_needed, qty_needed in materials_needed.items():
        qty_in_cargo = tracked_cargo.get(mat_needed, 0)
        reste = max(qty_needed - qty_in_cargo, 0)
        status = '✅ COMPLETED' if reste == 0 else ''
        table.append([mat_needed, qty_needed, qty_in_cargo, reste, status])
    print("\n[=== Fleet Carrier Cargo Tracking ===]")
    print(tabulate(table, headers=['Material', 'Required', 'In Cargo', 'Remaining', 'Status'], tablefmt='grid'))
    print("[=== End of Report ===]\n")

def main():
    tokens = load_tokens()
    if not tokens:
        print("[INFO] Please authorize this app by visiting the following URL:")
        print(get_authorization_url())
        code = input("[INPUT] After authorizing, paste the ?code= value here: ").strip()
        tokens = exchange_code_for_token(code)
        if 'access_token' not in tokens:
            print("[ERROR] Failed to obtain tokens.")
            return
        save_tokens(tokens)

    access_token = tokens['access_token']
    refresh_token_value = tokens['refresh_token']
    materials_needed = load_materials_needed()

    while True:
        data = fetch_fleet_carrier_status(access_token)
        if data and 'fleet_carrier' in data:
            carrier_inventory = data['fleet_carrier'].get('cargo', {}).get('inventory', [])
            display_progress(carrier_inventory, materials_needed)
        elif data is None:
            print("[INFO] Attempting token refresh...")
            refreshed = refresh_access_token(refresh_token_value)
            if 'access_token' in refreshed:
                access_token = refreshed['access_token']
                refresh_token_value = refreshed['refresh_token']
                save_tokens(refreshed)
                print("[INFO] Token refreshed successfully.")
            else:
                print("[ERROR] Token refresh failed. Please re-authorize.")
                tokens = None
                break
        time.sleep(60)  # Refresh every minute

if __name__ == "__main__":
    main()
