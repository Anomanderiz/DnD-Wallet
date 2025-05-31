
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

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

# ---- LOAD DATA ----
def get_wallet_data():
    data = wallet_ws.get_all_records()
    return {row["Character"]: row for row in data}

def get_history():
    return history_ws.get_all_records()

def update_wallet(character, change_cp, label):
    data = get_wallet_data()
    if character not in data:
        st.error("Character not found.")
        return

    old = data[character]
    total_cp = convert_to_cp(
    int(old["Platinum"]),
    int(old["Gold"]),
    int(old["Silver"]),
    int(old["Copper"])
) + change_cp

    if total_cp < 0:
        st.error("Insufficient funds.")
        return

    new_bal = convert_from_cp(total_cp)
    idx = list(data.keys()).index(character) + 2  # 1-based + header
    wallet_ws.update(f"B{idx}:E{idx}", [[new_bal["platinum"], new_bal["gold"], new_bal["silver"], new_bal["copper"]]])

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

def convert_to_cp(platinum=0, gold=0, silver=0, copper=0):
    return platinum * 1000 + gold * 100 + silver * 10 + copper

def convert_from_cp(total_cp):
    return {
        "platinum": total_cp // 1000,
        "gold": (total_cp % 1000) // 100,
        "silver": (total_cp % 100) // 10,
        "copper": total_cp % 10
    }

# ---- UI ----
st.title("💰 D&D Party Wallet Tracker")
data = get_wallet_data()

character = st.selectbox("Select Character", list(data.keys()))

if character:
    st.subheader(f"{character}'s Wallet")
    wallet = data[character]
    st.write(f"Platinum: {wallet['Platinum']}")
    st.write(f"Gold: {wallet['Gold']}")
    st.write(f"Silver: {wallet['Silver']}")
    st.write(f"Copper: {wallet['Copper']}")

    with st.form("txn"):
        st.markdown("### Add / Deduct Currency")
        platinum = st.number_input("Platinum", 0, step=1)
        gold = st.number_input("Gold", 0, step=1)
        silver = st.number_input("Silver", 0, step=1)
        copper = st.number_input("Copper", 0, step=1)
        label = st.text_input("Label")
        txn_type = st.radio("Transaction Type", ["Add", "Deduct"])
        submitted = st.form_submit_button("Submit")
        if submitted:
            mult = 1 if txn_type == "Add" else -1
            change = mult * convert_to_cp(platinum, gold, silver, copper)
            update_wallet(character, change, label)
            st.success("Transaction successful. Please refresh to see updated data.")

# ---- PARTY TOTAL ----
total_cp = sum([
    convert_to_cp(row["Platinum"], row["Gold"], row["Silver"], row["Copper"])
    for row in data.values()
])
total = convert_from_cp(total_cp)
st.markdown("---")
st.subheader("Party Total")
st.write(f"**{total['platinum']}pp, {total['gold']}gp, {total['silver']}sp, {total['copper']}cp**")

# ---- HISTORY ----
st.markdown("---")
st.subheader("Transaction History")
history = get_history()
for row in reversed(history[-50:]):
    st.write(f"{row['Timestamp']} – {row['Character']} – {row['Type']} – {row['Label']} → {row['Platinum']}pp, {row['Gold']}gp, {row['Silver']}sp, {row['Copper']}cp")
