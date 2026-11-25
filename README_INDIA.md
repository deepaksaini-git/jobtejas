# Blocked sites ke liye (Indian IP) - Android Termux setup

1. F-Droid se **Termux** install karo (Play Store wala purana hai).
2. Termux mein:
       pkg update && pkg install python git -y
       pip install requests beautifulsoup4 pypdf
3. Apni repo clone karo (public hai to):
       git clone https://github.com/<username>/<repo>.git
       cd <repo>
4. Token set karke chalao:
       export TELEGRAM_BOT_TOKEN="apna_token"
       export TELEGRAM_CHAT_ID="apna_chat_id"
       termux-wake-lock
       nohup bash run_local.sh > log.txt 2>&1 &
5. Pehli run mein purane links save honge (alert nahi). Uske baad naye par alert aayega.
   Check: `tail -n 40 log.txt`

Note: phone on rahe, internet chalu rahe, battery optimisation Termux ke liye band karo.
Zyada reliable: Oracle Cloud Free Tier (Mumbai) par yahi steps Linux par chalao (termux-wake-lock hata do).

---
## Oracle Cloud par (nginx website ke saath safe)
    git clone https://github.com/<username>/<repo>.git
    cd <repo>
    bash install_oracle.sh
Ye systemd timer banata hai (har 10 min), CPU 25% aur RAM 250 MB se zyada nahi leta, aur nginx se
upar priority nahi leta. Band karne ke liye: `sudo systemctl disable --now govt-job-alert.timer`
