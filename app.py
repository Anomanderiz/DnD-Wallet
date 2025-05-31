import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time

# ---- PASSWORD GATE ----
def password_gate():
    pw = st.text_input("Enter access password", type="password")
    if pw != st.secrets["access_password"]:
        st.stop()

password_gate()

# ---- GOOGLE SHEETS SETUP ----
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

# ---- SPREADSHEET SETUP ----
SHEET_ID = st.secrets["sheet_id"]
wallet_ws = client.open_by_key(SHEET_ID).worksheet("wallets")
history_ws = client.open_by_key(SHEET_ID).worksheet("history")

# ---- UTILITY FUNCTIONS ----
def safe_int(x):
    try:
        return int(x)
    except (ValueError, TypeError):
        return 0

def convert_to_cp(platinum=0, gold=0, silver=0, copper=0):
    return (
        safe_int(platinum) * 1000 +
        safe_int(gold) * 100 +
        safe_int(silver) * 10 +
        safe_int(copper)
    )

def convert_from_cp(total_cp):
    total_cp = safe_int(total_cp)
    return {
        "platinum": total_cp // 1000,
        "gold": (total_cp % 1000) // 100,
        "silver": (total_cp % 100) // 10,
        "copper": total_cp % 10
    }

# ---- DATA FUNCTIONS ----
@st.cache_data(ttl=30)
def get_wallet_data():
    try:
        data = wallet_ws.get_all_records()
        return {row["Character"]: row for row in data}
    except Exception as e:
        st.error(f"Error fetching wallet data: {e}")
        return {}

@st.cache_data(ttl=30)
def get_history():
    try:
        return history_ws.get_all_records()
    except Exception as e:
        st.error(f"Error fetching history: {e}")
        return []

def update_wallet(character, change_cp, label):
    try:
        data = get_wallet_data()
        if character not in data:
            st.error("Character not found.")
            return False

        old = data[character]
        current_cp = convert_to_cp(
            old["Platinum"],
            old["Gold"],
            old["Silver"],
            old["Copper"]
        )

        new_total_cp = current_cp + change_cp

        if new_total_cp < 0:
            st.error("Insufficient funds.")
            return False

        new_bal = convert_from_cp(new_total_cp)
        character_names = [row["Character"] for row in data.values()]
        idx = character_names.index(character) + 2

        wallet_ws.update(f"B{idx}:E{idx}", [[
            new_bal["platinum"],
            new_bal["gold"],
            new_bal["silver"],
            new_bal["copper"]
        ]])

        history_ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            character,
            "Add" if change_cp > 0 else "Deduct",
            label,
            new_bal["platinum"],
            new_bal["gold"],
            new_bal["silver"],
            new_bal["copper"]
        ])

        time.sleep(1)  # throttle write requests to avoid hitting API limits
        return True

    except Exception as e:
        st.error(f"Error updating wallet: {e}")
        return False

# ---- UI ----
st.title("💰 D&D Party Wallet Tracker")

data = get_wallet_data()

if not data:
    st.warning("No character data found. Please check your Google Sheets connection.")
    st.stop()

character = st.selectbox("Select Character", list(data.keys()))

if character:
    st.subheader(f"{character}'s Wallet")
    wallet = data[character]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Platinum", wallet['Platinum'])
    with col2:
        st.metric("Gold", wallet['Gold'])
    with col3:
        st.metric("Silver", wallet['Silver'])
    with col4:
        st.metric("Copper", wallet['Copper'])

    with st.form("txn"):
        st.markdown("### Add / Deduct Currency")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            platinum = st.number_input("Platinum", min_value=0, step=1, value=0)
        with col2:
            gold = st.number_input("Gold", min_value=0, step=1, value=0)
        with col3:
            silver = st.number_input("Silver", min_value=0, step=1, value=0)
        with col4:
            copper = st.number_input("Copper", min_value=0, step=1, value=0)

        label = st.text_input("Transaction Label", placeholder="e.g., 'Bought sword', 'Found treasure'")
        txn_type = st.radio("Transaction Type", ["Add", "Deduct"])

        submitted = st.form_submit_button("Submit Transaction")

        if submitted:
            if not label.strip():
                st.error("Please provide a transaction label.")
            elif platinum == 0 and gold == 0 and silver == 0 and copper == 0:
                st.error("Please enter an amount for the transaction.")
            else:
                multiplier = 1 if txn_type == "Add" else -1
                change_cp = multiplier * convert_to_cp(platinum, gold, silver, copper)

                if update_wallet(character, change_cp, label.strip()):
                    st.success("Transaction successful! Refreshing data...")
                    st.rerun()

# ---- PARTY TOTAL ----
st.markdown("---")
st.subheader("💎 Party Total Wealth")

try:
    total_cp = sum([
        convert_to_cp(row["Platinum"], row["Gold"], row["Silver"], row["Copper"])
        for row in data.values()
    ])
    total = convert_from_cp(total_cp)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Platinum", total['platinum'])
    with col2:
        st.metric("Gold", total['gold'])
    with col3:
        st.metric("Silver", total['silver'])
    with col4:
        st.metric("Copper", total['copper'])

except Exception as e:
    st.error(f"Error calculating party total: {e}")

# ---- TRANSACTION HISTORY ----
st.markdown("---")
st.subheader("📜 Recent Transaction History")

history = get_history()
if history:
    recent_history = list(reversed(history[-20:]))

    for row in recent_history:
        timestamp = row.get('Timestamp', 'Unknown')
        character_name = row.get('Character', 'Unknown')
        txn_type = row.get('Type', 'Unknown')
        txn_label = row.get('Label', 'No label')

        pp = row.get('Platinum', 0)
        gp = row.get('Gold', 0)
        sp = row.get('Silver', 0)
        cp = row.get('Copper', 0)

        st.write(f"**{timestamp}** - {character_name} ({txn_type}): {txn_label}")
        st.write(f"   → Balance: {pp}pp, {gp}gp, {sp}sp, {cp}cp")
        st.write("---")
else:
    st.info("No transaction history found.")
