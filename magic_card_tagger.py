import streamlit as st
import pandas as pd
import requests
import io
import re
import math
import os
import base64
from dotenv import load_dotenv
import json

# Use python-dotenv to load .env file
load_dotenv(dotenv_path="C:/Users/frogm/github_repos/magic-card-tagger/.env")

SCRYFALL_API = "https://api.scryfall.com/cards/named?"

SHOPIFY_COLUMNS = [
    'Handle', 'Name', 'Body (HTML)', 'Vendor', 'Product Category', 'Type', 'Tags', 'Published',
    'Option1 Name', 'Option1 Value', 'Option1 Linked To', 'Option2 Name', 'Option2 Value', 'Option2 Linked To',
    'Option3 Name', 'Option3 Value', 'Option3 Linked To', 'Variant SKU', 'Variant Grams',
    'Variant Inventory Tracker', 'Variant Inventory Qty', 'Variant Inventory Policy',
    'Variant Fulfillment Service', 'Variant Price', 'Variant Compare At Price', 'Variant Requires Shipping',
    'Variant Taxable', 'Variant Barcode', 'Image Src', 'Image Position', 'Image Alt Text', 'Gift Card',
    'SEO Title', 'SEO Description', 'Google Shopping / Google Product Category', 'Google Shopping / Gender',
    'Google Shopping / Age Group', 'Google Shopping / MPN', 'Google Shopping / Condition',
    'Google Shopping / Custom Product', 'Google Shopping / Custom Label 0', 'Google Shopping / Custom Label 1',
    'Google Shopping / Custom Label 2', 'Google Shopping / Custom Label 3', 'Google Shopping / Custom Label 4',
    'Merged Product (product.metafields.merges.product_merged)',
    'Age restrictions (product.metafields.shopify.age-restrictions)',
    'Board game features (product.metafields.shopify.board-game-features)',
    'Board game mechanics (product.metafields.shopify.board-game-mechanics)',
    'Card attributes (product.metafields.shopify.card-attributes)',
    'Color (product.metafields.shopify.color-pattern)',
    'Condition (product.metafields.shopify.condition)',
    'Event type (product.metafields.shopify.event-type)',
    'Gameplay skills (product.metafields.shopify.gameplay-skills)',
    'Rarity (product.metafields.shopify.rarity)',
    'Recommended age group (product.metafields.shopify.recommended-age-group)',
    'Theme (product.metafields.shopify.theme)',
    'Ticket additional features (product.metafields.shopify.ticket-additional-features)',
    'Ticket type (product.metafields.shopify.ticket-type)',
    'Toy/Game material (product.metafields.shopify.toy-game-material)',
    'Trading card packaging (product.metafields.shopify.trading-card-packaging)',
    'Variant Image', 'Variant Weight Unit', 'Variant Tax Code', 'Cost per item', 'Status'
]

FOREX_API = 'https://api.frankfurter.app/latest?from=USD&to=ZAR'

def get_usd_to_zar():
    response = requests.get(FOREX_API)
    try:
        data = response.json()
        return data['rates']['ZAR']
    except Exception as e:
        st.error(f"Error fetching forex rate: {e}\nResponse: {response.text}")
        return None

def fetch_card_tags(card_name, set_code=None):
    try:
        params = {'exact': card_name}
        if set_code:
            params['set'] = set_code.lower()
        response = requests.get(SCRYFALL_API, params=params)
        if response.status_code != 200:
            return None
        data = response.json()
        # Rarity
        rarity = data.get('rarity', '').capitalize()
        # Colors
        colors = data.get('colors', [])
        color_map = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'}
        if not colors:
            color_tag = 'Colour: Colorless'
        else:
            color_names = [color_map.get(c, c) for c in colors]
            color_tag = f"Colour: {', '.join(color_names)}"
        # Card types
        type_line = data.get('type_line', '')
        card_types = [t.strip() for t in type_line.split('—')[0].split() if t[0].isupper()]
        type_tag = f"Type: {' '.join(card_types)}" if card_types else ''
        rarity_tag = f"Rarity: {rarity}" if rarity else ''
        tags = ', '.join([color_tag, rarity_tag, type_tag])
        return tags
    except Exception:
        return None

