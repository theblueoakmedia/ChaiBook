import streamlit as st
import json
import os
import shutil
from datetime import datetime
from fpdf import FPDF
import pandas as pd
import inflect
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = "data"
os.makedirs(BASE_DIR, exist_ok=True)
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
if not os.path.exists(CREDENTIALS_FILE):
    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump({"admin": {"password": os.getenv("ADMIN_PASSWORD"), "role": "admin"}}, f)

def load_json(file_path):
    return json.load(open(file_path)) if os.path.exists(file_path) else {}

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def ensure_vendor_files(vendor_id):
    path = os.path.join(BASE_DIR, vendor_id)
    os.makedirs(path, exist_ok=True)
    for fname in ["offices.json", "entries.json", "paid_status.json"]:
        fpath = os.path.join(path, fname)
        if not os.path.exists(fpath):
            save_json(fpath, {} if 'paid_status' in fname else [])
    return path

st.set_page_config(page_title="Chaibook", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None

if not st.session_state.logged_in:
    st.title("🔐 Login to Chaibook")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    creds = load_json(CREDENTIALS_FILE)

    if st.button("Login"):
        found = False
        if username in creds and creds[username]['password'] == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = creds[username]['role']
            found = True
        else:
            for vname, vinfo in creds.items():
                if vinfo['role'] != 'vendor':
                    continue
                vendor_path = ensure_vendor_files(vname)
                offices = load_json(os.path.join(vendor_path, "offices.json"))
                for office in offices:
                    if username in (office.get("email"), office.get("mobile")) and password == office.get("mobile"):
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.role = "office"
                        found = True
                        break
                if found:
                    break
        if found:
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

role = st.session_state.role
username = st.session_state.username
st.sidebar.title(f"👤 Logged in as: {username.upper()} ({role.upper()})")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.rerun()

if role == "admin":
    creds = load_json(CREDENTIALS_FILE)
    menu = st.sidebar.radio("Menu", ["Dashboard", "Add Vendor", "Manage Vendors"])

    if menu == "Dashboard":
        st.title("📊 Admin Dashboard")
        vendors = [v for v in creds if creds[v]['role'] == 'vendor']
        st.markdown("### 📌 Overview")
        col1, col2 = st.columns(2)
        col1.metric("Total Vendors", len(vendors))

        today = datetime.now()
        expiring = []
        for v in vendors:
            sub_date = creds[v].get("subscription")
            if sub_date:
                d = datetime.strptime(sub_date, "%Y-%m-%d")
                if 0 <= (d - today).days <= 7:
                    expiring.append((v, d.strftime("%d-%m-%Y")))

        col2.metric("Plans Expiring Soon", len(expiring))

        if expiring:
            st.markdown("#### ⚠️ Vendors Expiring Soon")
            for v, d in expiring:
                st.write(f"- `{v}` expiring on **{d}**")

    elif menu == "Add Vendor":
        st.title("➕ Add Vendor")
        new_user = st.text_input("Username")
        new_pass = st.text_input("Password")
        sub_date = st.date_input("Subscription End Date")
        max_offices = st.number_input("Max Offices", min_value=1, value=5)
        vendor_address = st.text_input("Vendor Address")
        if st.button("Add"):
            if new_user in creds:
                st.error("Username already exists.")
            else:
                creds[new_user] = {
                    "password": new_pass,
                    "role": "vendor",
                    "subscription": str(sub_date),
                    "max_offices": max_offices,
                    "address": vendor_address
                }
                save_json(CREDENTIALS_FILE, creds)
                st.success("Vendor added.")

    elif menu == "Manage Vendors":
        st.title("🛠 Manage Vendors")
        vendor_list = [v for v in creds if creds[v]['role'] == 'vendor']
        selected = st.selectbox("Select Vendor", vendor_list)
        if selected:
            vendor_path = ensure_vendor_files(selected)
            offices = load_json(os.path.join(vendor_path, "offices.json"))
            entries = load_json(os.path.join(vendor_path, "entries.json"))
            st.write(f"Total Offices: {len(offices)}")
            st.write(f"Total Entries: {len(entries)}")
            new_date = st.date_input("Subscription End", datetime.now())
            new_limit = st.number_input("Max Offices", min_value=1, value=creds[selected].get("max_offices", 5))
            if st.button("Update"):
                creds[selected]["subscription"] = str(new_date)
                creds[selected]["max_offices"] = new_limit
                save_json(CREDENTIALS_FILE, creds)
                st.success("Updated.")
            if st.button("Delete Vendor"):
                creds.pop(selected)
                save_json(CREDENTIALS_FILE, creds)
                shutil.rmtree(vendor_path, ignore_errors=True)
                st.success("Deleted vendor and all data.")
                st.rerun()

elif role == "vendor":
    creds = load_json(CREDENTIALS_FILE)
    vendor_path = ensure_vendor_files(username)
    offices_file = os.path.join(vendor_path, "offices.json")
    entries_file = os.path.join(vendor_path, "entries.json")
    paid_file = os.path.join(vendor_path, "paid_status.json")

    offices = load_json(offices_file)
    entries = load_json(entries_file)
    paid_status = load_json(paid_file)

    sub_date = datetime.strptime(creds[username]["subscription"], "%Y-%m-%d")
    if (sub_date - datetime.now()).days <= 7:
        st.warning(f"🔔 Your plan expires on {sub_date.strftime('%d-%m-%Y')}")

    if datetime.now() > sub_date:
        st.error("Your subscription expired.")
        st.stop()

    menu = st.sidebar.radio("Menu", ["Dashboard", "Add Office", "Manage Offices", "Tea Entry", "Tea Report"])

    if menu == "Dashboard":
        st.title("📊 Vendor Dashboard")
        st.metric("Total Offices", len(offices))
        st.metric("Total Entries", len(entries))
        st.subheader("💸 Dues per Office")
        for office in offices:
            name = office['name']
            total = sum(e['tea'] * e['tea_price'] + e['coffee'] * e['coffee_price']
                        for e in entries if e['office'] == name)
            paid = paid_status.get(name, 0)
            due = total - paid
            st.write(f"📍 {name}: Rs.{due:.2f} due | Rs.{paid:.2f} paid")

    elif menu == "Add Office":
        st.title("🏢 Add Office")
        if len(offices) >= creds[username].get("max_offices", 5):
            st.error("Office limit reached.")
        else:
            name = st.text_input("Name")
            email = st.text_input("Email")
            mobile = st.text_input("Mobile")
            if st.button("Add"):
                offices.append({"name": name, "email": email, "mobile": mobile})
                save_json(offices_file, offices)
                st.success("Office added.")

    elif menu == "Manage Offices":
        st.title("📋 Manage Offices")
        st.dataframe(pd.DataFrame(offices))

    elif menu == "Tea Entry":
        st.title("☕ Add Tea/Coffee Entry")
        office = st.selectbox("Select Office", [o['name'] for o in offices])
        tea = st.number_input("Tea", min_value=0)
        coffee = st.number_input("Coffee", min_value=0)
        tea_price = st.number_input("Tea Price", min_value=0.0)
        coffee_price = st.number_input("Coffee Price", min_value=0.0)
        date = st.date_input("Date", datetime.now())
        if st.button("Save"):
            entries.append({
                "office": office,
                "tea": tea,
                "coffee": coffee,
                "tea_price": tea_price,
                "coffee_price": coffee_price,
                "date": str(date)
            })
            save_json(entries_file, entries)
            st.success("Entry saved.")

    elif menu == "Tea Report":
        st.title("📄 Tea Report + Invoice")
        if not entries:
            st.warning("No entries.")
        else:
            office = st.selectbox("Office", list(set(e['office'] for e in entries)))
            from_date = st.date_input("From Date")
            to_date = st.date_input("To Date")
            filtered = [e for e in entries if e['office'] == office and from_date.strftime("%Y-%m-%d") <= e['date'] <= to_date.strftime("%Y-%m-%d")]
            if filtered:
                df = pd.DataFrame(filtered)
                df['amount'] = df['tea'] * df['tea_price'] + df['coffee'] * df['coffee_price']
                total = df['amount'].sum()
                st.dataframe(df[['date', 'tea', 'coffee', 'amount']])
                st.success(f"Total: Rs.{total:.2f}")

                if st.checkbox("Mark as Paid"):
                    paid_status[office] = paid_status.get(office, 0) + total
                    save_json(paid_file, paid_status)
                    st.success("Marked as paid.")
                if st.button("📥 Generate Invoice"):
                    vendor_name = username
                    vendor_data = creds.get(vendor_name, {})
                    vendor_address = vendor_data.get("address", "Address not provided")

                    # Filter office info
                    office_info = next((o for o in offices if o['name'] == office), {})
                    office_mobile = office_info.get("mobile", "N/A")
                    office_email = office_info.get("email", "N/A")

                    # Count total cups
                    df['cups'] = df['tea'] + df['coffee']
                    total_cups = int(df['cups'].sum())

                    # Start PDF
                    pdf = FPDF()
                    pdf.add_page()

                    # Header
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(190, 10, vendor_name.upper(), ln=1, align='C')

                    pdf.set_font("Arial", '', 10)
                    pdf.cell(190, 8, vendor_address, ln=1, align='C')
                    pdf.cell(190, 6, f"Mobile: {office_mobile}", ln=1, align='C')
                    pdf.ln(6)

                    # Invoice Meta
                    pdf.set_font("Arial", '', 11)
                    pdf.cell(100, 8, f"Invoice No.: 001")
                    pdf.cell(90, 8, f"Invoice Date: {datetime.now().strftime('%d/%m/%Y')}", ln=1)
                    pdf.cell(100, 8, f"Due Date: {(datetime.now() + pd.Timedelta(days=7)).strftime('%d/%m/%Y')}", ln=1)
                    pdf.ln(4)

                    # Table Headers
                    pdf.set_font("Arial", 'B', 10)
                    pdf.cell(60, 8, "ITEMS", 1)
                    pdf.cell(40, 8, "Date", 1)
                    pdf.cell(30, 8, "QTY.", 1)
                    pdf.cell(30, 8, "RATE", 1)
                    pdf.cell(30, 8, "AMOUNT", 1)
                    pdf.ln()

                    # Table Rows
                    pdf.set_font("Arial", '', 10)
                    for _, row in df.iterrows():
                        item = "TEA INDIAN CHAI"
                        date = row['date']
                        qty_str = f"{int(row['tea'] + row['coffee'])} Cups"
                        rate_str = f"{int(row['tea_price'])}"  # Assuming same price for tea/coffee
                        amt_str = f"{row['amount']:.2f}"
                        pdf.cell(60, 8, item, 1)
                        pdf.cell(40, 8, date, 1)
                        pdf.cell(30, 8, qty_str, 1)
                        pdf.cell(30, 8, rate_str, 1)
                        pdf.cell(30, 8, amt_str, 1)
                        pdf.ln()

                    # Subtotal (Total Cups)
                    pdf.ln(3)
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(60, 8, "SUBTOTAL", ln=1)
                    pdf.set_font("Arial", '', 11)
                    pdf.cell(60, 8, f"{total_cups}")
                    pdf.cell(70)
                    pdf.cell(60, 8, f"Rs.{total:.2f}", ln=1)

                    # Total Amount + Balance
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(60, 8, "TOTAL AMOUNT", ln=1)
                    pdf.set_font("Arial", '', 11)
                    pdf.cell(60, 8, "Current Balance")
                    pdf.cell(70)
                    pdf.cell(60, 8, f"Rs.{total:.2f}", ln=1)
                    pdf.ln(3)

                    # Amount in Words
                    p = inflect.engine()
                    in_words = p.number_to_words(int(total)).capitalize()
                    pdf.set_fill_color(240, 240, 240)
                    pdf.set_font("Arial", 'B', 10)
                    pdf.cell(190, 8, "Total Amount (in words)", ln=1, fill=True)
                    pdf.set_font("Arial", '', 10)
                    pdf.multi_cell(190, 8, f"{in_words} Rupees", border=1)

                    # Signature
                    pdf.ln(10)
                    pdf.set_font("Arial", '', 10)
                    pdf.cell(0, 8, "AUTHORISED SIGNATORY FOR", ln=1, align='R')
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(0, 8, vendor_name.upper(), ln=1, align='R')

                    # Save and download
                    pdf.output("invoice.pdf")
                    with open("invoice.pdf", "rb") as f:
                        st.download_button("📩 Download Invoice PDF", f, file_name=f"invoice_{office}.pdf")

elif role == "office":
    st.title("🏢 Office Dashboard")
    all_creds = load_json(CREDENTIALS_FILE)
    for v in [v for v in all_creds if all_creds[v]['role'] == 'vendor']:
        path = ensure_vendor_files(v)
        offices = load_json(os.path.join(path, "offices.json"))
        entries = load_json(os.path.join(path, "entries.json"))
        paid_status = load_json(os.path.join(path, "paid_status.json"))
        for office in offices:
            if username in (office.get("email"), office.get("mobile")):
                df = pd.DataFrame([e for e in entries if e['office'] == office['name']])
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    df['amount'] = df['tea'] * df['tea_price'] + df['coffee'] * df['coffee_price']
                    st.dataframe(df[['date', 'tea', 'coffee', 'amount']])
                    total = df['amount'].sum()
                    paid = paid_status.get(office['name'], 0)
                    due = total - paid
                    st.metric("Total Bill", f"Rs.{total:.2f}")
                    st.metric("Amount Paid", f"Rs.{paid:.2f}")
                    st.metric("Amount Due", f"Rs.{due:.2f}")
                else:
                    st.warning("No entries found.")
                break
