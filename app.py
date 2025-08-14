import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import time
import requests
import json

# ---- PASSWORD GATE ----
# No changes needed here.
def password_gate():
    pw = st.text_input("Enter access password", type="password")
    if pw != st.secrets["access_password"]:
        st.stop()

password_gate()

# ---- SUPABASE SETUP ----
@st.cache_resource
def init_supabase_client() -> Client:
    """Initialize Supabase client - cached to avoid repeated authentication"""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# Get cached client
supabase = init_supabase_client()

# ---- UTILITY FUNCTIONS ----
# These functions are pure Python and require no changes.
def safe_int(x):
    """Convert value to int safely, returning 0 for invalid values"""
    try:
        return int(x)
    except (ValueError, TypeError):
        return 0

def convert_to_cp(platinum=0, gold=0, silver=0, copper=0):
    """Convert currency to total copper pieces"""
    return (
        safe_int(platinum) * 1000 +
        safe_int(gold) * 100 +
        safe_int(silver) * 10 +
        safe_int(copper)
    )

def convert_from_cp(total_cp):
    """Convert total copper pieces back to currency breakdown"""
    total_cp = safe_int(total_cp)
    return {
        "platinum": total_cp // 1000,
        "gold": (total_cp % 1000) // 100,
        "silver": (total_cp % 100) // 10,
        "copper": total_cp % 10
    }
def send_discord_notification(message: str):
    """
    Sends a message to the Discord channel via a configured webhook.

    Args:
        message (str): The text message to send to the Discord channel.
    """
    # Retrieve the webhook URL from Streamlit's secrets manager.
    # Using .get() is safer as it returns None if the key is not found.
    webhook_url = st.secrets.get("DISCORD_WEBHOOK_URL")

    # If the URL isn't configured, do nothing and exit gracefully.
    if not webhook_url:
        print("Discord webhook URL not found in secrets. Skipping notification.")
        return

    # Format the data payload as required by Discord's API.
    data = {"content": message}

    try:
        # Send the HTTP POST request to the webhook URL.
        # The `json` parameter automatically handles content type headers.
        response = requests.post(webhook_url, json=data, timeout=5)

        # Raise an exception if the request returned an error status (e.g., 404, 500).
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        # This will catch any network errors (timeout, DNS, etc.).
        # The error is printed to the console/logs for debugging.
        print(f"Error sending Discord notification: {e}")
        
# ---- CACHED DATA FUNCTIONS (Refactored for Supabase) ----
@st.cache_data(ttl=30)  # Cache for 30 seconds
def get_wallet_data():
    """Fetch wallet data from Supabase with caching"""
    try:
        response = supabase.table("wallets").select("*").order("character_name").execute()
        # Transform list of dicts into a dict keyed by character_name for compatibility
        return {row["character_name"]: row for row in response.data}
    except Exception as e:
        st.error(f"Error fetching wallet data: {e}")
        return {}

@st.cache_data(ttl=60)  # Cache history for 1 minute
def get_history():
    """Fetch recent transaction history from Supabase with caching"""
    try:
        # Fetch last 20 transactions, joining character name from the 'wallets' table
        response = supabase.table("transactions").select(
            "*, wallets(character_name)"
        ).order("created_at", desc=True).limit(20).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching history: {e}")
        return []

def update_wallet_supabase(character_wallet, change_cp, label, txn_type):
    """Update wallet and log transaction in Supabase."""
    try:
        # --- Step 1: Check for sufficient funds ---
        current_cp = convert_to_cp(
            character_wallet["platinum"],
            character_wallet["gold"],
            character_wallet["silver"],
            character_wallet["copper"]
        )
        if current_cp + change_cp < 0:
            st.error("Insufficient funds for this transaction.")
            return False

        # --- Step 2: Log the immutable transaction event. ---
        # Deconstruct the change from total copper into constituent coins
        change_amounts = convert_from_cp(abs(change_cp))
        
        supabase.table("transactions").insert({
            "character_id": character_wallet['id'], # The Foreign Key
            "description": label,
            "platinum_change": change_amounts['platinum'] if txn_type == "Add" else -change_amounts['platinum'],
            "gold_change": change_amounts['gold'] if txn_type == "Add" else -change_amounts['gold'],
            "silver_change": change_amounts['silver'] if txn_type == "Add" else -change_amounts['silver'],
            "copper_change": change_amounts['copper'] if txn_type == "Add" else -change_amounts['copper'],
        }).execute()
        
        # --- Step 3: Update the character's wallet summary. ---
        new_total_cp = current_cp + change_cp
        new_balance = convert_from_cp(new_total_cp)

        supabase.table("wallets").update({
            "platinum": new_balance["platinum"],
            "gold": new_balance["gold"],
            "silver": new_balance["silver"],
            "copper": new_balance["copper"],
        }).eq("id", character_wallet['id']).execute()

        # --- Step 4: Clear caches to force a refresh on the next run ---
        get_wallet_data.clear()
        get_history.clear()
        
        return True
        
    except Exception as e:
        st.error(f"Error updating wallet: {e}")
        return False

