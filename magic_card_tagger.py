"""
Magic Card Tagger - Streamlit App

This app enriches Magic card lists with Scryfall data and prepares Shopify-compatible CSVs, with optional direct upload to Shopify via API.
"""

# 1. Imports and Constants
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
from bs4 import BeautifulSoup

# Use python-dotenv to load .env file
load_dotenv(dotenv_path="C:/Users/frogm/github_repos/magic-card-tagger-1/.env")

SCRYFALL_API = "https://api.scryfall.com/cards/named?"
FOREX_API = 'https://api.frankfurter.app/latest?from=USD&to=ZAR'

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

# 2. Utility Functions

def get_usd_to_zar():
    """Fetches the current USD to ZAR exchange rate from the Frankfurter API."""
    response = requests.get(FOREX_API)
    try:
        data = response.json()
        return data['rates']['ZAR']
    except Exception as e:
        st.error(f"Error fetching forex rate: {e}\nResponse: {response.text}")
        return None

def parse_txt_to_df(txt):
    """Parses a plain text list of cards into a pandas DataFrame, supporting various input formats."""
    lines = txt.strip().splitlines()
    data = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^(\d+)\s+(.+?)(?:\s+\([A-Z0-9]+\)\s+\d+)?$', line)
        if m:
            qty, name = m.groups()
            data.append({'Name': name.strip(), 'Quantity': int(qty)})
            continue
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
        data.append({'Name': line, 'Quantity': 1})
    return pd.DataFrame(data)

def calculate_price_with_vat(usd_price, usd_to_zar):
    """Converts USD price to ZAR, adds VAT, and applies price floors (5, 8, 10)."""
    if usd_price is None or usd_to_zar is None:
        return ''
    try:
        price_zar = float(usd_price) * usd_to_zar * 1.15  # Add 15% VAT
        # Apply price floors
        if price_zar < 5:
            price_zar = 5
        elif price_zar < 8:
            price_zar = 8
        elif price_zar < 10:
            price_zar = 10
        return f"{price_zar:.2f}"
    except (ValueError, TypeError):
        return ''

def fetch_scryfall_sets():
    """Fetches all Magic sets from Scryfall and returns a list of dicts with set name and code."""
    url = "https://api.scryfall.com/sets"
    response = requests.get(url)
    if response.status_code != 200:
        return []
    data = response.json()
    sets = [s for s in data.get('data', []) if s.get('set_type') in ['expansion', 'core', 'masters', 'draft_innovation', 'commander', 'starter', 'funny', 'duel_deck', 'box', 'from_the_vault', 'spellbook', 'premium_deck', 'archenemy', 'planechase', 'vanguard', 'treasure_chest', 'alchemy', 'remaster']]
    # Sort by release date descending
    sets.sort(key=lambda s: s.get('released_at', ''), reverse=True)
    return sets

def fetch_all_regular_cards_for_set(set_code):
    """Fetches all regular (non-token, non-promo, non-digital) cards for a given set code from Scryfall."""
    cards = []
    url = f"https://api.scryfall.com/cards/search?q=e%3A{set_code}+game%3Apaper+-is%3Atoken+-promo"
    while url:
        resp = requests.get(url)
        if resp.status_code != 200:
            break
        data = resp.json()
        for card in data.get('data', []):
            # Exclude digital-only, tokens, promos, and cards with layout 'token' or 'art_series'
            if card.get('digital') or card.get('layout') in ['token', 'art_series']:
                continue
            cards.append(card)
        url = data.get('next_page')
    return cards

# 3. Scryfall Functions

def fetch_card_tags(card_name, set_code=None):
    """Retrieves card tags (color, rarity, type) from Scryfall for a given card name and set code."""
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
    """Retrieves detailed card info from Scryfall (name, type, tags, rarity, color, price, image) for a given card name, set code, and foil status."""
    try:
        # Use fuzzy search instead of exact match for better results
        params = {'fuzzy': card_name}
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
        prices = data.get('prices', {})
        
        if foil:
            usd_price = prices.get('usd_foil')
            if not usd_price:
                usd_price = prices.get('usd')  # Fallback to regular price for foil
        else:
            usd_price = prices.get('usd')
            if not usd_price:
                usd_price = prices.get('usd_foil')  # Fallback to foil price for regular
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

def build_option1_value(data, foil=False, fallback_card_number=None, fallback_set_name=None):
    """Constructs the Option1 Value for a variant using Scryfall data and input fallbacks. Now returns only the set name to match existing Shopify data."""
    set_name = data.get('set_name', '') or fallback_set_name or ''
    frame_effects = data.get('frame_effects', []) or []
    option1_value = set_name.strip()
    if foil:
        option1_value += " (Foil)"
    if 'boosterfun' in frame_effects:
        option1_value += " [Boosterfun]"
    return option1_value

# 4. Shopify API Functions

def get_shopify_auth_headers():
    """Returns the headers required for authenticating with the Shopify Admin API."""
    access_token = os.environ.get('SHOPIFY_ADMIN_API_ACCESS_TOKEN')
    if not access_token:
        st.error("Shopify Admin API access token not found. Please set SHOPIFY_ADMIN_API_ACCESS_TOKEN in your environment variables.")
        return None
    return {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }

def get_shopify_base_url():
    """Constructs the base URL for the Shopify Admin API using the store environment variable."""
    store = os.environ.get('SHOPIFY_STORE')
    if not store:
        st.error("Shopify store not found. Please set SHOPIFY_STORE in your environment variables.")
        return None
    return f"https://{store}/admin/api/2023-10"

def get_location_id():
    """Retrieves and caches the Shopify store's location ID for inventory management."""
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
    """Sets the inventory level for a variant at the store's location using the InventoryLevel API."""
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
    """Fetches all images attached to a Shopify product."""
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
    """Uploads an image to a Shopify product and polls until the image is available."""
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
    """Assigns an uploaded image to a specific variant in Shopify."""
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
    """Creates a new product in Shopify using the provided product data via the Shopify API."""
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
    """Maps a DataFrame row to the Shopify product/variant format for API upload."""
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
    """Fetches a product and its variants from Shopify by product handle."""
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
    """Updates a variant's price in Shopify, and sets inventory using the InventoryLevel API. Sends a full variant payload."""
    base_url = get_shopify_base_url()
    headers = get_shopify_auth_headers()
    if not base_url or not headers:
        return False, "Missing Shopify credentials."
    # Fetch the existing variant data
    get_url = f"{base_url}/variants/{variant_id}.json"
    try:
        get_resp = requests.get(get_url, headers=headers)
        if get_resp.status_code != 200:
            st.error(f"[DEBUG] Failed to fetch existing variant data: {get_resp.text}")
            return False, get_resp.text
        existing_variant = get_resp.json().get('variant', {})
        st.write(f"[DEBUG] Existing variant data: {json.dumps(existing_variant, indent=2)}")
        # Update only the fields we want to change
        existing_variant['price'] = price
        # Remove fields that Shopify does not allow in update
        for field in ['admin_graphql_api_id', 'created_at', 'updated_at', 'old_inventory_quantity', 'image_id', 'inventory_quantity', 'inventory_item_id', 'product_id']:
            if field in existing_variant:
                del existing_variant[field]
        data = {"variant": existing_variant}
        st.write(f"[DEBUG] Full payload to Shopify: {json.dumps(data, indent=2)}")
        url = f"{base_url}/variants/{variant_id}.json"
        with st.expander("Shopify Variant Update Payload"):
            st.code(json.dumps(data, indent=2))
        resp = requests.put(url, headers=headers, json=data)
        st.write(f"[DEBUG] Shopify update response status: {resp.status_code}")
        with st.expander("Shopify Variant Update Response"):
            st.code(resp.text)
        # After updating price, update inventory using InventoryLevel API
        if resp.status_code == 200:
            variant = resp.json().get('variant', {})
            inventory_item_id = variant.get('inventory_item_id')
            if inventory_item_id:
                set_inventory_level(inventory_item_id, quantity)
            return True, resp.json()
        else:
            return False, resp.text
    except Exception as e:
        st.error(f"Exception during Shopify variant update: {e}")
        return False, str(e)

def add_shopify_variant(product_id, variant_data):
    """Adds a new variant to an existing Shopify product and assigns inventory and image."""
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

# 5. Data Enrichment Functions
# (If you have any additional enrichment helpers, add here)

# 6. Streamlit UI Functions
# (For preview, warnings, debug output, etc. If needed, add here)

