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
import time

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
    'Variant Image', 'Variant Weight Unit', 'Variant Tax Code', 'Cost per item', 'Status',
    'Set Name', 'Card Number', 'Rarity'
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
            color_tags = ['Colour: Colorless']
        else:
            color_tags = [f"Colour: {color_map.get(c, c)}" for c in colors]
        # Card types
        type_line = data.get('type_line', '')
        card_types = [t.strip() for t in type_line.split('—')[0].split() if t[0].isupper()]
        type_tag = f"Type: {' '.join(card_types)}" if card_types else ''
        rarity_tag = f"Rarity: {rarity}" if rarity else ''
        tags = ', '.join(color_tags + [rarity_tag, type_tag])
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
            color_tags = ['Colour: Colorless']
        else:
            color_tags = [f"Colour: {color_map.get(c, c)}" for c in colors]
        # Card types
        type_line = data.get('type_line', '')
        card_types = [t.strip() for t in type_line.split('—')[0].split() if t[0].isupper()]
        type_tag = f"Type: {' '.join(card_types)}" if card_types else ''
        rarity_tag = f"Rarity: {rarity}" if rarity else ''
        tags = ', '.join(color_tags + [rarity_tag, type_tag])
        # Price
        usd_price = None
        if foil:
            usd_price = data.get('prices', {}).get('usd_foil')
        if not usd_price:
            usd_price = data.get('prices', {}).get('usd')
        # Image URL
        image_url = ''
        if 'image_uris' in data and 'png' in data['image_uris']:
            image_url = data['image_uris']['png']
        elif 'card_faces' in data and isinstance(data['card_faces'], list) and 'image_uris' in data['card_faces'][0] and 'png' in data['card_faces'][0]['image_uris']:
            image_url = data['card_faces'][0]['image_uris'].get('png', '')
        # Shopify fields
        info = {
            'Handle': card_name.lower().replace(' ', '-'),
            'Name': data.get('name', card_name),
            'Type': type_line,
            'Tags': tags,
            'Rarity (product.metafields.shopify.rarity)': rarity,
            'Color (product.metafields.shopify.color-pattern)': ', '.join(color_tags),
            'usd_price': usd_price,
            'Image Src': image_url,
            'Variant Image': image_url
        }
        # Set Scryfall info columns
        if info:
            info['Set Name'] = data.get('set_name', '')
            info['Card Number'] = data.get('collector_number', '')
            info['Rarity'] = rarity
            # Add rarity to Tags if not already present
            rarity_tag = f"Rarity: {rarity}"
            if 'Tags' in info and rarity_tag not in info['Tags']:
                info['Tags'] = f"{info['Tags']}, {rarity_tag}" if info['Tags'] else rarity_tag
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

def get_location_id():
    # Cache location_id after first fetch
    if not hasattr(get_location_id, 'location_id'):
        base_url = get_shopify_base_url()
        headers = get_shopify_auth_headers()
        if not base_url or not headers:
            return None
        url = f"{base_url}/locations.json"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            locations = resp.json().get('locations', [])
            if locations:
                get_location_id.location_id = locations[0]['id']
                return get_location_id.location_id
        return None
    return get_location_id.location_id

def set_inventory_level(inventory_item_id, available):
    location_id = get_location_id()
    if not location_id:
        st.warning('Could not fetch Shopify location_id, inventory not updated.')
        return False, 'No location_id'
    base_url = get_shopify_base_url()
    headers = get_shopify_auth_headers()
    url = f"{base_url}/inventory_levels/set.json"
    payload = {
        "location_id": location_id,
        "inventory_item_id": inventory_item_id,
        "available": available
    }
    st.write("Shopify InventoryLevel API Payload:", payload)
    resp = requests.post(url, headers=headers, json=payload)
    return resp.status_code in (200, 201), resp.text

def get_product_images(product_id):
    base_url = get_shopify_base_url()
    headers = get_shopify_auth_headers()
    url = f"{base_url}/products/{product_id}/images.json"
    resp = requests.get(url, headers=headers)
    with st.expander("Shopify Get Product Images Response"):
        st.code(resp.text)
    if resp.status_code == 200:
        return resp.json().get('images', [])
    return []

