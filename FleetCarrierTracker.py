import requests
import csv
import time
from tabulate import tabulate

# === CONFIG ===
CLIENT_ID = '76f2a525-a260-44b6-86a7-63a793381966'
CLIENT_SECRET = '84a3c017-b5ce-4abd-9138-7ee3acea35ad'
REDIRECT_URI = 'https://jr-hub-dev.github.io/FleetTracker/'
TOKEN_URL = 'https://auth.frontierstore.net/token'
AUTH_URL = 'https://auth.frontierstore.net/auth'
API_URL = 'https://companion.orerve.net/profile'  # Frontier Companion API

# === STEP 1: GET CODE ===
print("[INFO] Visit the following URL in your browser to authorize:")
print(f"{AUTH_URL}?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=capi")
authorization_code = input("[INPUT] Paste the ?code= value here: ")

# === STEP 2: EXCHANGE CODE FOR TOKEN ===
data = {
    'grant_type': 'authorization_code',
    'code': authorization_code,
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'redirect_uri': REDIRECT_URI,
}

response = requests.post(TOKEN_URL, data=data)
if response.status_code != 200:
    print("[ERROR] Failed to get token:", response.text)
    exit()

tokens = response.json()
access_token = tokens['access_token']
print("[SUCCESS] Access token obtained.")

# === LOAD MATERIALS NEEDED ===
materials_needed = {}
with open('materials_needed.csv', newline='', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    next(reader, None)  # skip header if present
    for row in reader:
        material, quantity = row
        materials_needed[material.strip().lower()] = int(quantity.strip())

# === POLL LOOP ===
headers = {'Authorization': f'Bearer {access_token}'}

while True:
    resp = requests.get(API_URL, headers=headers)
    if resp.status_code != 200:
        print("[ERROR] Failed to fetch carrier data:", resp.text)
        time.sleep(10)
        continue

    data = resp.json()

    # Find fleet carrier cargo (this assumes you're owner)
    try:
        cargo_list = data['fleetCarrier']['cargo']
    except KeyError:
        print("[ERROR] Could not find fleet carrier cargo in API response.")
        time.sleep(10)
        continue

    # Build comparison table
    report = []
    for mat, needed_qty in materials_needed.items():
        in_cargo = 0
        for item in cargo_list:
            name = item.get('name', '').strip().lower()
            qty = item.get('qty', 0)
            if mat in name:
                in_cargo = qty
                break
        remaining = max(needed_qty - in_cargo, 0)
        report.append([mat, needed_qty, in_cargo, remaining])

    print("\n[=== Fleet Carrier Cargo Progress ===]")
    print(tabulate(report, headers=['Material', 'Needed', 'In Carrier', 'Remaining'], tablefmt='grid'))
    print("[INFO] Updating again in 60 seconds...\n")
    time.sleep(60)