# ---- UI (with minor adjustments) ----
st.title("⚔️ D&D Party Wallet Tracker")

if st.button("🔄 Refresh Data"):
    get_wallet_data.clear()
    get_history.clear()
    st.rerun()

data = get_wallet_data()
if not data:
    st.warning("No character data found. Check your Supabase connection and tables.")
    st.stop()

character_name = st.selectbox("Select Character", list(data.keys()))

if character_name:
    wallet = data[character_name]
    st.subheader(f"{wallet['character_name']}'s Wallet")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Platinum", wallet['platinum'])
    col2.metric("Gold", wallet['gold'])
    col3.metric("Silver", wallet['silver'])
    col4.metric("Copper", wallet['copper'])

    with st.form("txn"):
        st.markdown("### Add / Deduct Currency")
        c1, c2, c3, c4 = st.columns(4)
        platinum = c1.number_input("Platinum", min_value=0, step=1, value=0)
        gold = c2.number_input("Gold", min_value=0, step=1, value=0)
        silver = c3.number_input("Silver", min_value=0, step=1, value=0)
        copper = c4.number_input("Copper", min_value=0, step=1, value=0)
        
        label = st.text_input("Transaction Label", placeholder="e.g., 'Loot from goblin cave'")
        txn_type = st.radio("Transaction Type", ["Add", "Deduct"])
        submitted = st.form_submit_button("Submit Transaction")
        
        if submitted:
            if not label.strip():
                st.error("Please provide a transaction label.")
            else:
                change_cp = convert_to_cp(platinum, gold, silver, copper)
                if change_cp == 0:
                    st.error("Transaction amount cannot be zero.")
                else:
                    multiplier = 1 if txn_type == "Add" else -1
                    if update_wallet_supabase(wallet, multiplier * change_cp, label.strip(), txn_type):
                        st.success("Transaction successful!")
                        # --- NEW: Call the notification function ---
                        # Create a more descriptive message for Discord
                        currency_str = f"{platinum}p, {gold}g, {silver}s, {copper}c"
                        # The Code
                        notification_message = (f"🏦 A Wizard's Vault transaction has been posted to the account of **{character_name}**.\n"
                                                f"The vault has registered a **{txn_type.lower()}** of `{currency_str}` for the purpose of: *{label.strip()}*.\n"
                                                f"The new balance is `{final_balance_str}`.\n"
                                                f"The ledgers are balanced. For now."
                        send_discord_notification(notification_message)
                         # --- END of new code ---
                        time.sleep(0.5) # A brief pause can feel more responsive
                        st.rerun()

# ---- PARTY TOTAL ----
st.markdown("---")
st.subheader("🏰 Party Total Wealth")
try:
    total_cp = sum(convert_to_cp(**{k.lower(): v for k, v in row.items() if k.lower() in ['platinum', 'gold', 'silver', 'copper']}) for row in data.values())
    total = convert_from_cp(total_cp)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Platinum", total['platinum'])
    col2.metric("Gold", total['gold'])
    col3.metric("Silver", total['silver'])
    col4.metric("Copper", total['copper'])
except Exception as e:
    st.error(f"Error calculating party total: {e}")

# ---- TRANSACTION HISTORY ----
st.markdown("---")
st.subheader("📜 Recent Transaction History")
if st.checkbox("Show Transaction History", value=True):
    history = get_history()
    if history:
        for row in history:
            # The structure of 'row' is now much cleaner
            char_name = row['wallets']['character_name'] if row.get('wallets') else 'Unknown'
            change_str = ", ".join([f"{v} {k.split('_')[0]}" for k, v in row.items() if 'change' in k and v != 0])
            
            st.markdown(f"""
            **{datetime.fromisoformat(row['created_at']).strftime('%Y-%m-%d %H:%M')}** - **{char_name}**: {row['description']}
            
            *Change: {change_str}*
            """)
    else:
        st.info("No transaction history found.")
