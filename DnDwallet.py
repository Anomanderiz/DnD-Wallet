import streamlit as st
from datetime import datetime
import json

st.set_page_config(page_title="D&D Party Wallet", layout="wide")

# ----------------------
# Initialize session state
# ----------------------
if "profiles" not in st.session_state:
    st.session_state.profiles = {}

def convert_to_cp(platinum=0, gold=0, silver=0, copper=0):
    return platinum * 1000 + gold * 100 + silver * 10 + copper

def convert_from_cp(total_cp):
    platinum = total_cp // 1000
    gold = (total_cp % 1000) // 100
    silver = (total_cp % 100) // 10
    copper = total_cp % 10
    return {"platinum": platinum, "gold": gold, "silver": silver, "copper": copper}

def update_wallet(profile_name, change_cp, label):
    wallet = st.session_state.profiles[profile_name]["wallet"]
    current_cp = convert_to_cp(**wallet)
    new_total_cp = current_cp + change_cp
    if new_total_cp < 0:
        st.error(f"Transaction failed: {profile_name} cannot have negative balance.")
        return

    new_wallet = convert_from_cp(new_total_cp)
    st.session_state.profiles[profile_name]["wallet"] = new_wallet
    st.session_state.profiles[profile_name]["history"].append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "change": convert_from_cp(abs(change_cp)),
        "type": "Added" if change_cp > 0 else "Deducted",
        "label": label
    })

# ----------------------
# Sidebar: Create or switch profile
# ----------------------
st.sidebar.header("Character Profiles")

new_profile = st.sidebar.text_input("Add New Character")
if st.sidebar.button("Create Profile"):
    if new_profile and new_profile not in st.session_state.profiles:
        st.session_state.profiles[new_profile] = {
            "wallet": {"platinum": 0, "gold": 0, "silver": 0, "copper": 0},
            "history": []
        }

selected_profile = st.sidebar.selectbox("Select Character", list(st.session_state.profiles.keys()))

# ----------------------
# Main Area
# ----------------------
st.title("💰 D&D Party Wallet Tracker")

if selected_profile:
    col1, col2 = st.columns([2, 3])

    with col1:
        st.subheader(f"Wallet: {selected_profile}")
        wallet = st.session_state.profiles[selected_profile]["wallet"]
        st.metric("Platinum", wallet["platinum"])
        st.metric("Gold", wallet["gold"])
        st.metric("Silver", wallet["silver"])
        st.metric("Copper", wallet["copper"])

        st.markdown("### Add / Deduct Currency")
        platinum = st.number_input("Platinum", 0, step=1)
        gold = st.number_input("Gold", 0, step=1)
        silver = st.number_input("Silver", 0, step=1)
        copper = st.number_input("Copper", 0, step=1)
        label = st.text_input("Label (optional)")
        change_type = st.radio("Transaction Type", ["Add", "Deduct"])

        if st.button("Submit Transaction"):
            multiplier = 1 if change_type == "Add" else -1
            total_change_cp = multiplier * convert_to_cp(platinum, gold, silver, copper)
            update_wallet(selected_profile, total_change_cp, label)

    with col2:
        st.subheader("Transaction History")
        history = st.session_state.profiles[selected_profile]["history"]
        if not history:
            st.write("No transactions yet.")
        else:
            for h in reversed(history):
                delta = h["change"]
                delta_str = f'{delta["platinum"]}pp {delta["gold"]}gp {delta["silver"]}sp {delta["copper"]}cp'
                st.write(f'**{h["time"]}** - *{h["type"]}* {delta_str} – {h["label"] or "No Label"}')

# ----------------------
# Party Total Section
# ----------------------
st.markdown("---")
st.header("🧙‍♂️ Party-Wide Total")

total_cp = 0
for profile_data in st.session_state.profiles.values():
    total_cp += convert_to_cp(**profile_data["wallet"])
party_total = convert_from_cp(total_cp)

st.write(
    f"**Total Party Currency:** {party_total['platinum']}pp, {party_total['gold']}gp, {party_total['silver']}sp, {party_total['copper']}cp"
)