def add_image_to_product(product_id, image_url):
    base_url = get_shopify_base_url()
    headers = get_shopify_auth_headers()
    url = f"{base_url}/products/{product_id}/images.json"
    payload = {"image": {"src": image_url}}
    with st.expander("Shopify Add Image Payload"):
        st.code(json.dumps(payload, indent=2))
    resp = requests.post(url, headers=headers, json=payload)
    with st.expander("Shopify Add Image Response"):
        st.code(resp.text)
    image_id = None
    if resp.status_code in (200, 201):
        image = resp.json().get('image', {})
        image_id = image.get('id')
    # Poll for image to appear in product images (max 5 tries, 2s each)
    for attempt in range(5):
        images = get_product_images(product_id)
        with st.expander(f"Poll Attempt {attempt+1} - Product Images"):
            st.code(json.dumps(images, indent=2))
        found_id = None
        for img in images:
            if img.get('src') == image_url and img.get('id'):
                found_id = img['id']
                break
        with st.expander(f"Poll Attempt {attempt+1} - Found image_id"):
            st.write(found_id)
        if found_id:
            image_id = found_id
            break
        time.sleep(2)
    return image_id

def assign_image_to_variant(variant_id, image_id):
    base_url = get_shopify_base_url()
    headers = get_shopify_auth_headers()
    url = f"{base_url}/variants/{variant_id}.json"
    payload = {"variant": {"id": variant_id, "image_id": image_id}}
    with st.expander("Shopify Assign Image to Variant Payload"):
        st.code(json.dumps(payload, indent=2))
    resp = requests.put(url, headers=headers, json=payload)
    with st.expander("Shopify Assign Image to Variant Response"):
        st.code(resp.text)
    return resp.status_code in (200, 201)

def create_shopify_product(product_data):
    base_url = get_shopify_base_url()
    headers = get_shopify_auth_headers()
    if not base_url or not headers:
        return False, "Missing Shopify credentials."
    url = f"{base_url}/products.json"
    with st.expander("Shopify Product Creation Payload"):
        st.code(json.dumps({"product": product_data}, indent=2))
    resp = requests.post(url, headers=headers, json={"product": product_data})
    with st.expander("Shopify Product Creation Response"):
        st.code(resp.text)
    if resp.status_code == 201:
        # Assign images to variants after product creation
        product = resp.json().get('product', {})
        product_id = product.get('id')
        variants = product.get('variants', [])
        images = product.get('images', [])
        for variant in variants:
            # Find the matching variant_data by option1 value
            for vdata in product_data.get('variants', []):
                if vdata.get('option1') == variant.get('option1'):
                    image_url = vdata.get('image', {}).get('src') if 'image' in vdata else None
                    if image_url:
                        image_id = add_image_to_product(product_id, image_url)
                        if image_id:
                            assign_image_to_variant(variant['id'], image_id)
        return True, resp.json()
    else:
        return False, resp.text

def row_to_shopify_product(row):
    # Map DataFrame row to Shopify product format
    # Set defaults for required Shopify fields
    status = row.get("Status", "active") or "active"
    fulfillment_service = row.get("Variant Fulfillment Service", "manual") or "manual"
    inventory_policy = row.get("Variant Inventory Policy", "deny") or "deny"
    variant = {
        "price": row.get("Variant Price", ""),
        "sku": row.get("Variant SKU", ""),
        "inventory_quantity": int(row.get("Variant Inventory Qty", 1) or 1),
        "inventory_management": row.get("Variant Inventory Tracker", "shopify"),
        "option1": row.get("Option1 Value", "Default Title"),
        "fulfillment_service": fulfillment_service,
        "inventory_policy": inventory_policy,
    }
    # Add unique image to variant if present
    if row.get("Image Src"):
        variant["image"] = {"src": row["Image Src"]}
    product = {
        "title": row.get("Name", ""),
        "body_html": row.get("Body (HTML)", ""),
        "vendor": row.get("Vendor", ""),
        "product_type": row.get("Type", ""),
        "tags": row.get("Tags", ""),
        "status": status,
        "variants": [variant]
    }
    # Optionally add product-level image if present and not already set for variant
    if row.get("Image Src") and "image" not in variant:
        product["images"] = [{"src": row["Image Src"]}]
    return product

