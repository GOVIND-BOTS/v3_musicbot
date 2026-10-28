V3 MUSIC BOT - FILE SETUP (Hindi)

1) ZIP extract karke repo ke ROOT folder me saari root files upload karein.
   Root files: bot.py, config.py, youtube.py, music.py, stream.py, buttons.py,
   thumbnails.py, requirements.txt, Dockerfile, Procfile, .gitignore

2) In folders ko bilkul isi naam se banayein:
   database/
      __init__.py
      mongodb.py
   handlers/
      __init__.py
      start.py
      play.py
      callbacks.py
      queue.py
      admin.py

3) .env.example ko rename karke .env karein, phir placeholders me apni values bharein.
   .env ko GitHub par upload/commit NA karein. .gitignore me .env excluded hai.
   Agar credentials pehle public hue the to BotFather se bot token revoke/regenerate karein
   aur assistant session ko revoke karke naya session generate karein.

4) Telegram API_ID/API_HASH my.telegram.org se; BOT_TOKEN BotFather se; MONGO_DB_URI
   MongoDB Atlas se. OWNER_ID/SUDO_USERS me apna numeric Telegram user ID dein.
   SESSION_STRING assistant/user account ka valid Pyrogram string session hona chahiye.

5) VPS par:
   sudo apt update
   sudo apt install -y python3-venv python3-pip ffmpeg
   cd /path/to/v3_musicbot
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -U pip
   pip install -r requirements.txt
   python bot.py

IMPORTANT:
- Ye initial integrated code bundle hai, production-tested release nahi. Pehle test group me try karein.
- Bot ko group me add karke admin banayein; voice chat start karein. Assistant account ko bhi
  group me add karna pad sakta hai.
- Telegram voice-chat streaming ke liye group permissions, PyTgCalls compatibility aur
  valid assistant session zaroori hain.
- YouTube playback/yt-dlp upstream changes ke kaaran kabhi fail ho sakta hai.
- .env.example ko GitHub me rakhna safe hai; actual .env ko nahi.
