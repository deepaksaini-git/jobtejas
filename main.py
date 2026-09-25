import os
import requests

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

print("Checking Secrets...")
if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
    print("❌ Error: Token ya Chat ID nahi mila. GitHub Secrets check karein.")
else:
    print("✅ Secrets mil gaye. Message bhej rahe hain...")

def send_test_message():
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    message = "🚨 Test Alert: GitHub Actions aur Telegram Bot bilkul sahi connect ho gaye hain!"
    
    # Telegram API ko request bhejna
    response = requests.post(api_url, json={'chat_id': CHAT_ID, 'text': message})
    
    # Error ya success dekhne ke liye print karna
    print("Telegram Response:", response.text)

send_test_message()