def get_product_variants_by_handle(handle):
    base_url = get_shopify_base_url()
    headers = get_shopify_auth_headers()
    if not base_url or not headers:
        return None, None
    url = f"{base_url}/products.json?handle={handle}"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        products = resp.json().get('products', [])
        if products:
            product = products[0]
            variants = {v['option1']: v for v in product.get('variants', [])}
            return product, variants
    return None, None

def update_shopify_variant(product_id, variant_id, price, quantity):
    base_url = get_shopify_base_url()
    headers = get_shopify_auth_headers()
    if not base_url or not headers:
        return False, "Missing Shopify credentials."
    url = f"{base_url}/variants/{variant_id}.json"
    data = {"variant": {"id": variant_id, "price": price, "inventory_quantity": quantity, "inventory_management": "shopify"}}
    with st.expander("Shopify Variant Update Payload"):
        st.code(json.dumps(data, indent=2))
    resp = requests.put(url, headers=headers, json=data)
    with st.expander("Shopify Variant Update Response"):
        st.code(resp.text)
    # Also update inventory using InventoryLevel API
    if resp.status_code == 200:
        variant = resp.json().get('variant', {})
        inventory_item_id = variant.get('inventory_item_id')
        if inventory_item_id:
            set_inventory_level(inventory_item_id, quantity)
        return True, resp.json()
    else:
        return False, resp.text

def add_shopify_variant(product_id, variant_data):
    base_url = get_shopify_base_url()
    headers = get_shopify_auth_headers()
    if not base_url or not headers:
        return False, "Missing Shopify credentials."
    url = f"{base_url}/products/{product_id}/variants.json"
    with st.expander("Shopify Add Variant Payload"):
        st.code(json.dumps({"variant": variant_data}, indent=2))
    resp = requests.post(url, headers=headers, json={"variant": variant_data})
    with st.expander("Shopify Add Variant Response"):
        st.code(resp.text)
    # Also update inventory using InventoryLevel API
    if resp.status_code == 201:
        variant = resp.json().get('variant', {})
        inventory_item_id = variant.get('inventory_item_id')
        quantity = variant_data.get('inventory_quantity', 0)
        if inventory_item_id:
            set_inventory_level(inventory_item_id, quantity)
        # Assign image to variant if Image Src is present
        image_url = variant_data.get('image', {}).get('src') if 'image' in variant_data else None
        if image_url:
            image_id = add_image_to_product(product_id, image_url)
            if image_id:
                assign_image_to_variant(variant['id'], image_id)
        return True, resp.json()
    else:
        return False, resp.text