def fetch_card_info(card_name, set_code=None, foil=False):
    try:
        params = {'exact': card_name}
        if set_code:
            params['set'] = set_code.lower()
        response = requests.get(SCRYFALL_API, params=params)
        if response.status_code != 200:
            return None
        data = response.json()
        # Rarity
        rarity = data.get('rarity', '').capitalize()
        # Colors
        colors = data.get('colors', [])
        color_map = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'}
        if not colors:
            color_tag = 'Colour: Colorless'
        else:
            color_names = [color_map.get(c, c) for c in colors]
            color_tag = f"Colour: {', '.join(color_names)}"
        # Card types
        type_line = data.get('type_line', '')
        card_types = [t.strip() for t in type_line.split('—')[0].split() if t[0].isupper()]
        type_tag = f"Type: {' '.join(card_types)}" if card_types else ''
        rarity_tag = f"Rarity: {rarity}" if rarity else ''
        tags = ', '.join([color_tag, rarity_tag, type_tag])
        # Price
        usd_price = None
        if foil:
            usd_price = data.get('prices', {}).get('usd_foil')
        if not usd_price:
            usd_price = data.get('prices', {}).get('usd')
        # Image URL
        image_url = ''
        if 'image_uris' in data and 'normal' in data['image_uris']:
            image_url = data['image_uris']['normal']
        elif 'card_faces' in data and isinstance(data['card_faces'], list) and 'image_uris' in data['card_faces'][0]:
            image_url = data['card_faces'][0]['image_uris'].get('normal', '')
        # Shopify fields
        info = {
            'Handle': card_name.lower().replace(' ', '-'),
            'Name': data.get('name', card_name),
            'Type': type_line,
            'Tags': tags,
            'Rarity (product.metafields.shopify.rarity)': rarity,
            'Color (product.metafields.shopify.color-pattern)': ', '.join(color_names) if colors else 'Colorless',
            'usd_price': usd_price,
            'Image Src': image_url
        }
        return info
    except Exception:
        return None

def parse_txt_to_df(txt):
    lines = txt.strip().splitlines()
    data = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # New: Match 'Quantity Card Name (SET) Number' or 'Quantity Card Name'
        m = re.match(r'^(\d+)\s+(.+?)(?:\s+\([A-Z0-9]+\)\s+\d+)?$', line)
        if m:
            qty, name = m.groups()
            data.append({'Name': name.strip(), 'Quantity': int(qty)})
            continue
        # Try formats: Quantity x Card Name, Quantity Card Name, Card Name, Card Name, Quantity
        m = re.match(r'^(\d+)\s*[xX]?\s+(.+)$', line)
        if m:
            qty, name = m.groups()
            data.append({'Name': name.strip(), 'Quantity': int(qty)})
            continue
        m = re.match(r'^(.+),\s*(\d+)$', line)
        if m:
            name, qty = m.groups()
            data.append({'Name': name.strip(), 'Quantity': int(qty)})
            continue
        # Just card name
        data.append({'Name': line, 'Quantity': 1})
    return pd.DataFrame(data)

def get_shopify_auth_headers():
    access_token = os.environ.get('SHOPIFY_ADMIN_API_ACCESS_TOKEN')
    if not access_token:
        st.error("Shopify Admin API access token not found. Please set SHOPIFY_ADMIN_API_ACCESS_TOKEN in your environment variables.")
        return None
    return {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }

def get_shopify_base_url():
    store = os.environ.get('SHOPIFY_STORE')
    if not store:
        st.error("Shopify store not found. Please set SHOPIFY_STORE in your environment variables.")
        return None
    return f"https://{store}/admin/api/2023-10"

def create_shopify_product(product_data):
    base_url = get_shopify_base_url()
    headers = get_shopify_auth_headers()
    if not base_url or not headers:
        return False, "Missing Shopify credentials."
    url = f"{base_url}/products.json"
    resp = requests.post(url, headers=headers, json={"product": product_data})
    if resp.status_code == 201:
        return True, resp.json()
    else:
        return False, resp.text

