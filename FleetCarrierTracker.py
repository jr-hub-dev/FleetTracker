import os
import json
import time
import requests
import threading
import pandas as pd
from flask import Flask, request
from tabulate import tabulate

# === CONFIGURATION ===
CLIENT_ID = 'YOUR_CLIENT_ID'  # 🔑 À remplacer
CLIENT_SECRET = 'YOUR_CLIENT_SECRET'  # 🔑 À remplacer
REDIRECT_URI = 'http://localhost:8000/callback'
API_BASE_URL = 'https://companion.orerve.net'
CSV_FILE = 'materials_needed.csv'
TOKENS_FILE = 'tokens.json'

# === GLOBAL ===
app = Flask(__name__)
auth_code = None

# === TOKEN STORAGE ===
def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        return None
    with open(TOKENS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_tokens(tokens):
    with open(TOKENS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tokens, f, indent=4)
    print("[INFO] Tokens sauvegardés.")

# === AUTH ===
def get_authorization_url():
    return (
        f"https://auth.frontierstore.net/oauth/authorize?"
        f"client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=capi"
    )

def exchange_code_for_token(code):
    url = "https://auth.frontierstore.net/token"
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    response = requests.post(url, data=data)
    return response.json()

def refresh_access_token(refresh_token):
    url = "https://auth.frontierstore.net/token"
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    response = requests.post(url, data=data)
    return response.json()

# === FLASK ROUTE ===
@app.route('/callback')
def callback():
    global auth_code
    auth_code = request.args.get('code')
    return "Authorization code received! You can close this window."

# === DATA ===
def load_materials_needed():
    df = pd.read_csv(CSV_FILE, sep=';', encoding='utf-8')
    return {row['Materiau'].strip().upper(): row['Quantite_Demandee'] for idx, row in df.iterrows()}

def fetch_fleet_carrier_status(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(f"{API_BASE_URL}/v4/profile", headers=headers)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        print("[WARN] Token expiré ou invalide.")
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

# === MAIN FLOW ===
def main_flow():
    tokens = load_tokens()

    if tokens:
        print("[INFO] Tokens existants trouvés. Tentative d'utilisation...")
    else:
        print(f"[INFO] Visit this URL to authorize: {get_authorization_url()}")
        # Start Flask in background to capture code
        threading.Thread(target=lambda: app.run(port=8000)).start()

        # Wait for auth code
        while not auth_code:
            time.sleep(1)

        print("[INFO] Exchanging code for tokens...")
        tokens = exchange_code_for_token(auth_code)
        if 'access_token' not in tokens:
            print("[ERROR] Échec de récupération du token.")
            exit(1)
        save_tokens(tokens)

    access_token = tokens.get('access_token')
    refresh_token_value = tokens.get('refresh_token')

    materials_needed = load_materials_needed()

    while True:
        data = fetch_fleet_carrier_status(access_token)

        if data and 'fleet_carrier' in data:
            carrier_inventory = data['fleet_carrier'].get('cargo', {}).get('inventory', [])
            display_progress(carrier_inventory, materials_needed)
        elif data is None:
            # Token peut être expiré, tentative de refresh
            print("[INFO] Tentative de rafraîchissement du token...")
            refreshed = refresh_access_token(refresh_token_value)
            if 'access_token' in refreshed:
                access_token = refreshed['access_token']
                refresh_token_value = refreshed['refresh_token']
                save_tokens(refreshed)
                print("[INFO] Token rafraîchi avec succès.")
            else:
                print("[ERROR] Rafraîchissement échoué. Veuillez réauthentifier.")
                break

        time.sleep(60)  # Actualise toutes les 60 secondes

if __name__ == "__main__":
    main_flow()