def build_option1_value(data, foil=False, fallback_card_number=None, fallback_set_name=None):
    collector_number = data.get('collector_number', '') or fallback_card_number or ''
    set_name = data.get('set_name', '') or fallback_set_name or ''
    frame_effects = data.get('frame_effects', []) or []
    option1_value = f"{set_name} #{collector_number}".strip()
    if foil:
        option1_value += " (Foil)"
    if 'boosterfun' in frame_effects:
        option1_value += " [Boosterfun]"
    return option1_value

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
                enriched['Variant Fulfillment Service'] = 'manual'
                enriched['Variant Inventory Policy'] = 'deny'
                # Set user-specified defaults
                enriched['Vendor'] = 'Top Deck'
                enriched['Product Category'] = 'Uncategorized'
                enriched['Published'] = 'TRUE'
                enriched['Option1 Name'] = 'Version'
                enriched['Variant Grams'] = 2
                enriched['Variant Inventory Tracker'] = 'shopify'
                enriched['Variant Requires Shipping'] = 'TRUE'
                enriched['Variant Taxable'] = 'TRUE'
                enriched['Gift Card'] = 'FALSE'
                enriched['Variant Weight Unit'] = 'g'
                # Set Option1 Value using Scryfall data or fallback to input Card Number
                fallback_card_number = row.get('Card Number', '') if 'Card Number' in row else None
                fallback_set_name = row.get('Edition', '') if 'Edition' in row else None
                if info:
                    enriched['Option1 Value'] = build_option1_value(info, foil, fallback_card_number, fallback_set_name)
                else:
                    enriched['Option1 Value'] = build_option1_value({}, foil, fallback_card_number, fallback_set_name)
                # Set Scryfall info columns, fallback to Edition for Set Name
                if info:
                    enriched['Set Name'] = info.get('set_name', '') or row.get('Edition', '')
                    enriched['Card Number'] = info.get('collector_number', '') or fallback_card_number
                    enriched['Rarity'] = info.get('rarity', '')
                    # Add rarity to Tags if not already present
                    rarity_tag = f"Rarity: {info.get('rarity', '').capitalize()}"
                    if 'Tags' in enriched and rarity_tag not in enriched['Tags']:
                        enriched['Tags'] = f"{enriched['Tags']}, {rarity_tag}" if enriched['Tags'] else rarity_tag
                # Set Variant Image to match Image Src
                enriched['Variant Image'] = enriched.get('Image Src', '')
                enriched_rows.append(enriched)
            enriched_df = pd.DataFrame(enriched_rows, columns=SHOPIFY_COLUMNS)
            # Show preview of Option1 Value
            st.write('Preview of Option1 Value (first 10 rows):')
            st.dataframe(enriched_df[['Name', 'Set Name', 'Card Number', 'Option1 Value']].head(10))
            # Show warning if any Option1 Value is missing
            if enriched_df['Option1 Value'].isnull().any() or (enriched_df['Option1 Value'] == '').any():
                st.warning('Some rows are missing Option1 Value. Please check your input or Scryfall data.')
            output = io.StringIO()
            enriched_df.to_csv(output, index=False)
            st.download_button("Download Shopify-style tagged CSV", data=output.getvalue(), file_name="shopify_tagged_cards.csv", mime="text/csv")
            if 'enriched_df' in locals():
                st.write("---")
                if st.button("Upload to Shopify"):
                    st.info("Uploading products to Shopify...")
                    results = []
                    progress = st.progress(0)
                    for handle, group in enriched_df.groupby('Handle'):
                        product, existing_variants = get_product_variants_by_handle(handle)
                        if not product:
                            # Product does not exist, create with all variants
                            first_row = group.iloc[0]
                            product_data = row_to_shopify_product(first_row)
                            # Add all variants
                            product_data['variants'] = []
                            for _, row in group.iterrows():
                                variant = row_to_shopify_product(row)['variants'][0]
                                product_data['variants'].append(variant)
                            success, resp = create_shopify_product(product_data)
                            if success:
                                results.append(f"✅ {handle} created with {len(group)} variants.")
                            else:
                                results.append(f"❌ {handle} create failed: {resp}")
                        else:
                            # Product exists, update or add variants
                            product_id = product['id']
                            for _, row in group.iterrows():
                                variant = row_to_shopify_product(row)['variants'][0]
                                option1_value = variant['option1']
                                if option1_value in existing_variants:
                                    # Update existing variant
                                    variant_id = existing_variants[option1_value]['id']
                                    price = variant.get('price', existing_variants[option1_value]['price'])
                                    quantity = variant.get('inventory_quantity', existing_variants[option1_value]['inventory_quantity'])
                                    success, resp = update_shopify_variant(product_id, variant_id, price, quantity)
                                    if success:
                                        results.append(f"📝 {handle} - {option1_value} updated.")
                                    else:
                                        results.append(f"❌ {handle} - {option1_value} update failed: {resp}")
                                else:
                                    # Add new variant
                                    success, resp = add_shopify_variant(product_id, variant)
                                    if success:
                                        results.append(f"➕ {handle} - {option1_value} added.")
                                    else:
                                        results.append(f"❌ {handle} - {option1_value} add failed: {resp}")
                        progress.progress((list(enriched_df['Handle']).index(handle) + 1) / len(enriched_df['Handle'].unique()))
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
                enriched['Variant Fulfillment Service'] = 'manual'
                enriched['Variant Inventory Policy'] = 'deny'
                # Set user-specified defaults
                enriched['Vendor'] = 'Top Deck'
                enriched['Product Category'] = 'Uncategorized'
                enriched['Published'] = 'TRUE'
                enriched['Option1 Name'] = 'Version'
                enriched['Variant Grams'] = 2
                enriched['Variant Inventory Tracker'] = 'shopify'
                enriched['Variant Requires Shipping'] = 'TRUE'
                enriched['Variant Taxable'] = 'TRUE'
                enriched['Gift Card'] = 'FALSE'
                enriched['Variant Weight Unit'] = 'g'
                # Set Option1 Value using Scryfall data or fallback to input Card Number
                fallback_card_number = row.get('Card Number', '') if 'Card Number' in row else None
                fallback_set_name = row.get('Edition', '') if 'Edition' in row else None
                if info:
                    enriched['Option1 Value'] = build_option1_value(info, foil, fallback_card_number, fallback_set_name)
                else:
                    enriched['Option1 Value'] = build_option1_value({}, foil, fallback_card_number, fallback_set_name)
                # Set Scryfall info columns, fallback to Edition for Set Name
                if info:
                    enriched['Set Name'] = info.get('set_name', '') or row.get('Edition', '')
                    enriched['Card Number'] = info.get('collector_number', '') or fallback_card_number
                    enriched['Rarity'] = info.get('rarity', '')
                    # Add rarity to Tags if not already present
                    rarity_tag = f"Rarity: {info.get('rarity', '').capitalize()}"
                    if 'Tags' in enriched and rarity_tag not in enriched['Tags']:
                        enriched['Tags'] = f"{enriched['Tags']}, {rarity_tag}" if enriched['Tags'] else rarity_tag
                else:
                    enriched['Set Name'] = row.get('Edition', '')
                    enriched['Card Number'] = fallback_card_number
                # Set Variant Image to match Image Src
                enriched['Variant Image'] = enriched.get('Image Src', '')
                enriched_rows.append(enriched)
            enriched_df = pd.DataFrame(enriched_rows, columns=SHOPIFY_COLUMNS)
            # Show preview of Option1 Value
            st.write('Preview of Option1 Value (first 10 rows):')
            st.dataframe(enriched_df[['Name', 'Set Name', 'Card Number', 'Option1 Value']].head(10))
            # Show warning if any Option1 Value is missing
            if enriched_df['Option1 Value'].isnull().any() or (enriched_df['Option1 Value'] == '').any():
                st.warning('Some rows are missing Option1 Value. Please check your input or Scryfall data.')
            output = io.StringIO()
            enriched_df.to_csv(output, index=False)
            st.download_button("Download Shopify-style tagged CSV", data=output.getvalue(), file_name="shopify_tagged_cards.csv", mime="text/csv")
            if 'enriched_df' in locals():
                st.write("---")
                if st.button("Upload to Shopify"):
                    st.info("Uploading products to Shopify...")
                    results = []
                    progress = st.progress(0)
                    for handle, group in enriched_df.groupby('Handle'):
                        product, existing_variants = get_product_variants_by_handle(handle)
                        if not product:
                            # Product does not exist, create with all variants
                            first_row = group.iloc[0]
                            product_data = row_to_shopify_product(first_row)
                            # Add all variants
                            product_data['variants'] = []
                            for _, row in group.iterrows():
                                variant = row_to_shopify_product(row)['variants'][0]
                                product_data['variants'].append(variant)
                            success, resp = create_shopify_product(product_data)
                            if success:
                                results.append(f"✅ {handle} created with {len(group)} variants.")
                            else:
                                results.append(f"❌ {handle} create failed: {resp}")
                        else:
                            # Product exists, update or add variants
                            product_id = product['id']
                            for _, row in group.iterrows():
                                variant = row_to_shopify_product(row)['variants'][0]
                                option1_value = variant['option1']
                                if option1_value in existing_variants:
                                    # Update existing variant
                                    variant_id = existing_variants[option1_value]['id']
                                    price = variant.get('price', existing_variants[option1_value]['price'])
                                    quantity = variant.get('inventory_quantity', existing_variants[option1_value]['inventory_quantity'])
                                    success, resp = update_shopify_variant(product_id, variant_id, price, quantity)
                                    if success:
                                        results.append(f"📝 {handle} - {option1_value} updated.")
                                    else:
                                        results.append(f"❌ {handle} - {option1_value} update failed: {resp}")
                                else:
                                    # Add new variant
                                    success, resp = add_shopify_variant(product_id, variant)
                                    if success:
                                        results.append(f"➕ {handle} - {option1_value} added.")
                                    else:
                                        results.append(f"❌ {handle} - {option1_value} add failed: {resp}")
                        progress.progress((list(enriched_df['Handle']).index(handle) + 1) / len(enriched_df['Handle'].unique()))
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