def adjust_shopify_csv_with_counts(count_df, shopify_df):
    """Adjust Shopify CSV inventory quantities based on count data."""
    adjusted_df = shopify_df.copy()
    matches_found = 0
    


    # Find the correct column name for card number
    card_number_col = None
    for col in ['collector_number', 'Card Number', 'card number', 'card number ', 'Card Number', 'card_number', 'CardNumber', 'Number', 'number']:
        if col in count_df.columns:
            card_number_col = col
            break
    
    if card_number_col is None:
        print(f"Available columns in count sheet: {list(count_df.columns)}")
        raise ValueError("Could not find collector number column. Available columns: " + str(list(count_df.columns)))

    print(f"Using column '{card_number_col}' for collector numbers")

    for _, count_row in count_df.iterrows():
        try:
            # Handle potential NaN values in card_name
            card_name_raw = count_row['card_name']
            if pd.isna(card_name_raw):
                print(f"Skipping row with NaN card_name")
                continue
            card_name = str(card_name_raw)
            
            # Convert card_name to handle format
            import re
            handle = card_name.lower()
            handle = re.sub(r'[^\w\s-]', '', handle)  # Remove special characters except spaces and hyphens
            handle = re.sub(r'\s+', '-', handle)  # Replace spaces with hyphens
            handle = re.sub(r'-+', '-', handle)  # Replace multiple hyphens with single hyphen
            handle = handle.strip('-')  # Remove leading/trailing hyphens
            
            # Handle potential NaN values in collector number
            card_number_raw = count_row[card_number_col]
            if pd.isna(card_number_raw):
                print(f"Skipping {card_name} - NaN collector number")
                continue
            card_number = str(card_number_raw).strip()
            
            # Debug the raw values
            raw_regular = count_row['inventory_quantity']
            raw_foil = count_row['Foil inventory_quantity']
            print(f"\nRaw values for {card_name}:")
            print(f"  Card name: '{card_name}'")
            print(f"  Converted handle: '{handle}'")
            print(f"  Raw regular: '{raw_regular}' (type: {type(raw_regular)})")
            print(f"  Raw foil: '{raw_foil}' (type: {type(raw_foil)})")
            
            # Handle NaN values in counts
            if pd.isna(raw_regular) or str(raw_regular).strip() == '':
                regular_count = 0
            else:
                try:
                    regular_count = int(float(raw_regular))
                except (ValueError, TypeError):
                    regular_count = 0
                    
            if pd.isna(raw_foil) or str(raw_foil).strip() == '':
                foil_count = 0
            else:
                try:
                    foil_count = int(float(raw_foil))
                except (ValueError, TypeError):
                    foil_count = 0
            
            print(f"  Converted regular: {regular_count} (type: {type(regular_count)})")
            print(f"  Converted foil: {foil_count} (type: {type(foil_count)})")

            if regular_count == 0 and foil_count == 0:
                continue  # Skip if no inventory to add

            # Match by Title and extract collector number from Option1 Value
            # Option1 Value format: "Edge of Eternities {R} #1" - extract the number after #
            def extract_collector_number(option1_value):
                if pd.isna(option1_value):
                    return None
                import re
                match = re.search(r'#(\d+)', str(option1_value))
                return match.group(1) if match else None

            # Find matching cards in Shopify CSV
            matching_cards = adjusted_df[adjusted_df['Handle'] == handle]
            
            print(f"\nLooking for: {card_name} #{card_number}")
            print(f"Looking for Handle: {handle}")
            print(f"Found {len(matching_cards)} cards with handle '{handle}'")
            print(f"Regular count: {regular_count}, Foil count: {foil_count}")
            
            # Check ALL variants for the correct collector number
            found_regular = False
            found_foil = False
            if len(matching_cards) > 0:
                print("Checking all variants:")
                for idx, card in matching_cards.iterrows():
                    option1_value = card['Option1 Value']
                    extracted_number = extract_collector_number(option1_value)
                    is_foil = '(Foil)' in option1_value
                    print(f"  - Variant: Option1 Value='{option1_value}', extracted number='{extracted_number}', is_foil={is_foil}")
                    
                    # Check if this variant has the correct collector number
                    if extracted_number == card_number:
                        if is_foil:
                            found_foil = True
                            print(f"    ✅ Found foil variant with collector number #{card_number}")
                        else:
                            found_regular = True
                            print(f"    ✅ Found regular variant with collector number #{card_number}")
            
            # Update regular variant
            if regular_count > 0:
                regular_mask = (
                    (adjusted_df['Handle'] == handle) & 
                    (adjusted_df['Option1 Value'].apply(extract_collector_number) == card_number) &
                    (~adjusted_df['Option1 Value'].str.contains(r'\(Foil\)', na=False))
                )
                
                if regular_mask.any():
                    current_inventory = adjusted_df.loc[regular_mask, 'Variant Inventory Qty'].values
                    print(f"  Regular - Current inventory values: {current_inventory}")
                    
                    # Add count sheet quantity to existing inventory
                    for idx in adjusted_df[regular_mask].index:
                        existing_qty = adjusted_df.loc[idx, 'Variant Inventory Qty']
                        if pd.isna(existing_qty) or existing_qty == '':
                            existing_qty = 0
                        else:
                            try:
                                existing_qty = int(float(existing_qty))
                            except (ValueError, TypeError):
                                existing_qty = 0
                        
                        new_qty = existing_qty + regular_count
                        adjusted_df.loc[idx, 'Variant Inventory Qty'] = new_qty
                        print(f"  Regular - Added {regular_count} to existing {existing_qty} = {new_qty}")
                        

                    
                    updated_inventory = adjusted_df.loc[regular_mask, 'Variant Inventory Qty'].values
                    print(f"  Regular - Updated inventory values: {updated_inventory}")
                    matches_found += 1
                    print(f"✅ Updated regular {card_name} #{card_number} with quantity {regular_count}")
                else:
                    print(f"❌ No regular variant found for {card_name} #{card_number}")
            
            # Update or create foil variant
            if foil_count > 0:
                print(f"  Processing foil count: {foil_count} (type: {type(foil_count)})")
                
                # Debug: Show all variants for this handle
                handle_variants = adjusted_df[adjusted_df['Handle'] == handle]
                print(f"  All variants for handle '{handle}':")
                for idx, variant in handle_variants.iterrows():
                    option1_value = variant.get('Option1 Value', '')
                    extracted_num = extract_collector_number(option1_value)
                    is_foil = '(Foil)' in option1_value
                    print(f"    - Variant: Option1 Value='{option1_value}', extracted number='{extracted_num}', is_foil={is_foil}")
                    print(f"      Raw Option1 Value: '{option1_value}'")
                    print(f"      Contains 'Foil': {'Foil' in option1_value}")
                    print(f"      Contains '(Foil)': {'(Foil)' in option1_value}")
                    print(f"      Contains '[Boosterfun]': {'[Boosterfun]' in option1_value}")
                    if is_foil:
                        print(f"      ✅ This is a foil variant!")
                    else:
                        print(f"      ❌ This is NOT a foil variant")
                
                # Simple foil detection for format: Edge of Eternities: Stellar Sights {M} #1 (Foil) [Boosterfun]
                foil_mask = (
                    (adjusted_df['Handle'] == handle) & 
                    (adjusted_df['Option1 Value'].apply(extract_collector_number) == card_number) &
                    (adjusted_df['Option1 Value'].str.contains(r'\(Foil\)', na=False))
                )
                
                print(f"  Foil mask found {foil_mask.sum()} matching variants")
                if foil_mask.any():
                    # Update existing foil variant
                    current_inventory = adjusted_df.loc[foil_mask, 'Variant Inventory Qty'].values
                    print(f"  Foil - Current inventory values: {current_inventory}")
                    
                    # Add count sheet quantity to existing inventory
                    for idx in adjusted_df[foil_mask].index:
                        existing_qty = adjusted_df.loc[idx, 'Variant Inventory Qty']
                        if pd.isna(existing_qty) or existing_qty == '':
                            existing_qty = 0
                        else:
                            try:
                                existing_qty = int(float(existing_qty))
                            except (ValueError, TypeError):
                                existing_qty = 0
                        
                        new_qty = existing_qty + foil_count
                        adjusted_df.loc[idx, 'Variant Inventory Qty'] = new_qty
                        print(f"  Foil - Added {foil_count} to existing {existing_qty} = {new_qty}")
                    
                    updated_inventory = adjusted_df.loc[foil_mask, 'Variant Inventory Qty'].values
                    print(f"  Foil - Updated inventory values: {updated_inventory}")
                    matches_found += 1
                    print(f"✅ Updated foil {card_name} #{card_number} with quantity {foil_count}")
                else:
                    print(f"❌ No existing foil variant found for {card_name} #{card_number} - foil count {foil_count} will not be added")
                    
        except Exception as e:
            print(f"Error processing row for card: {card_name if 'card_name' in locals() else 'unknown'}")
            print(f"Error details: {str(e)}")
            print(f"Row data: {count_row.to_dict()}")
            continue

    print(f"\nTotal matches found: {matches_found}")
    return adjusted_df

# Deckbox Collection Value Calculator Functions
USD_TO_ZAR = 18  # Conversion rate
STORE_OFFER_PERCENT = 0.4
STORE_CREDIT_PERCENT = 0.5

def debug_show_html(html, tables, rows):
    with st.expander("Debug: Raw HTML and Table Info"):
        st.write(f"Found {len(tables)} tables on the page.")
        if tables:
            st.code(str(tables[0])[:2000], language='html')
        st.write(f"First 3 rows:")
        for row in rows[:3]:
            st.write([c.get_text(strip=True) for c in row.find_all('td')])

