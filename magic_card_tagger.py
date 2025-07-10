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
        if price_zar < 5:
            return '5'
        elif price_zar < 8:
            return '8'
        elif price_zar < 10:
            return '10'
        else:
            return str(int(math.ceil(price_zar)))
    except Exception:
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
    """Retrieves and caches the Shopify store’s location ID for inventory management."""
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
    """Sets the inventory level for a variant at the store’s location using the InventoryLevel API."""
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
    """Updates a variant’s price in Shopify, and sets inventory using the InventoryLevel API. Sends a full variant payload."""
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

# 7. Main App Logic
def main():
    """The main Streamlit app function: handles file upload, enrichment, preview, download, and Shopify upload."""
    st.title("Magic Card Tagger")
    st.write("Upload a CSV or TXT with card names. The app will fill in the Shopify columns with Scryfall data where possible.")

    # --- New Section: Download Shopify CSV for a Magic Set ---
    st.header("Download Shopify CSV for a Magic Set")
    sets = fetch_scryfall_sets()
    if sets:
        set_options = {f"{s['name']} ({s['code'].upper()})": s['code'] for s in sets}
        selected_set = st.selectbox("Select a Magic set to download all regular cards:", list(set_options.keys()))
        if selected_set:
            set_code = set_options[selected_set]
            if st.button(f"Fetch and Download All Cards from {selected_set}"):
                st.info(f"Fetching all regular cards from set {selected_set}...")
                cards = fetch_all_regular_cards_for_set(set_code)
                st.success(f"Fetched {len(cards)} cards from {selected_set}.")
                usd_to_zar = get_usd_to_zar()
                enriched_rows = []
                for card in cards:
                    # Use your enrichment logic to build a Shopify row
                    info = {}
                    # Simulate fetch_card_info output structure
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
                    enriched['Product Category'] = 'Uncategorized'
                    enriched['Published'] = 'TRUE'
                    enriched['Option1 Name'] = 'Version'
                    enriched['Variant Grams'] = 2
                    enriched['Variant Inventory Tracker'] = 'shopify'
                    enriched['Variant Requires Shipping'] = 'TRUE'
                    enriched['Variant Taxable'] = 'TRUE'
                    enriched['Gift Card'] = 'FALSE'
                    enriched['Variant Weight Unit'] = 'g'
                    # Option1 Value = set name
                    enriched['Option1 Value'] = card.get('set_name', '')
                    enriched_rows.append(enriched)
                enriched_df = pd.DataFrame(enriched_rows, columns=SHOPIFY_COLUMNS)
                st.write('Preview (first 10 cards):')
                st.dataframe(enriched_df[['Name', 'Set Name', 'Card Number', 'Option1 Value']].head(10))
                output = io.StringIO()
                enriched_df.to_csv(output, index=False)
                st.download_button(f"Download Shopify CSV for {selected_set}", data=output.getvalue(), file_name=f"shopify_{set_code}_cards.csv", mime="text/csv")
    else:
        st.warning("Could not fetch Magic sets from Scryfall.")

    # --- Existing Section: File Upload ---
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
                enriched['Variant Price'] = calculate_price_with_vat(usd_price, usd_to_zar)
                # Set Shopify-required defaults
                enriched['Status'] = 'draft'
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
                        # Normalize existing variant keys for robust matching
                        normalized_existing_variants = {}
                        if existing_variants:
                            for k, v in existing_variants.items():
                                norm_k = str(k).strip().lower()
                                normalized_existing_variants[norm_k] = v
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
                                option1_value = str(variant['option1']).strip().lower()
                                st.write(f"Checking for existing variant: '{option1_value}' in {list(normalized_existing_variants.keys())}")
                                if option1_value in normalized_existing_variants:
                                    # Update existing variant
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
                                    # Add new variant
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
