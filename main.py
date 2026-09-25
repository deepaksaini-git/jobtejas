import os
import json
import requests
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
MEMORY_FILE = "last_links.json"

# Yahan aap multiple websites add kar sakte hain
# Har website ka HTML tag aur class alag hota hai, isliye wo specify karna zaroori hai
SITES_TO_TRACK = [
    {
        "name": "UPSSSC",
        "url": "https://upsssc.gov.in", # Asli URL dalein
        "tag": "a",                     # Tag jisme notice ho
        "class_name": "notice-link"     # Notice ki class (inspect karke)
    },
    {
        "name": "SSC",
        "url": "https://ssc.nic.in",
        "tag": "a",
        "class_name": "latest-link"
    },
    # Nayi website yahan aise hi add karte jayein
]

def get_latest_notice(url, tag, class_name):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Exact element dhoondhna
        latest_item = soup.find(tag, class_=class_name) if class_name else soup.find(tag)
        
        if latest_item:
            title = latest_item.text.strip()
            link = latest_item.get('href')
            
            # Relative link ko full URL mein badalna (agar zaroorat ho)
            if link and link.startswith('/'):
                base_url = "/".join(url.split("/")[:3]) # Extract domain
                link = base_url + link
                
            return title, link
    except Exception as e:
        print(f"Error checking {url}: {e}")
    return None, None

def send_telegram_alert(site_name, title, link):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    message = f"🚨 **New Update from {site_name}!**\n\n📌 {title}\n🔗 {link}"
    requests.post(api_url, json={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'})

def main():
    # Purana data load karna
    saved_links = {}
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as file:
            saved_links = json.load(file)

    updates_found = False

    # Har website ko ek-ek karke check karna
    for site in SITES_TO_TRACK:
        print(f"Checking {site['name']}...")
        title, link = get_latest_notice(site['url'], site['tag'], site.get('class_name'))
        
        if not link:
            print(f"⚠️ {site['name']} par koi data nahi mila. Tags check karein.")
            continue

        last_link = saved_links.get(site['name'], "")
        
        # Agar link naya hai
        if link != last_link:
            print(f"✅ Naya update mila {site['name']} par: {title}")
            send_telegram_alert(site['name'], title, link)
            saved_links[site['name']] = link # Naya link save kar lein
            updates_found = True
        else:
            print(f"❌ {site['name']} par koi naya update nahi hai.")

    # Agar kisi bhi site par update mila ho, toh JSON file update kar dein
    if updates_found:
        with open(MEMORY_FILE, "w") as file:
            json.dump(saved_links, file, indent=4)

if __name__ == "__main__":
    main()