@st.cache_data(show_spinner=False)
def get_total_pages(url):
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        page_info = soup.find(string=re.compile(r'Page \\d+ of \\d+'))
        if page_info:
            match = re.search(r'Page \d+ of (\d+)', page_info)
            if match:
                return int(match.group(1))
        last_page = 1
        for a in soup.find_all('a', href=True):
            if '?p=' in a['href']:
                try:
                    page_num = int(a['href'].split('=')[-1])
                    if page_num > last_page:
                        last_page = page_num
                except Exception:
                    continue
        return last_page
    except Exception as e:
        return 1

@st.cache_data(show_spinner=False)
def scrape_deckbox_page(url, debug=False):
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    tables = soup.find_all('table')
    table = None
    for t in tables:
        headers = t.find_all('th')
        if len(headers) >= 5:
            table = t
            break
    data = []
    if not table:
        if debug:
            debug_show_html(soup.prettify(), tables, [])
        return data
    rows = table.find_all('tr')[1:]
    if debug:
        debug_show_html(soup.prettify(), tables, rows)
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 5:
            continue
        qty = cols[0].get_text(strip=True)
        name = cols[1].get_text(strip=True)
        price_text = cols[3].get_text(strip=True)
        price_match = re.search(r'\$(\d+\.\d+)', price_text)
        price = float(price_match.group(1)) if price_match else 0.0
        try:
            qty = int(qty)
        except Exception:
            qty = 1
        data.append({
            'Name': name,
            'Quantity': qty,
            'Price': price,
            'Total': qty * price
        })
    return data

def scrape_entire_collection(base_url):
    base_url = re.sub(r'\?p=\d+$', '', base_url)
    total_pages = get_total_pages(base_url)
    all_cards = []
    progress = st.progress(0, text="Scraping Deckbox pages...")
    for page in range(1, total_pages + 1):
        if page == 1:
            page_url = base_url
        else:
            page_url = f"{base_url}?p={page}"
        try:
            cards = scrape_deckbox_page(page_url, debug=(page==1))
            all_cards.extend(cards)
        except Exception as e:
            st.warning(f"Failed to scrape page {page}: {e}")
        progress.progress(page / total_pages, text=f"Scraping page {page} of {total_pages}")
        time.sleep(0.2)
    progress.empty()
    return all_cards

def aggregate_cards(cards):
    df = pd.DataFrame(cards)
    if df.empty:
        return df, 0.0
    grouped = df.groupby(['Name', 'Price'], as_index=False).agg({'Quantity': 'sum', 'Total': 'sum'})
    total_value = grouped['Total'].sum()
    grouped = grouped.sort_values(by='Total', ascending=False)
    return grouped, total_value

# Moxfield Deck Value Calculator Functions
def extract_moxfield_deck_id(url):
    """Extracts the deck ID from a Moxfield URL."""
    import re
    # Handle various Moxfield URL formats
    patterns = [
        r'moxfield\.com/decks/([a-zA-Z0-9_-]+)',
        r'moxfield\.com/deck/([a-zA-Z0-9_-]+)',
        r'decks/([a-zA-Z0-9_-]+)',
        r'deck/([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def fetch_moxfield_deck(deck_id):
    """Fetches deck data from Moxfield API."""
    try:
        # Try the correct API endpoint with more realistic headers
        url = f"https://api.moxfield.com/v2/decks/all/{deck_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.moxfield.com/',
            'Origin': 'https://www.moxfield.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # If the API fails, try web scraping as fallback
        try:
            st.info("API access failed, trying web scraping...")
            return scrape_moxfield_deck_web(deck_id)
        except Exception as scrape_error:
            st.error(f"Error fetching Moxfield deck: {e}")
            st.error(f"Web scraping also failed: {scrape_error}")
            return None

def scrape_moxfield_deck_web(deck_id):
    """Scrapes deck data from Moxfield web page as fallback."""
    try:
        url = f"https://www.moxfield.com/decks/{deck_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.moxfield.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for the deck data in the page's JavaScript
        scripts = soup.find_all('script')
        deck_data = None
        
        for script in scripts:
            if script.string and 'window.__INITIAL_STATE__' in script.string:
                # Extract the deck data from the JavaScript
                import re
                import json
                
                # Find the INITIAL_STATE__ object
                match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', script.string, re.DOTALL)
                if match:
                    try:
                        initial_state = json.loads(match.group(1))
                        # Navigate to the deck data
                        if 'decks' in initial_state and deck_id in initial_state['decks']:
                            deck_data = initial_state['decks'][deck_id]
                            break
                    except json.JSONDecodeError:
                        continue
        
        if not deck_data:
            # Fallback: try to extract from a different script pattern
            for script in scripts:
                if script.string and 'deck' in script.string.lower():
                    # Look for deck data in other script tags
                    try:
                        # Try to find deck data in various formats
                        if '"mainboard"' in script.string and '"sideboard"' in script.string:
                            # Extract the deck object
                            deck_match = re.search(r'({[^}]*"mainboard"[^}]*})', script.string)
                            if deck_match:
                                deck_data = json.loads(deck_match.group(1))
                                break
                    except:
                        continue
        
        return deck_data
        
    except Exception as e:
        # If JavaScript extraction fails, try direct HTML parsing
        try:
            st.info("JavaScript extraction failed, trying direct HTML parsing...")
            return scrape_moxfield_deck_html(deck_id)
        except Exception as html_error:
            raise Exception(f"Web scraping failed: {e}. HTML parsing also failed: {html_error}")

def scrape_moxfield_deck_html(deck_id):
    """Scrapes deck data directly from HTML as final fallback."""
    try:
        url = f"https://www.moxfield.com/decks/{deck_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.moxfield.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for card elements in the HTML
        cards = []
        
        # Try to find card elements by common selectors
        card_selectors = [
            '[data-testid="card-name"]',
            '.card-name',
            '.card-title',
            '[class*="card"]',
            '[class*="Card"]'
        ]
        
        for selector in card_selectors:
            card_elements = soup.select(selector)
            if card_elements:
                for element in card_elements:
                    card_name = element.get_text(strip=True)
                    if card_name and len(card_name) > 2:  # Basic validation
                        cards.append({
                            'Name': card_name,
                            'Quantity': 1,
                            'Section': 'Mainboard'
                        })
                break
        
        # If no cards found with selectors, try to extract from text
        if not cards:
            # Look for patterns like "2x Card Name" or "Card Name (2)"
            import re
            text_content = soup.get_text()
            card_patterns = [
                r'(\d+)x\s+([^\n\r]+)',  # 2x Card Name
                r'([^\n\r]+)\s+\((\d+)\)',  # Card Name (2)
                r'(\d+)\s+([^\n\r]+)',  # 2 Card Name
            ]
            
            for pattern in card_patterns:
                matches = re.findall(pattern, text_content)
                for match in matches:
                    if len(match) == 2:
                        quantity = int(match[0])
                        card_name = match[1].strip()
                        if card_name and len(card_name) > 2:
                            cards.append({
                                'Name': card_name,
                                'Quantity': quantity,
                                'Section': 'Mainboard'
                            })
        
        # Create a mock deck data structure
        deck_data = {
            'name': f'Deck {deck_id}',
            'mainboard': {},
            'sideboard': {},
            'commanders': {}
        }
        
        # Add cards to mainboard
        for i, card in enumerate(cards):
            deck_data['mainboard'][f'card_{i}'] = {
                'card': {'name': card['Name']},
                'quantity': card['Quantity']
            }
        
        return deck_data
        
    except Exception as e:
        raise Exception(f"HTML parsing failed: {e}")

def parse_moxfield_deck(deck_data):
    """Parses Moxfield deck data and extracts card information."""
    cards = []
    
    try:
        # Handle different data structures from API vs web scraping
        if isinstance(deck_data, dict):
            # Extract cards from different sections
            mainboard = deck_data.get('mainboard', {})
            sideboard = deck_data.get('sideboard', {})
            commanders = deck_data.get('commanders', {})
            
            # Process mainboard
            if isinstance(mainboard, dict):
                for card_id, card_info in mainboard.items():
                    if isinstance(card_info, dict):
                        card_name = card_info.get('card', {}).get('name', 'Unknown Card')
                        quantity = card_info.get('quantity', 1)
                        cards.append({
                            'Name': card_name,
                            'Quantity': quantity,
                            'Section': 'Mainboard'
                        })
            
            # Process sideboard
            if isinstance(sideboard, dict):
                for card_id, card_info in sideboard.items():
                    if isinstance(card_info, dict):
                        card_name = card_info.get('card', {}).get('name', 'Unknown Card')
                        quantity = card_info.get('quantity', 1)
                        cards.append({
                            'Name': card_name,
                            'Quantity': quantity,
                            'Section': 'Sideboard'
                        })
            
            # Process commanders
            if isinstance(commanders, dict):
                for card_id, card_info in commanders.items():
                    if isinstance(card_info, dict):
                        card_name = card_info.get('card', {}).get('name', 'Unknown Card')
                        quantity = card_info.get('quantity', 1)
                        cards.append({
                            'Name': card_name,
                            'Quantity': quantity,
                            'Section': 'Commander'
                        })
        
        # If no cards found, try alternative parsing
        if not cards:
            st.warning("Could not parse deck data in expected format. Trying alternative parsing...")
            # Try to extract cards from any available data
            for key, value in deck_data.items():
                if isinstance(value, dict) and 'cards' in str(value).lower():
                    # Look for card data in any structure
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, dict) and 'name' in sub_value:
                            card_name = sub_value.get('name', 'Unknown Card')
                            quantity = sub_value.get('quantity', 1)
                            cards.append({
                                'Name': card_name,
                                'Quantity': quantity,
                                'Section': 'Mainboard'
                            })
            
    except Exception as e:
        st.error(f"Error parsing Moxfield deck data: {e}")
        st.write("Debug - Deck data structure:", deck_data)
        return []
    
    return cards

