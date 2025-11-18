import streamlit as st
import requests
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import yagmail
from serpapi import GoogleSearch

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Outreach Automation",
    page_icon="🚀",
    layout="wide"
)

# ==================== HEADER ====================
st.title("Outreach Automation")
st.markdown("---")

# ==================== SIDEBAR CONFIG ====================
with st.sidebar:
    st.header("⚙️ Configuration")
    
    sender_email = st.text_input("Gmail Address", value="mishitamaggo23@gmail.com")
    sender_password = st.text_input("Gmail App Password", type="djpshvfjlyorviuu")
    spreadsheet_name = st.text_input("Google Sheet Name", value="Outreach Log")
    serpapi_key = st.text_input("SerpAPI Key", value="b2696f69e610d46016664216366411e1034347b6712f0119919e7b351ed12013")
    
    st.markdown("---")
    
    search_query = st.text_input("Search Query", value="UAE brands")
    num_results = st.slider("Number of Brands", 1, 20, 5)
    
    st.markdown("---")
    
    # Upload credentials
    credentials_file = st.file_uploader("Upload credentials.json", type=['json'])
    
    if credentials_file:
        with open("credentials.json", "wb") as f:
            f.write(credentials_file.getbuffer())
        st.success("✅ Credentials uploaded!")

# ==================== MAIN AREA ====================

# Stats dashboard
col1, col2, col3, col4 = st.columns(4)

# Try to load existing stats
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open(spreadsheet_name).sheet1
    data = sheet.get_all_records()
    
    total_brands = len(data)
    emails_sent = len([r for r in data if r.get('Status') == 'Sent'])
    follow_ups = len([r for r in data if r.get('Follow Up')])
    
    with col1:
        st.metric("Total Brands", total_brands)
    with col2:
        st.metric("Emails Sent", emails_sent)
    with col3:
        st.metric("Follow-ups", follow_ups)
    with col4:
        st.metric("Success Rate", f"{int(emails_sent/max(total_brands,1)*100)}%")
        
except Exception as e:
    with col1:
        st.metric("Total Brands", 0)
    with col2:
        st.metric("Emails Sent", 0)
    with col3:
        st.metric("Follow-ups", 0)
    with col4:
        st.metric("Success Rate", "0%")

st.markdown("---")

# ==================== AUTOMATION FUNCTIONS ====================

