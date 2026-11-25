# Govt Job Alert Bot (Telegram + GitHub Actions)

## Setup (10 minute)
1. Telegram par @BotFather -> /newbot -> **Bot Token** copy karo.
2. Apne bot ko ek message bhejo (ya channel mein admin banao). Chat ID ke liye @userinfobot use karo
   (channel ke liye ID `-100xxxxxxxxxx` hoti hai). Kai IDs comma se alag kar sakte ho.
3. GitHub par **Public** repo banao aur ye saari files upload karo
   (public repo mein Actions free aur unlimited hai).
4. Repo -> Settings -> Secrets and variables -> Actions -> New secret:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Actions tab -> "Govt Job Monitor" -> Run workflow. Pehli run mein sirf purane links save hote hain
   (alert nahi aate). Uske baad har 10 minute mein naye links par alert aayega.

## Test (apne computer par)
    pip install -r requirements.txt
    python monitor.py --test

## Nayi website jodna
`sources.json` mein `{"name": "...", "url": "..."}` add karo (notice/recruitment page ka URL do).
