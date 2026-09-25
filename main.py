import os
import requests
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Yahan jis website ko track karna hai uska URL dalein
# Example ke liye ek dummy structure hai, ise apne target (e.g. UPSSSC) ke mutabiq modify karein
URL = 'https://up.gov.in/en/news' # Example URL

def get_latest_notice():
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(URL, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Yahan website ka exact HTML tag aur class dalein (Inspect karke)
    # Example: soup.find('a', class_='notice-link')
    latest_item = soup.find('a') 
    
    if latest_item:
        title = latest_item.text.strip()
        link = latest_item.get('href')
        
        # Agar link aadha hai (relative path), toh usme base URL jod dein
        if link.startswith('/'):
            link = "https://up.gov.in" + link
            
        return title, link
    return None, None

def send_telegram_alert(title, link):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    message = f"🚨 **New Job Update!**\n\n📌 {title}\n🔗 {link}"
    requests.post(api_url, json={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'})

# --- Duplicate Alert Rokne ka Logic ---
def main():
    title, link = get_latest_notice()
    
    if not link:
        print("Website se koi data nahi mila. HTML tags check karein.")
        return

    # Pehle save kiya hua link padhein
    last_link = ""
    if os.path.exists("last_link.txt"):
        with open("last_link.txt", "r") as file:
            last_link = file.read().strip()
            
    # Agar naya link purane link se alag hai, tabhi message bhejein
    if link != last_link:
        print(f"Naya update mila: {title}")
        send_telegram_alert(title, link)
        
        # Naye link ko file mein save kar dein taaki agli baar duplicate na jaye
        with open("last_link.txt", "w") as file:
            file.write(link)
    else:
        print("Koi naya update nahi hai.")

if __name__ == "__main__":
    main()