def get_card_prices_from_scryfall(cards):
    """Fetches prices for cards from Scryfall API."""
    priced_cards = []
    
    for card in cards:
        card_name = card['Name']
        quantity = card['Quantity']
        
        try:
            # Fetch card info from Scryfall
            card_info = fetch_card_info(card_name)
            if card_info and 'usd_price' in card_info:
                price = float(card_info['usd_price']) if card_info['usd_price'] else 0.0
            else:
                price = 0.0
            
            priced_cards.append({
                'Name': card_name,
                'Quantity': quantity,
                'Price': price,
                'Total': quantity * price,
                'Section': card.get('Section', 'Mainboard')
            })
            
            # Rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            st.warning(f"Could not fetch price for {card_name}: {e}")
            priced_cards.append({
                'Name': card_name,
                'Quantity': quantity,
                'Price': 0.0,
                'Total': 0.0,
                'Section': card.get('Section', 'Mainboard')
            })
    
    return priced_cards

def parse_manual_deck_list(deck_text):
    """Parses manually entered deck list text."""
    cards = []
    lines = deck_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Try different patterns
        patterns = [
            r'(\d+)x\s+(.+)',  # 2x Lightning Bolt
            r'(.+)\s+\((\d+)\)',  # Lightning Bolt (2)
            r'(\d+)\s+(.+)',  # 2 Lightning Bolt
            r'(.+)',  # Just card name (quantity = 1)
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                if len(match.groups()) == 2:
                    quantity = int(match.group(1))
                    card_name = match.group(2).strip()
                else:
                    quantity = 1
                    card_name = match.group(1).strip()
                
                if card_name and len(card_name) > 2:
                    cards.append({
                        'Name': card_name,
                        'Quantity': quantity,
                        'Section': 'Mainboard'
                    })
                break
    
    return cards

# 7. Main App Logic
def main():
    st.set_page_config(page_title="Magic Card Tagger", layout="wide")
    st.markdown("""
        <style>
        .block-container {padding-top: 2rem;}
        .stButton>button {width: 100%;}
        .stDownloadButton>button {width: 100%;}
        </style>
    """, unsafe_allow_html=True)

    # --- Homepage with logo and navigation ---
    import os
    logo_path = os.path.join(os.path.dirname(__file__), 'logo.png')
    # Center the logo
    if os.path.exists(logo_path):
        st.markdown("""
        <div style="display: flex; justify-content: center; align-items: center;">
            <img src="data:image/png;base64,{}" width="200" style="display: block;">
        </div>
        """.format(base64.b64encode(open(logo_path, 'rb').read()).decode()), unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="display: flex; justify-content: center; align-items: center;">
        """, unsafe_allow_html=True)
        st.info('To display the logo, download it from [this link](https://drive.google.com/file/d/1zTe-hfoDw8s3GPTOWnyv76RFyF6mpN_c/view?usp=sharing) and save as logo.png in the app folder.')
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Center the title and subtitle
    st.markdown("<h1 style='text-align: center;'>Card Inventory Manager</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Count converter, price updater and more.</p>", unsafe_allow_html=True)
    
    # Homepage with buttons
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Home"
    
    if st.session_state.current_page == "Home":
        st.header("Choose a Feature")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📤 Upload & Enrich Card List", use_container_width=True):
                st.session_state.current_page = "Upload & Enrich Card List"
                st.rerun()
            
            if st.button("📥 Download Set as Shopify CSV", use_container_width=True):
                st.session_state.current_page = "Download Set as Shopify CSV"
                st.rerun()
            
            if st.button("🎴 Deckbox Collection Value Calculator", use_container_width=True):
                st.session_state.current_page = "Deckbox Collection Value Calculator"
                st.rerun()
        
        with col2:
            if st.button("📊 Top Deck Count Sheet to Shopify CSV", use_container_width=True):
                st.session_state.current_page = "Top Deck Count Sheet to Shopify CSV with Prices"
                st.rerun()
            
            if st.button("💰 Price Check & Update", use_container_width=True):
                st.session_state.current_page = "Price Check & Update"
                st.rerun()
    
    # Navigation logic
    page = st.session_state.current_page

    if page == "Upload & Enrich Card List":
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🏠 Back to Home"):
                st.session_state.current_page = "Home"
                st.rerun()
        with col2:
            st.header("Upload & Enrich Card List")
        st.markdown("""
        Upload a CSV or TXT with card names. The app will fill in the Shopify columns with Scryfall data where possible.
        """)
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
                    usd_price = info.get('usd_price')
                    enriched['Variant Price'] = calculate_price_with_vat(usd_price, usd_to_zar)
                    enriched['Status'] = 'draft'
                    enriched['Variant Fulfillment Service'] = 'manual'
                    enriched['Variant Inventory Policy'] = 'deny'
                    enriched['Vendor'] = 'Top Deck'
                    enriched['Product Category'] = 'Gaming Cards'
                    enriched['Published'] = 'TRUE'
                    enriched['Option1 Name'] = 'Version'
                    enriched['Variant Grams'] = 2
                    enriched['Variant Inventory Tracker'] = 'shopify'
                    enriched['Variant Requires Shipping'] = 'TRUE'
                    enriched['Variant Taxable'] = 'TRUE'
                    enriched['Gift Card'] = 'FALSE'
                    enriched['Variant Weight Unit'] = 'g'
                    fallback_card_number = row.get('Card Number', '') if 'Card Number' in row else None
                    fallback_set_name = row.get('Edition', '') if 'Edition' in row else None
                    if info:
                        enriched['Option1 Value'] = build_option1_value(info, foil, fallback_card_number, fallback_set_name)
                    else:
                        enriched['Option1 Value'] = build_option1_value({}, foil, fallback_card_number, fallback_set_name)
                    if info:
                        enriched['Set Name'] = info.get('set_name', '') or row.get('Edition', '')
                        enriched['Card Number'] = info.get('collector_number', '') or fallback_card_number
                        enriched['Rarity'] = info.get('rarity', '')
                        rarity_tag = f"Rarity: {info.get('rarity', '').capitalize()}"
                        if 'Tags' in enriched and rarity_tag not in enriched['Tags']:
                            enriched['Tags'] = f"{enriched['Tags']}, {rarity_tag}" if enriched['Tags'] else rarity_tag
                    enriched['Variant Image'] = enriched.get('Image Src', '')
                    enriched_rows.append(enriched)
                enriched_df = pd.DataFrame(enriched_rows, columns=SHOPIFY_COLUMNS)
                st.subheader('Preview of Option1 Value (first 10 rows):')
                st.dataframe(enriched_df[['Name', 'Set Name', 'Card Number', 'Option1 Value']].head(10), use_container_width=True)
                if enriched_df['Option1 Value'].isnull().any() or (enriched_df['Option1 Value'] == '').any():
                    st.warning('Some rows are missing Option1 Value. Please check your input or Scryfall data.')
                output = io.StringIO()
                enriched_df.to_csv(output, index=False)
                st.download_button("Download Shopify-style tagged CSV", data=output.getvalue(), file_name="shopify_tagged_cards.csv", mime="text/csv")
                st.markdown("---")
                with st.expander("Upload to Shopify (Advanced)"):
                    if st.button("Upload to Shopify"):
                        st.info("Uploading products to Shopify...")
                        results = []
                        progress = st.progress(0)
                        for handle, group in enriched_df.groupby('Handle'):
                            product, existing_variants = get_product_variants_by_handle(handle)
                            normalized_existing_variants = {}
                            if existing_variants:
                                for k, v in existing_variants.items():
                                    norm_k = str(k).strip().lower()
                                    normalized_existing_variants[norm_k] = v
                            if not product:
                                first_row = group.iloc[0]
                                product_data = row_to_shopify_product(first_row)
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
                                product_id = product['id']
                                for _, row in group.iterrows():
                                    variant = row_to_shopify_product(row)['variants'][0]
                                    option1_value = str(variant['option1']).strip().lower()
                                    st.write(f"Checking for existing variant: '{option1_value}' in {list(normalized_existing_variants.keys())}")
                                    if option1_value in normalized_existing_variants:
                                        variant_id = normalized_existing_variants[option1_value]['id']
                                        price = variant.get('price', normalized_existing_variants[option1_value]['price'])
                                        quantity = variant.get('inventory_quantity', normalized_existing_variants[option1_value]['inventory_quantity'])
                                        st.write(f"Updating variant '{option1_value}' (ID: {variant_id}) with price {price} and quantity {quantity}")
                                        success, resp = update_shopify_variant(product_id, variant_id, price, quantity)
                                        if success:
                                            results.append(f"📝 {handle} - {variant['option1']} updated.")
                                        else:
                                            results.append(f"❌ {handle} - {variant['option1']} update failed: {resp}")
                                    else:
                                        st.write(f"Adding new variant '{variant['option1']}' to product {handle}")
                                        success, resp = add_shopify_variant(product_id, variant)
                                        if success:
                                            results.append(f"➕ {handle} - {variant['option1']} added.")
                                        else:
                                            results.append(f"❌ {handle} - {variant['option1']} add failed: {resp}")
                            progress.progress((list(enriched_df['Handle']).index(handle) + 1) / len(enriched_df['Handle'].unique()))
                        st.success("Upload complete!")
                        st.write("Results:")
                        for r in results:
                            st.write(r)
                return
            if not name_col:
                st.error("CSV or TXT must contain a 'name', 'Name', 'title', or 'Title' column or be formatted as 'Quantity Card Name' or 'Card Name, Quantity'.")
                return
            set_col = None
            for col in ['Edition Code', 'Set Code', 'set', 'Set']:
                if col in df.columns:
                    set_col = col
                    break
            if set_col and set_col in df.columns:
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
                    qty_col = 'quantity' if 'quantity' in df.columns else 'Quantity' if 'Quantity' in df.columns else None
                    if qty_col:
                        enriched['Variant Inventory Qty'] = row[qty_col]
                    usd_price = info.get('usd_price')
                    enriched['Variant Price'] = calculate_price_with_vat(usd_price, usd_to_zar)
                    enriched['Status'] = 'draft'
                    enriched['Variant Fulfillment Service'] = 'manual'
                    enriched['Variant Inventory Policy'] = 'deny'
                    enriched['Vendor'] = 'Top Deck'
                    enriched['Product Category'] = 'Gaming Cards'
                    enriched['Published'] = 'TRUE'
                    enriched['Option1 Name'] = 'Version'
                    enriched['Variant Grams'] = 2
                    enriched['Variant Inventory Tracker'] = 'shopify'
                    enriched['Variant Requires Shipping'] = 'TRUE'
                    enriched['Variant Taxable'] = 'TRUE'
                    enriched['Gift Card'] = 'FALSE'
                    enriched['Variant Weight Unit'] = 'g'
                    fallback_card_number = row.get('Card Number', '') if 'Card Number' in row else None
                    fallback_set_name = row.get('Edition', '') if 'Edition' in row else None
                    if info:
                        enriched['Option1 Value'] = build_option1_value(info, foil, fallback_card_number, fallback_set_name)
                    else:
                        enriched['Option1 Value'] = build_option1_value({}, foil, fallback_card_number, fallback_set_name)
                    if info:
                        enriched['Set Name'] = info.get('set_name', '') or row.get('Edition', '')
                        enriched['Card Number'] = info.get('collector_number', '') or fallback_card_number
                        enriched['Rarity'] = info.get('rarity', '')
                        rarity_tag = f"Rarity: {info.get('rarity', '').capitalize()}"
                        if 'Tags' in enriched and rarity_tag not in enriched['Tags']:
                            enriched['Tags'] = f"{enriched['Tags']}, {rarity_tag}" if enriched['Tags'] else rarity_tag
                    else:
                        enriched['Set Name'] = row.get('Edition', '')
                        enriched['Card Number'] = fallback_card_number
                    enriched['Variant Image'] = enriched.get('Image Src', '')
                    enriched_rows.append(enriched)
                enriched_df = pd.DataFrame(enriched_rows, columns=SHOPIFY_COLUMNS)
                st.subheader('Preview of Option1 Value (first 10 rows):')
                st.dataframe(enriched_df[['Name', 'Set Name', 'Card Number', 'Option1 Value']].head(10), use_container_width=True)
                if enriched_df['Option1 Value'].isnull().any() or (enriched_df['Option1 Value'] == '').any():
                    st.warning('Some rows are missing Option1 Value. Please check your input or Scryfall data.')
                output = io.StringIO()
                enriched_df.to_csv(output, index=False)
                st.download_button("Download Shopify-style tagged CSV", data=output.getvalue(), file_name="shopify_tagged_cards.csv", mime="text/csv")
                st.markdown("---")
                with st.expander("Upload to Shopify (Advanced)"):
                    if st.button("Upload to Shopify"):
                        st.info("Uploading products to Shopify...")
                        results = []
                        progress = st.progress(0)
                        for handle, group in enriched_df.groupby('Handle'):
                            product, existing_variants = get_product_variants_by_handle(handle)
                            if not product:
                                first_row = group.iloc[0]
                                product_data = row_to_shopify_product(first_row)
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
                                product_id = product['id']
                                for _, row in group.iterrows():
                                    variant = row_to_shopify_product(row)['variants'][0]
                                    option1_value = variant['option1']
                                    if option1_value in existing_variants:
                                        variant_id = existing_variants[option1_value]['id']
                                        price = variant.get('price', existing_variants[option1_value]['price'])
                                        quantity = variant.get('inventory_quantity', existing_variants[option1_value]['inventory_quantity'])
                                        success, resp = update_shopify_variant(product_id, variant_id, price, quantity)
                                        if success:
                                            results.append(f"📝 {handle} - {option1_value} updated.")
                                        else:
                                            results.append(f"❌ {handle} - {option1_value} update failed: {resp}")
                                    else:
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

    elif page == "Download Set as Shopify CSV":
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🏠 Back to Home"):
                st.session_state.current_page = "Home"
                st.rerun()
        with col2:
            st.header("Download Set as Shopify CSV")
        st.markdown("""
        Select a Magic set to download all regular cards as a Shopify-enriched CSV. Only regular cards (not tokens, promos, or digital-only) are included.
        """)
        sets = fetch_scryfall_sets()
        if sets:
            set_options = {f"{s['name']} ({s['code'].upper()})": s['code'] for s in sets}
            selected_set = st.selectbox("Select a Magic set:", list(set_options.keys()))
            if selected_set:
                set_code = set_options[selected_set]
                if st.button(f"Fetch and Download All Cards from {selected_set}"):
                    st.info(f"Fetching all regular cards from set {selected_set}...")
                    cards = fetch_all_regular_cards_for_set(set_code)
                    st.success(f"Fetched {len(cards)} cards from {selected_set}.")
                    usd_to_zar = get_usd_to_zar()
                    enriched_rows = []
                    for card in cards:
                        rarity = card.get('rarity', '').capitalize()
                        colors = card.get('colors', [])
                        color_map = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'}
                        if not colors:
                            color_tags = ['Colour: Colorless']
                        else:
                            color_tags = [f"Colour: {color_map.get(c, c)}" for c in colors]
                        type_line = card.get('type_line', '')
                        card_types = [t.strip() for t in type_line.split('—')[0].split() if t and t[0].isupper()]
                        type_tag = f"Type: {' '.join(card_types)}" if card_types else ''
                        rarity_tag = f"Rarity: {rarity}" if rarity else ''
                        tags = ', '.join(color_tags + [rarity_tag, type_tag])
                        usd_price = card.get('prices', {}).get('usd')
                        image_url = ''
                        if 'image_uris' in card and 'png' in card['image_uris']:
                            image_url = card['image_uris']['png']
                        elif 'card_faces' in card and isinstance(card['card_faces'], list) and 'image_uris' in card['card_faces'][0] and 'png' in card['card_faces'][0]['image_uris']:
                            image_url = card['card_faces'][0]['image_uris'].get('png', '')
                        info = {
                            'Handle': card['name'].lower().replace(' ', '-'),
                            'Name': card.get('name', ''),
                            'Type': type_line,
                            'Tags': tags,
                            'Rarity (product.metafields.shopify.rarity)': rarity,
                            'Color (product.metafields.shopify.color-pattern)': ', '.join(color_tags),
                            'usd_price': usd_price,
                            'Image Src': image_url,
                            'Variant Image': image_url,
                            'Set Name': card.get('set_name', ''),
                            'Card Number': card.get('collector_number', ''),
                            'Rarity': rarity
                        }
                        enriched = {col: '' for col in SHOPIFY_COLUMNS}
                        enriched.update(info)
                        enriched['Variant Inventory Qty'] = 1
                        enriched['Variant Price'] = calculate_price_with_vat(usd_price, usd_to_zar)
                        enriched['Status'] = 'draft'
                        enriched['Variant Fulfillment Service'] = 'manual'
                        enriched['Variant Inventory Policy'] = 'deny'
                        enriched['Vendor'] = 'Top Deck'
                        enriched['Product Category'] = 'Gaming Cards'
                        enriched['Published'] = 'TRUE'
                        enriched['Option1 Name'] = 'Version'
                        enriched['Variant Grams'] = 2
                        enriched['Variant Inventory Tracker'] = 'shopify'
                        enriched['Variant Requires Shipping'] = 'TRUE'
                        enriched['Variant Taxable'] = 'TRUE'
                        enriched['Gift Card'] = 'FALSE'
                        enriched['Variant Weight Unit'] = 'g'
                        enriched['Option1 Value'] = card.get('set_name', '')
                        enriched_rows.append(enriched)
                    enriched_df = pd.DataFrame(enriched_rows, columns=SHOPIFY_COLUMNS)
                    st.subheader('Preview (first 10 cards):')
                    st.dataframe(enriched_df[['Name', 'Set Name', 'Card Number', 'Option1 Value']].head(10), use_container_width=True)
                    output = io.StringIO()
                    enriched_df.to_csv(output, index=False)
                    st.download_button(f"Download Shopify CSV for {selected_set}", data=output.getvalue(), file_name=f"shopify_{set_code}_cards.csv", mime="text/csv")
        else:
            st.warning("Could not fetch Magic sets from Scryfall.")

    elif page == "Top Deck Count Sheet to Shopify CSV with Prices":
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🏠 Back to Home"):
                st.session_state.current_page = "Home"
                st.rerun()
        with col2:
            st.header("Top Deck Count Sheet to Shopify CSV with Prices")
        st.markdown("""
        Upload a count CSV file and a Shopify CSV file to adjust inventory quantities.
        The count sheet should contain: card_name, set_name, collector_number, inventory_quantity, and Foil inventory_quantity.
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Upload Count Sheet")
            count_file = st.file_uploader("Choose count CSV file", type=["csv"], key="count_file")
            
        with col2:
            st.subheader("Upload Shopify CSV")
            shopify_file = st.file_uploader("Choose Shopify CSV file", type=["csv"], key="shopify_file")
        
        if count_file and shopify_file:
            try:
                count_df = pd.read_csv(count_file)
                shopify_df = pd.read_csv(shopify_file)
                
                st.success(f"Loaded {len(count_df)} count records and {len(shopify_df)} Shopify records")
                
                # Show preview of count data
                st.subheader("Count Sheet Preview")
                st.dataframe(count_df[['card_name', 'set_name', 'collector_number', 'inventory_quantity', 'Foil inventory_quantity']].head(10), use_container_width=True)
                
                # Show preview of Shopify data
                st.subheader("Shopify CSV Preview")
                shopify_preview_cols = ['Handle', 'Title', 'Option1 Value', 'Variant Inventory Qty', 'Variant Price']
                shopify_available_cols = [col for col in shopify_preview_cols if col in shopify_df.columns]
                st.dataframe(shopify_df[shopify_available_cols].head(10), use_container_width=True)
                
                if st.button("Adjust Inventory Quantities"):
                    st.info("Processing inventory adjustments...")
                    
                    # Add debugging info
                    st.write(f"Count sheet columns: {list(count_df.columns)}")
                    st.write(f"Shopify CSV columns: {list(shopify_df.columns)}")
                    st.write(f"Sample count data:")
                    st.write(count_df[['card_name', 'set_name', 'collector_number', 'inventory_quantity', 'Foil inventory_quantity']].head(3))
                    st.write(f"Sample Shopify data:")
                    st.write(shopify_df[['Title', 'Option1 Value', 'Variant Inventory Qty']].head(3))
                    
                    adjusted_df = adjust_shopify_csv_with_counts(count_df, shopify_df)
                    
                    st.success(f"Created {len(adjusted_df)} inventory records")
                    
                    # Show preview of adjusted data
                    st.subheader("Adjusted Inventory Preview")
                    preview_cols = ['Title', 'Option1 Value', 'Variant Inventory Qty', 'Variant Price']
                    available_cols = [col for col in preview_cols if col in adjusted_df.columns]
                    st.dataframe(adjusted_df[available_cols].head(10), use_container_width=True)
                    
                    # Download adjusted CSV
                    output = io.StringIO()
                    adjusted_df.to_csv(output, index=False)
                    st.download_button(
                        "Download Adjusted Shopify CSV", 
                        data=output.getvalue(), 
                        file_name="adjusted_shopify_inventory.csv", 
                        mime="text/csv"
                    )
                    
            except Exception as e:
                st.error(f"Error processing files: {str(e)}")
                st.info("Make sure your count CSV has columns: card_name, set_name, collector_number, inventory_quantity, Foil inventory_quantity")
                st.info("Make sure your Shopify CSV has the standard Shopify product format with Title and Option1 Value columns")
        elif count_file or shopify_file:
            st.warning("Please upload both files to proceed")
        else:
            st.info("Upload both a count CSV file and a Shopify CSV file to adjust inventory quantities")

    elif page == "Price Check & Update":
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🏠 Back to Home"):
                st.session_state.current_page = "Home"
                st.rerun()
        with col2:
            st.header("Price Check & Update")
        st.markdown("""
        Upload a Shopify CSV file to check and update prices based on current Scryfall data.
        Prices will only be updated if the Scryfall price (converted to ZAR with VAT) is higher than the existing price.
        """)
        
        shopify_file = st.file_uploader("Choose Shopify CSV file", type=["csv"], key="price_check_file")
        
        if shopify_file:
            try:
                shopify_df = pd.read_csv(shopify_file)
                st.success(f"Loaded {len(shopify_df)} Shopify records")
                
                # Show preview of Shopify data
                st.subheader("Shopify CSV Preview")
                preview_cols = ['Handle', 'Title', 'Option1 Value', 'Variant Price']
                available_cols = [col for col in preview_cols if col in shopify_df.columns]
                st.dataframe(shopify_df[available_cols].head(10), use_container_width=True)
                
                if st.button("Check and Update Prices"):
                    st.info("Checking prices against Scryfall data...")
                    
                    # Debug: Show available columns
                    st.write(f"Available columns in CSV: {list(shopify_df.columns)}")
                    
                    # Get exchange rate
                    usd_to_zar = get_usd_to_zar()
                    if not usd_to_zar:
                        st.error("Could not fetch USD to ZAR exchange rate. Price updates will be skipped.")
                        return
                    
                    st.info(f"Current USD to ZAR exchange rate: 1 USD = {usd_to_zar:.2f} ZAR")
                    
                    # Process price updates
                    updated_df = shopify_df.copy()
                    price_updates = 0
                    price_checks = 0
                    price_changes = []  # Store all price change information
                    
                    # Debug: Show total number of rows and unique handles
                    st.write(f"Total rows in CSV: {len(updated_df)}")
                    st.write(f"Unique handles found: {updated_df['Handle'].nunique()}")
                    st.write(f"Sample handles: {updated_df['Handle'].head(5).tolist()}")
                    
                    # Group by Handle to process each product
                    total_products = len(updated_df.groupby('Handle'))
                    processed = 0
                    
                    for handle, group in updated_df.groupby('Handle'):
                        processed += 1
                        # Get the first row to extract card name
                        first_row = group.iloc[0]
                        card_name = first_row.get('Title', '')
                        
                        st.write(f"Processing {processed}/{total_products}: '{handle}' with card_name: '{card_name}'")
                        st.write(f"  Raw Title value: {repr(first_row.get('Title', ''))}")
                        st.write(f"  Title type: {type(first_row.get('Title', ''))}")
                        
                        # Try to extract card name from Option1 Value if Title is NaN
                        if not card_name or pd.isna(card_name):
                            option1_value = first_row.get('Option1 Value', '')
                            st.write(f"  Trying Option1 Value: {option1_value}")
                            
                            # Extract card name from Option1 Value (e.g., "Edge of Eternities: Stellar Sights {M} #1 (Foil) [Boosterfun]" -> "Edge of Eternities: Stellar Sights")
                            if option1_value and not pd.isna(option1_value):
                                # Remove the set code and collector number
                                import re
                                # Remove everything after the first { or [
                                card_name = re.sub(r'\{.*?\}.*$', '', option1_value).strip()
                                card_name = re.sub(r'\[.*?\]', '', card_name).strip()
                                st.write(f"  Extracted card name: '{card_name}'")
                                
                                # The issue is we're getting the set name, not the card name
                                # We need to extract the actual card name from the handle
                                # Handle format: "ancient-tomb", "blast-zone", etc.
                                # Convert handle back to card name
                                card_name_from_handle = handle.replace('-', ' ').title()
                                st.write(f"  Card name from handle: '{card_name_from_handle}'")
                                card_name = card_name_from_handle
                                
                                # Debug: Show the exact card name being used for Scryfall
                                st.write(f"  Final card name for Scryfall: '{card_name}'")
                        
                        if not card_name or pd.isna(card_name):
                            st.write(f"  ⚠️ Skipping - no valid card name")
                            continue
                        
                        price_checks += 1
                        st.write(f"Processing product: {card_name} (Handle: {handle}) - {len(group)} variants")
                        
                        # Check each variant of this product
                        for idx, row in group.iterrows():
                            option1_value = row.get('Option1 Value', '')
                            
                            # Check if Variant Price column exists, otherwise use 0
                            if 'Variant Price' in row:
                                current_price = row.get('Variant Price', '')
                            else:
                                current_price = ''
                                st.write(f"  ⚠️ No 'Variant Price' column found in CSV")
                            
                            # Determine if this is a foil variant
                            is_foil = '(Foil)' in option1_value if option1_value else False
                            
                            st.write(f"  Checking variant: {option1_value} (Foil: {is_foil}) - Current price: {current_price}")
                            
                            # Convert current price to float
                            if pd.notna(current_price) and current_price != '':
                                try:
                                    current_price_float = float(current_price)
                                except (ValueError, TypeError):
                                    current_price_float = 0
                            else:
                                current_price_float = 0
                            
                            # Get Scryfall price with better error handling
                            st.write(f"    Calling Scryfall for: '{card_name}' (Foil: {is_foil})")
                            
                            # Add rate limiting to avoid API issues
                            import time
                            time.sleep(0.1)  # 100ms delay between calls
                            
                            try:
                                # Try to get the specific set version first
                                set_code = None
                                if option1_value and not pd.isna(option1_value):
                                    # Use the correct set code for Edge of Eternities: Stellar Sights
                                    set_code = "eos"
                                    st.write(f"    Trying with set code: '{set_code}'")
                                    scryfall_data = fetch_card_info(card_name, set_code, is_foil)
                                    
                                    # If that fails, try without set
                                    if not scryfall_data or not scryfall_data.get('usd_price'):
                                        st.write(f"    Set-specific search failed, trying generic search")
                                        scryfall_data = fetch_card_info(card_name, None, is_foil)
                                else:
                                    scryfall_data = fetch_card_info(card_name, None, is_foil)
                                
                                st.write(f"    Scryfall response: {scryfall_data}")
                                
                                # Debug: Check if we got any data
                                if scryfall_data:
                                    st.write(f"    Has usd_price: {'usd_price' in scryfall_data}")
                                    if 'usd_price' in scryfall_data:
                                        st.write(f"    USD price: {scryfall_data['usd_price']}")
                                    
                                    # Show all available price data
                                    if 'prices' in scryfall_data:
                                        st.write(f"    All prices: {scryfall_data['prices']}")
                                    else:
                                        st.write(f"    No prices object found")
                                else:
                                    st.write(f"    No Scryfall data returned")
                                    
                            except Exception as e:
                                st.write(f"    Scryfall API error: {str(e)}")
                                scryfall_data = None
                            
                            if scryfall_data and 'usd_price' in scryfall_data and scryfall_data['usd_price']:
                                try:
                                    scryfall_usd = float(scryfall_data['usd_price'])
                                    scryfall_zar_calculated = calculate_price_with_vat(scryfall_usd, usd_to_zar)
                                    
                                    if scryfall_zar_calculated and scryfall_zar_calculated != '':
                                        scryfall_zar = float(scryfall_zar_calculated)
                                        if scryfall_zar > current_price_float:
                                            updated_df.loc[idx, 'Variant Price'] = scryfall_zar_calculated
                                            price_updates += 1
                                            price_changes.append({
                                                'Card Name': card_name,
                                                'Variant': 'Foil' if is_foil else 'Regular',
                                                'Original Price': f"R{current_price_float:.2f}",
                                                'New Price': f"R{scryfall_zar:.2f}",
                                                'Scryfall ZAR': f"R{scryfall_zar:.2f}",
                                                'Status': 'Updated'
                                            })
                                        else:
                                            price_changes.append({
                                                'Card Name': card_name,
                                                'Variant': 'Foil' if is_foil else 'Regular',
                                                'Original Price': f"R{current_price_float:.2f}",
                                                'New Price': f"R{current_price_float:.2f}",
                                                'Scryfall ZAR': f"R{scryfall_zar:.2f}",
                                                'Status': 'No Change'
                                            })
                                    else:
                                        price_changes.append({
                                            'Card Name': card_name,
                                            'Variant': 'Foil' if is_foil else 'Regular',
                                            'Original Price': f"R{current_price_float:.2f}",
                                            'New Price': f"R{current_price_float:.2f}",
                                            'Scryfall ZAR': 'N/A',
                                            'Status': 'No Valid Price'
                                        })
                                except (ValueError, TypeError):
                                    price_changes.append({
                                        'Card Name': card_name,
                                        'Variant': 'Foil' if is_foil else 'Regular',
                                        'Original Price': f"R{current_price_float:.2f}",
                                        'New Price': f"R{current_price_float:.2f}",
                                        'Scryfall ZAR': 'Error',
                                        'Status': 'Error'
                                    })
                            else:
                                price_changes.append({
                                    'Card Name': card_name,
                                    'Variant': 'Foil' if is_foil else 'Regular',
                                    'Original Price': f"R{current_price_float:.2f}",
                                    'New Price': f"R{current_price_float:.2f}",
                                    'Scryfall ZAR': 'Not Found',
                                    'Status': 'No Scryfall Data'
                                })
                    
                    st.success(f"Price check complete! Checked {price_checks} products, updated {price_updates} prices.")
                    
                    # Play completion sound
                    st.audio("https://www.soundjay.com/misc/sounds/bell-ringing-05.wav", format="audio/wav")
                    
                    st.info(f"Results summary: {len(price_changes)} total variants processed")
                    
                    # Display comprehensive price change list
                    if price_changes:
                        st.subheader("Price Change Summary")
                        
                        # Create DataFrame for better display
                        price_df = pd.DataFrame(price_changes)
                        
                        # Show summary statistics
                        updated_count = len(price_df[price_df['Status'] == 'Updated'])
                        no_change_count = len(price_df[price_df['Status'] == 'No Change'])
                        error_count = len(price_df[price_df['Status'].isin(['Error', 'No Valid Price', 'No Scryfall Data'])])
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Updated", updated_count)
                        with col2:
                            st.metric("No Change", no_change_count)
                        with col3:
                            st.metric("Errors/Issues", error_count)
                        
                        # Show detailed error breakdown
                        if error_count > 0:
                            st.subheader("Error Breakdown")
                            error_df = price_df[price_df['Status'].isin(['Error', 'No Valid Price', 'No Scryfall Data'])]
                            error_summary = error_df['Status'].value_counts()
                            st.write("Error types found:")
                            for error_type, count in error_summary.items():
                                st.write(f"- {error_type}: {count}")
                            
                            # Show first few error examples
                            st.write("Sample errors:")
                            st.dataframe(error_df[['Card Name', 'Variant', 'Status']].head(10), use_container_width=True)
                        
                        # Show detailed price change table
                        st.subheader("Detailed Price Changes")
                        
                        # Add filter options
                        status_filter = st.selectbox(
                            "Filter by status:",
                            ["All", "Updated", "No Change", "Error", "No Valid Price", "No Scryfall Data"]
                        )
                        
                        if status_filter == "All":
                            filtered_df = price_df
                        else:
                            filtered_df = price_df[price_df['Status'] == status_filter]
                        
                        st.write(f"Showing {len(filtered_df)} results for '{status_filter}'")
                        st.dataframe(filtered_df, use_container_width=True)
                        
                        # Download price change report
                        price_report = io.StringIO()
                        price_df.to_csv(price_report, index=False)
                        st.download_button(
                            "Download Price Change Report",
                            data=price_report.getvalue(),
                            file_name="price_change_report.csv",
                            mime="text/csv"
                        )
                    
                    # Add a column to show which rows were updated
                    updated_df['Price Updated'] = 'No'
                    for change in price_changes:
                        if change['Status'] == 'Updated':
                            # Find matching rows and mark them as updated
                            mask = (
                                (updated_df['Handle'] == change['Card Name'].lower().replace(' ', '-')) &
                                (updated_df['Option1 Value'].str.contains('(Foil)', na=False) == ('Foil' in change['Variant']))
                            )
                            updated_df.loc[mask, 'Price Updated'] = 'Yes'
                    
                    # Show preview of updated data
                    st.subheader("Updated Prices Preview")
                    preview_cols = ['Handle', 'Title', 'Option1 Value', 'Variant Price', 'Price Updated']
                    available_cols = [col for col in preview_cols if col in updated_df.columns]
                    st.dataframe(updated_df[available_cols].head(10), use_container_width=True)
                    
                    # Download updated CSV
                    output = io.StringIO()
                    updated_df.to_csv(output, index=False)
                    st.download_button(
                        "Download Updated Shopify CSV", 
                        data=output.getvalue(), 
                        file_name="updated_shopify_prices.csv", 
                        mime="text/csv"
                    )
                    
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")
                st.info("Make sure your Shopify CSV has the standard Shopify product format")
        else:
            st.info("Upload a Shopify CSV file to check and update prices")

    elif page == "Deckbox Collection Value Calculator":
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🏠 Back to Home"):
                st.session_state.current_page = "Home"
                st.rerun()
        with col2:
            st.header("🎴 Collection Value Calculator")
        
        st.write("Calculate the value of your Magic: The Gathering collections and decks. Supports both Deckbox collections and Moxfield decks.")
        
        # Platform selection
        platform = st.radio("Select platform:", ["Deckbox Collection", "Moxfield Deck"])
        
        if platform == "Deckbox Collection":
            st.subheader("📚 Deckbox Collection")
            st.write("The app scrapes the entire collection. It shows the total value, the value of cards above 2, the value in rand, and the store offer.")
            
            url = st.text_input("Enter your Deckbox collection URL:")
            
            if url:
                with st.spinner("Scraping your entire Deckbox collection..."):
                    try:
                        cards = scrape_entire_collection(url)
                        df_all, total_value_all = aggregate_cards(cards)
                        # Filter for cards $2+
                        cards_2plus = [c for c in cards if c['Price'] >= 2.0]
                        df_2plus, total_value_2plus = aggregate_cards(cards_2plus)
                        # Rand values
                        total_value_all_rand = total_value_all * USD_TO_ZAR
                        total_value_2plus_rand = total_value_2plus * USD_TO_ZAR
                        store_offer_usd = total_value_2plus * STORE_OFFER_PERCENT
                        store_offer_rand = store_offer_usd * USD_TO_ZAR
                        store_credit_usd = total_value_2plus * STORE_CREDIT_PERCENT
                        store_credit_rand = store_credit_usd * USD_TO_ZAR
                        
                        st.header(":moneybag: Collection Summary")
                        st.write(f"Total collection worth: {total_value_all:,.2f}  |  R{total_value_all_rand:,.2f}")
                        st.write(f"Cards 2 and up worth: {total_value_2plus:,.2f}  |  R{total_value_2plus_rand:,.2f}")
                        st.write(f"Store offer (forty percent of 2 and up): {store_offer_usd:,.2f}  |  R{store_offer_rand:,.2f}")
                        st.write(f"Store credit (fifty percent of 2 and up): {store_credit_usd:,.2f}  |  R{store_credit_rand:,.2f}")
                        st.write("---")
                        
                        st.subheader("All Cards")
                        if not df_all.empty:
                            st.dataframe(df_all, use_container_width=True)
                        else:
                            st.warning("No cards found. Please check your collection URL.")
                        
                        st.subheader("Cards 2 and Up (Store Offer Table)")
                        if not df_2plus.empty:
                            st.dataframe(df_2plus, use_container_width=True)
                        else:
                            st.warning("No cards 2 or greater found.")
                            
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        elif platform == "Moxfield Deck":
            st.subheader("🎴 Moxfield Deck")
            st.write("Enter a Moxfield deck URL to calculate its value. The app will fetch deck data and get current prices from Scryfall.")
            
            # Add tabs for different input methods
            moxfield_tab1, moxfield_tab2 = st.tabs(["🔗 URL Input", "📝 Manual Input"])
            
            with moxfield_tab1:
                moxfield_url = st.text_input("Enter your Moxfield deck URL:")
                
                if moxfield_url:
                    # Extract deck ID from URL
                    deck_id = extract_moxfield_deck_id(moxfield_url)
                    
                    if not deck_id:
                        st.error("Could not extract deck ID from URL. Please check the URL format.")
                    else:
                        with st.spinner("Fetching deck data from Moxfield..."):
                            try:
                                # Fetch deck data
                                deck_data = fetch_moxfield_deck(deck_id)
                                
                                if deck_data:
                                    st.success(f"Successfully fetched deck: {deck_data.get('name', 'Unknown Deck')}")
                                    
                                    # Parse deck data
                                    cards = parse_moxfield_deck(deck_data)
                                    
                                    if cards:
                                        st.info(f"Found {len(cards)} cards in deck")
                                        
                                        # Get prices from Scryfall
                                        with st.spinner("Fetching current prices from Scryfall..."):
                                            priced_cards = get_card_prices_from_scryfall(cards)
                                            
                                            if priced_cards:
                                                # Create DataFrame
                                                df_all = pd.DataFrame(priced_cards)
                                                total_value_all = df_all['Total'].sum()
                                                
                                                # Filter for cards $2+
                                                cards_2plus = [c for c in priced_cards if c['Price'] >= 2.0]
                                                df_2plus = pd.DataFrame(cards_2plus) if cards_2plus else pd.DataFrame()
                                                total_value_2plus = df_2plus['Total'].sum() if not df_2plus.empty else 0.0
                                                
                                                # Rand values
                                                total_value_all_rand = total_value_all * USD_TO_ZAR
                                                total_value_2plus_rand = total_value_2plus * USD_TO_ZAR
                                                store_offer_usd = total_value_2plus * STORE_OFFER_PERCENT
                                                store_offer_rand = store_offer_usd * USD_TO_ZAR
                                                store_credit_usd = total_value_2plus * STORE_CREDIT_PERCENT
                                                store_credit_rand = store_credit_usd * USD_TO_ZAR
                                                
                                                st.header(":moneybag: Deck Summary")
                                                st.write(f"Total deck worth: {total_value_all:,.2f}  |  R{total_value_all_rand:,.2f}")
                                                st.write(f"Cards 2 and up worth: {total_value_2plus:,.2f}  |  R{total_value_2plus_rand:,.2f}")
                                                st.write(f"Store offer (forty percent of 2 and up): {store_offer_usd:,.2f}  |  R{store_offer_rand:,.2f}")
                                                st.write(f"Store credit (fifty percent of 2 and up): {store_credit_usd:,.2f}  |  R{store_credit_rand:,.2f}")
                                                st.write("---")
                                                
                                                # Show cards by section
                                                st.subheader("All Cards by Section")
                                                if not df_all.empty:
                                                    st.dataframe(df_all, use_container_width=True)
                                                else:
                                                    st.warning("No cards found in deck.")
                                                
                                                st.subheader("Cards 2 and Up (Store Offer Table)")
                                                if not df_2plus.empty:
                                                    st.dataframe(df_2plus, use_container_width=True)
                                                else:
                                                    st.warning("No cards 2 or greater found.")
                                                    
                                            else:
                                                st.error("Could not fetch prices for cards.")
                                    else:
                                        st.warning("No cards found in deck.")
                                else:
                                    st.error("Could not fetch deck data from Moxfield.")
                                    st.info("💡 Try the Manual Input tab if URL access fails.")
                                    
                            except Exception as e:
                                st.error(f"Error processing Moxfield deck: {e}")
                                st.info("💡 Try the Manual Input tab if URL access fails.")
            
            with moxfield_tab2:
                st.write("If URL access fails, you can manually enter your deck list.")
                st.write("**💡 How to get your deck list from Moxfield:**")
                st.write("1. In Moxfield, click the **3 dots** (⋮) next to your deck")
                st.write("2. Click **Export** to get the deck list")
                st.write("3. Copy and paste the deck list below")
                st.write("")
                st.write("**Format:** One card per line, with quantity (e.g., '2x Lightning Bolt' or 'Lightning Bolt (2)')")
                
                manual_deck_text = st.text_area("Enter your deck list:", height=200, 
                                               placeholder="2x Lightning Bolt\n1x Black Lotus\n3x Counterspell\n...")
                
                if manual_deck_text:
                    with st.spinner("Processing manual deck list..."):
                        try:
                            # Parse manual deck text
                            cards = parse_manual_deck_list(manual_deck_text)
                            
                            if cards:
                                st.info(f"Found {len(cards)} cards in deck")
                                
                                # Get prices from Scryfall
                                with st.spinner("Fetching current prices from Scryfall..."):
                                    priced_cards = get_card_prices_from_scryfall(cards)
                                    
                                    if priced_cards:
                                        # Create DataFrame
                                        df_all = pd.DataFrame(priced_cards)
                                        total_value_all = df_all['Total'].sum()
                                        
                                        # Filter for cards $2+
                                        cards_2plus = [c for c in priced_cards if c['Price'] >= 2.0]
                                        df_2plus = pd.DataFrame(cards_2plus) if cards_2plus else pd.DataFrame()
                                        total_value_2plus = df_2plus['Total'].sum() if not df_2plus.empty else 0.0
                                        
                                        # Rand values
                                        total_value_all_rand = total_value_all * USD_TO_ZAR
                                        total_value_2plus_rand = total_value_2plus * USD_TO_ZAR
                                        store_offer_usd = total_value_2plus * STORE_OFFER_PERCENT
                                        store_offer_rand = store_offer_usd * USD_TO_ZAR
                                        store_credit_usd = total_value_2plus * STORE_CREDIT_PERCENT
                                        store_credit_rand = store_credit_usd * USD_TO_ZAR
                                        
                                        st.header(":moneybag: Deck Summary")
                                        st.write(f"Total deck worth: {total_value_all:,.2f}  |  R{total_value_all_rand:,.2f}")
                                        st.write(f"Cards 2 and up worth: {total_value_2plus:,.2f}  |  R{total_value_2plus_rand:,.2f}")
                                        st.write(f"Store offer (forty percent of 2 and up): {store_offer_usd:,.2f}  |  R{store_offer_rand:,.2f}")
                                        st.write(f"Store credit (fifty percent of 2 and up): {store_credit_usd:,.2f}  |  R{store_credit_rand:,.2f}")
                                        st.write("---")
                                        
                                        # Show cards
                                        st.subheader("All Cards")
                                        if not df_all.empty:
                                            st.dataframe(df_all, use_container_width=True)
                                        else:
                                            st.warning("No cards found in deck.")
                                        
                                        st.subheader("Cards 2 and Up (Store Offer Table)")
                                        if not df_2plus.empty:
                                            st.dataframe(df_2plus, use_container_width=True)
                                        else:
                                            st.warning("No cards 2 or greater found.")
                                            
                                    else:
                                        st.error("Could not fetch prices for cards.")
                            else:
                                st.warning("No cards found in deck list.")
                                
                        except Exception as e:
                            st.error(f"Error processing manual deck list: {e}")



if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "runnow":
        import subprocess
        import os
        # Relaunch as streamlit app
        cmd = [sys.executable, '-m', 'streamlit', 'run', os.path.abspath(__file__)]
        subprocess.run(cmd)
    else:
        main()