def row_to_shopify_product(row):
    # Map DataFrame row to Shopify product format
    # Set defaults for required Shopify fields
    status = row.get("Status", "active") or "active"
    fulfillment_service = row.get("Variant Fulfillment Service", "shopify") or "shopify"
    inventory_policy = row.get("Variant Inventory Policy", "continue") or "continue"
    product = {
        "title": row.get("Name", ""),
        "body_html": row.get("Body (HTML)", ""),
        "vendor": row.get("Vendor", ""),
        "product_type": row.get("Type", ""),
        "tags": row.get("Tags", ""),
        "status": status,
        "variants": [
            {
                "price": row.get("Variant Price", ""),
                "sku": row.get("Variant SKU", ""),
                "inventory_quantity": int(row.get("Variant Inventory Qty", 1) or 1),
                "inventory_management": row.get("Variant Inventory Tracker", "shopify"),
                "option1": row.get("Option1 Value", "Default Title"),
                "fulfillment_service": fulfillment_service,
                "inventory_policy": inventory_policy,
            }
        ]
    }
    # Optionally add image if present
    if row.get("Image Src"):
        product["images"] = [{"src": row["Image Src"]}]
    return product

def main():
    st.title("Magic Card Tagger")
    st.write("Upload a CSV or TXT with card names. The app will fill in the Shopify columns with Scryfall data where possible.")

    uploaded_file = st.file_uploader("Choose a CSV or TXT file", type=["csv", "txt"])
    if uploaded_file:
        usd_to_zar = get_usd_to_zar()
        if usd_to_zar:
            st.info(f"Current USD to ZAR exchange rate: 1 USD = {usd_to_zar:.2f} ZAR")
        else:
            st.warning("Could not fetch USD to ZAR exchange rate. Prices will not be converted.")
        if uploaded_file.name.lower().endswith('.txt'):
            txt = uploaded_file.read().decode('utf-8')
            df = parse_txt_to_df(txt)
        else:
            df = pd.read_csv(uploaded_file)
        # Accept 'name', 'Name', 'title', or 'Title' as the card name column
        name_col = None
        for col in ['name', 'Name', 'title', 'Title']:
            if col in df.columns:
                name_col = col
                break
        # Deckbox-style columns
        is_deckbox = all(col in df.columns for col in ['Name', 'Count', 'Edition Code'])
        if is_deckbox:
            enriched_rows = []
            for idx, row in df.iterrows():
                card_name = row['Name']
                set_code = row['Edition Code'] if pd.notnull(row['Edition Code']) else None
                foil = False
                if 'Foil' in row and str(row['Foil']).strip().lower() in ['yes', 'true', '1']:
                    foil = True
                info = fetch_card_info(card_name, set_code, foil) or {}
                enriched = {col: '' for col in SHOPIFY_COLUMNS}
                enriched.update(info)
                enriched['Name'] = card_name
                enriched['Variant Inventory Qty'] = row['Count'] if pd.notnull(row['Count']) else 1
                # Price conversion
                usd_price = info.get('usd_price')
                if usd_price and usd_to_zar:
                    try:
                        enriched['Variant Price'] = str(int(math.ceil(float(usd_price) * usd_to_zar)))
                    except Exception:
                        enriched['Variant Price'] = ''
                else:
                    enriched['Variant Price'] = ''
                # Set Shopify-required defaults
                enriched['Status'] = 'active'
                enriched['Variant Fulfillment Service'] = 'shopify'
                enriched['Variant Inventory Policy'] = 'continue'
                enriched_rows.append(enriched)
            enriched_df = pd.DataFrame(enriched_rows, columns=SHOPIFY_COLUMNS)
            output = io.StringIO()
            enriched_df.to_csv(output, index=False)
            st.download_button("Download Shopify-style tagged CSV", data=output.getvalue(), file_name="shopify_tagged_cards.csv", mime="text/csv")
            if 'enriched_df' in locals():
                st.write("---")
                if st.button("Upload to Shopify"):
                    st.info("Uploading products to Shopify...")
                    results = []
                    progress = st.progress(0)
                    for idx, row in enriched_df.iterrows():
                        product_data = row_to_shopify_product(row)
                        success, resp = create_shopify_product(product_data)
                        if success:
                            results.append(f"✅ {row.get('Name', '')} uploaded.")
                        else:
                            results.append(f"❌ {row.get('Name', '')} failed: {resp}")
                        progress.progress((idx + 1) / len(enriched_df))
                    st.success("Upload complete!")
                    st.write("Results:")
                    for r in results:
                        st.write(r)
            return
        if not name_col:
            st.error("CSV or TXT must contain a 'name', 'Name', 'title', or 'Title' column or be formatted as 'Quantity Card Name' or 'Card Name, Quantity'.")
            return
        # Check for set code column
        set_col = None
        for col in ['Edition Code', 'Set Code', 'set', 'Set']:
            if col in df.columns:
                set_col = col
                break
        # If simple CSV (just name and maybe quantity), enrich to Shopify format
        if set(df.columns).issubset({'name', 'Name', 'title', 'Title', 'quantity', 'Quantity'}):
            # Build enriched DataFrame
            enriched_rows = []
            for idx, row in df.iterrows():
                card_name = row[name_col]
                set_code = row[set_col] if set_col and set_col in row and pd.notnull(row[set_col]) else None
                foil = False
                if 'Foil' in row and str(row['Foil']).strip().lower() in ['yes', 'true', '1']:
                    foil = True
                info = fetch_card_info(card_name, set_code, foil) or {}
                enriched = {col: '' for col in SHOPIFY_COLUMNS}
                enriched.update(info)
                # Quantity mapping
                qty_col = 'quantity' if 'quantity' in df.columns else 'Quantity' if 'Quantity' in df.columns else None
                if qty_col:
                    enriched['Variant Inventory Qty'] = row[qty_col]
                # Price conversion
                usd_price = info.get('usd_price')
                if usd_price and usd_to_zar:
                    try:
                        enriched['Variant Price'] = str(int(math.ceil(float(usd_price) * usd_to_zar)))
                    except Exception:
                        enriched['Variant Price'] = ''
                else:
                    enriched['Variant Price'] = ''
                # Set Shopify-required defaults
                enriched['Status'] = 'active'
                enriched['Variant Fulfillment Service'] = 'shopify'
                enriched['Variant Inventory Policy'] = 'continue'
                enriched_rows.append(enriched)
            enriched_df = pd.DataFrame(enriched_rows, columns=SHOPIFY_COLUMNS)
            output = io.StringIO()
            enriched_df.to_csv(output, index=False)
            st.download_button("Download Shopify-style tagged CSV", data=output.getvalue(), file_name="shopify_tagged_cards.csv", mime="text/csv")
            if 'enriched_df' in locals():
                st.write("---")
                if st.button("Upload to Shopify"):
                    st.info("Uploading products to Shopify...")
                    results = []
                    progress = st.progress(0)
                    for idx, row in enriched_df.iterrows():
                        product_data = row_to_shopify_product(row)
                        success, resp = create_shopify_product(product_data)
                        if success:
                            results.append(f"✅ {row.get('Name', '')} uploaded.")
                        else:
                            results.append(f"❌ {row.get('Name', '')} failed: {resp}")
                        progress.progress((idx + 1) / len(enriched_df))
                    st.success("Upload complete!")
                    st.write("Results:")
                    for r in results:
                        st.write(r)
        else:
            # Use 'Tags' column if it exists, otherwise create it
            tag_col = 'Tags'
            if tag_col not in df.columns:
                df[tag_col] = ''
            progress = st.progress(0)
            for idx, row in df.iterrows():
                set_code = row[set_col] if set_col and set_col in row and pd.notnull(row[set_col]) else None
                foil = False
                if 'Foil' in row and str(row['Foil']).strip().lower() in ['yes', 'true', '1']:
                    foil = True
                tags = fetch_card_tags(row[name_col], set_code)
                if tags:
                    df.at[idx, tag_col] = tags
                progress.progress((idx + 1) / len(df))
            st.success("Tags populated!")
            output = io.StringIO()
            df.to_csv(output, index=False)
            st.download_button("Download tagged CSV", data=output.getvalue(), file_name="tagged_cards.csv", mime="text/csv")

    print("STORE:", os.environ.get("SHOPIFY_STORE"))
    print("TOKEN:", os.environ.get("SHOPIFY_ADMIN_API_ACCESS_TOKEN"))

if __name__ == "__main__":
    main()