def scrape_potential_clients(query, num_results):
    """Find brands using SerpAPI"""
    try:
        params = {
            "q": query,
            "num": num_results,
            "api_key": serpapi_key,
            "engine": "google"
        }
        
        search = GoogleSearch(params)
        results_data = search.get_dict()
        organic_results = results_data.get("organic_results", [])
        
        brands = []
        for result in organic_results:
            url = result.get('link', '')
            skip_domains = ['facebook.com', 'instagram.com', 'linkedin.com', 
                          'youtube.com', 'twitter.com', 'wikipedia.org']
            
            if any(domain in url.lower() for domain in skip_domains):
                continue
            
            brands.append({
                'name': result.get('title', 'Unknown')[:50],
                'url': url,
                'emails': [],
                'social_links': {},
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return brands
    except Exception as e:
        st.error(f"Error scraping: {e}")
        return []

def extract_emails(url):
    """Extract emails from website"""
    emails = set()
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=10, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for a in soup.find_all('a', href=lambda x: x and x.startswith('mailto:')):
            emails.add(a['href'][7:].split('?')[0])
        
        email_pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        emails.update(re.findall(email_pattern, response.text))
        
        filtered = [e for e in emails if not any(x in e.lower() for x in ['example', 'test@', 'noreply'])]
        return list(filtered)[:2]
    except:
        return []

def find_social_links(url):
    """Find social media profiles"""
    socials = {}
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if "instagram.com/" in href and 'instagram' not in socials:
                socials['instagram'] = a['href']
            elif "facebook.com/" in href and 'facebook' not in socials:
                socials['facebook'] = a['href']
        return socials
    except:
        return {}

def personalize_email(brand):
    """Create personalized email"""
    company_name = brand['name'].split('|')[0].strip() if '|' in brand['name'] else brand['name']
    has_instagram = 'instagram' in brand.get('social_links', {})
    
    if has_instagram:
        opening = f"I came across your Instagram profile while researching e-commerce brands in the UAE."
        insight = "I noticed there's potential to increase your Instagram engagement through strategic Reels."
    else:
        opening = f"I found your business online and was impressed by what you're building."
        insight = "I noticed you could benefit from a stronger Instagram presence to reach high-intent buyers."
    
    return f"""Hi,

{opening}

{insight}

I specialize in helping e-commerce brands like yours grow through:

→ Instagram Reels that drive traffic & sales
→ Content strategies based on trending formats
→ Consistent posting schedules

I'd love to offer you a complimentary social media audit with 3-5 actionable recommendations.

Would you be open to a quick 15-minute call this week?

Best Regards,
Mishita
Genixovate
"""

def send_email_and_log(brand, recipient_email, sheet):
    """Send email and log to sheet"""
    try:
        yag = yagmail.SMTP(sender_email, sender_password)
        email_body = personalize_email(brand)
        
        yag.send(
            to=recipient_email,
            subject="Quick question about your social media",
            contents=email_body
        )
        
        if sheet:
            ig_link = brand.get('social_links', {}).get('instagram', 'None')
            sheet.append_row([
                brand['name'],
                brand['url'],
                recipient_email,
                ig_link,
                'Sent',
                brand['timestamp'],
                ''
            ])
        
        return True
    except Exception as e:
        st.error(f"Email error: {e}")
        return False

# ==================== RUN CAMPAIGN BUTTON ====================

if st.button("🚀 Start Campaign", type="primary", use_container_width=True):
    
    if not sender_email or not sender_password:
        st.error("Please enter email credentials in the sidebar!")
    elif not credentials_file:
        st.error("Please upload credentials.json in the sidebar!")
    else:
        # Setup sheet
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            client = gspread.authorize(creds)
            sheet = client.open(spreadsheet_name).sheet1
            
            if sheet.row_count == 0 or sheet.cell(1, 1).value != 'Brand Name':
                sheet.insert_row(['Brand Name', 'URL', 'Email', 'Instagram', 'Status', 'Timestamp', 'Follow Up'], 1)
        except Exception as e:
            st.error(f"Sheet setup error: {e}")
            st.stop()
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Find brands
        status_text.text("🔍 Searching for brands...")
        brands = scrape_potential_clients(search_query, num_results)
        
        if not brands:
            st.error("No brands found!")
            st.stop()
        
        st.success(f"✓ Found {len(brands)} brands")
        
        # Process each brand
        results_container = st.container()
        
        for idx, brand in enumerate(brands):
            progress = (idx + 1) / len(brands)
            progress_bar.progress(progress)
            status_text.text(f"Processing {idx + 1}/{len(brands)}: {brand['name']}")
            
            with results_container:
                with st.expander(f"📌 {brand['name']}", expanded=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**URL:** {brand['url']}")
                        
                        # Extract emails
                        st.write("🔍 Extracting emails...")
                        brand['emails'] = extract_emails(brand['url'])
                        if brand['emails']:
                            st.success(f"✓ Found: {', '.join(brand['emails'])}")
                        else:
                            st.warning("⚠ No emails found")
                    
                    with col2:
                        # Find social
                        st.write("🔍 Finding social media...")
                        brand['social_links'] = find_social_links(brand['url'])
                        if brand['social_links']:
                            for platform, link in brand['social_links'].items():
                                st.success(f"✓ {platform.title()}: {link}")
                        else:
                            st.warning("⚠ No social profiles found")
                    
                    # Send email
                    if brand['emails']:
                        st.write("📧 Sending email...")
                        if send_email_and_log(brand, brand['emails'][0], sheet):
                            st.success("✅ Email sent successfully!")
                        else:
                            st.error("❌ Failed to send email")
                        time.sleep(2)
            
        progress_bar.progress(1.0)
        status_text.text("✅ Campaign completed!")
        st.balloons()

# ==================== VIEW LOG ====================

st.markdown("---")
st.subheader("📊 Recent Campaigns")

if st.button("🔄 Refresh Log"):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open(spreadsheet_name).sheet1
        data = sheet.get_all_records()
        
        if data:
            st.dataframe(data, use_container_width=True)
        else:
            st.info("No campaigns yet. Start one above!")
    except Exception as e:
        st.error(f"Error loading log: {e}")
