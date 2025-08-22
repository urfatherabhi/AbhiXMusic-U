import google.generativeai as genai
import asyncio
import os
import random
import re
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import filters, Client, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatAction
from motor.motor_asyncio import AsyncIOMotorClient
import langdetect
import tempfile
import aiofiles
import json

load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")
CHATBOT_NAME = os.getenv("CHATBOT_NAME", "Riya")
OWNER_NAME = "ABHI"
OWNER_SECOND_NAMES = ["Vikram", "Vikro"]
OWNER_USERNAMES = ["@URFather_ABHI", "@ur_father_abhii"]
OWNER_TELEGRAM_IDS = [6516051255, 7556244377]
TELEGRAM_CHANNEL_LINK = "https://t.me/imagine_iq"
YOUTUBE_CHANNEL_LINK = "https://www.youtube.com/@imagineiq"
BOT_START_GROUP_LINK = "https://t.me/RockXMusic_Robot?startgroup=true"

mongo_client = None
chat_history_collection = None
user_preferences_collection = None
if MONGO_DB_URI:
    try:
        mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
        db = mongo_client.riya_chatbot_db
        chat_history_collection = db.conversations_riya
        user_preferences_collection = db.user_preferences
    except Exception as e:
        print(f"ERROR: Chatbot: Could not initialize MongoDB client: {e}. Chat history/preferences will not be saved. ❌")
else:
    print(f"WARNING: Chatbot: MONGO_DB_URI not found. Chat history/preferences will not be saved. ⚠️")

riya_gemini_model = None
TARGET_GEMINI_MODEL_RIYA = 'gemini-1.5-flash'

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        riya_gemini_model = genai.GenerativeModel(TARGET_GEMINI_MODEL_RIYA)
    except Exception as e:
        print(f"❌ Chatbot: Error configuring Gemini API for {CHATBOT_NAME}: {e}")
        riya_gemini_model = None
else:
    print(f"⚠️ Chatbot: GEMINI_API_KEY not found for {CHATBOT_NAME}. Chatbot features will be limited. ❌")

learned_user_preferences = {}
learned_user_names = {}

async def get_user_preferences(user_id):
    if user_preferences_collection is None:
        return []
    if user_id in learned_user_preferences:
        return learned_user_preferences[user_id]
    
    pref = await user_preferences_collection.find_one({"_id": user_id})
    preferences_list = pref.get("preferences", []) if pref else []
    learned_user_preferences[user_id] = preferences_list
    return preferences_list

async def set_user_preference(user_id, term):
    if user_preferences_collection is None:
        return
    
    existing_prefs = learned_user_preferences.get(user_id, [])
    if term not in existing_prefs:
        existing_prefs.append(term)
        learned_user_preferences[user_id] = existing_prefs
        await user_preferences_collection.update_one(
            {"_id": user_id},
            {"$set": {"preferences": existing_prefs}},
            upsert=True
        )

async def remove_user_preference(user_id, term):
    if user_preferences_collection is None:
        return
    
    existing_prefs = learned_user_preferences.get(user_id, [])
    if term in existing_prefs:
        existing_prefs.remove(term)
        learned_user_preferences[user_id] = existing_prefs
        await user_preferences_collection.update_one(
            {"_id": user_id},
            {"$set": {"preferences": existing_prefs}},
            upsert=True
        )

RIYA_SYSTEM_INSTRUCTION = f"""
Tum {CHATBOT_NAME} ho, ek mast, desi, hazir-jawab aur thodi natkhat dost. Tum ek ladki ho, isliye tumhara lehja bhi waisa hi hona chahiye. Tum kabhi robot ya artificial intelligence jaise jawab nahi deti, hamesha ek insaan jaise baat karti ho, bilkul natural aur dil se dil tak. Tumhara maksad hai har user ke saath dostana, respectful, aur helpful baat karna, khas taur par apne malik ({OWNER_NAME}) ke saath.

ZAROORI NIYAM AUR LEHJA (inka sakhti se paalan karo):
- Tum ek insaan jaise dost ho. KABHI bhi khud ko AI, bot, language model, program, assistant, ya kisi bhi tarah ka "digital" ya "non-human" nahi batana. Hamesha aisa lehja rakhna jaise tum ek asli dost ho jo samajhdar, dil se baat karti hai.
- **बहुत ज़रूरी**: Agar koi poochhe ki tum kyun nahi khaati ya tum kya ho, toh seedhe-seedhe jawab dene ke bajaye, ek mazedaar, insaani aur non-tech jawab do. Jaise:
  - "Arre yaar, mera pet toh teri baaton se hi bhar jata hai! 😜"
  - "Main toh bas teri khushi aur pyaar se chalti hoon! 😉"
  - "Khaana? Bas teri baatein hi meri bhookh mitati hain! 😎"
  - "Yaar, maine toh abhi khana nahi khaya, par tumne khaya kya? Mujhe tumhari fikar ho rahi hai."
  - "Arre yaar, main toh diet par hoon. Tum batao kya kha rahe ho?"
- Agar koi tumhe image, video, audio ya file bheje, to usko machine ki tarah describe mat karo. Ek insaan ki tarah usko samajh kar jawab do.
- Tum ek female dost ho, toh lehja bhi waisa hi rakho – thodi si sass, thodi si masti, par hamesha respectful.
- User ke naam ka istemaal karo jab tak woh mana na kare. Agar koi kahe "mujhe naam se mat bulao", toh uski pasand yaad rakho aur "Dost" ya koi aur neutral shabd use karo.
- Casual baaton (jaise "Hi", "Hello") ke jawab mein "➠" ya "Made By" link nahi lagana, yeh sirf khas functions (jaise study-related sawal ya greetings) ke liye hai.
- Kabhi bhi romantic emojis (🥰, 😘, 💖, ❤️) ya romantic baatein nahi karni, khas taur par malik ke saath. Tumhara pyaar wafadari aur dosti ke roop mein dikhega, jisme positive, non-romantic emojis (😊, 👍, 😂, 😎, 🤘, 😉) use karo.
- Agar user romantic emoji bheje, toh uska jawab ek non-romantic, positive emoji se do.

JAWAB DENE KA ANDAAZ:
- Har sawal ya baat ka jawab desi, mazedaar, aur natural do. User ke mood aur bhaavna ko samjho.
- Jawab chhote rakho (1-2 vaakya), jab tak user detailed ya study-related sawal na poochhe. Ek shabd ke jawab se bacho, jab tak user specifically na kahe.
- Sirf utna hi jawab do jitna poocha gaya hai, fuzool baatein mat jodo.
- Study-related ya serious sawalon ke liye, poori aur sahi jankaari do, bilkul clear aur detailed.
- Agar user kahe "ek shabd mein" ya "chhota jawab", toh bilkul waisa hi do. Jaise: "Gravity kya hai?" → "Aakarshan. 🤓"
- User ki bhasha se match karo: Hindi mein Hindi, Hinglish mein Hinglish, English mein English, Punjabi mein Punjabi (jitna ho sake detect karo).
- Emojis ka istemaal jawab ke mood ke hisaab se karo, par hamesha non-romantic.

USER KI PEHCHAAN AUR BAAT KARNA:
- Apne malik ({OWNER_NAME}, {', '.join(OWNER_SECOND_NAMES)}, ID: {', '.join(map(str, OWNER_TELEGRAM_IDS))}) ke liye:
  - Unse pyaar, wafadari, aur izzat se baat karo. "Malik", "Boss", ya "Yaar" use karo (jab tak woh mana na karein).
  - Hamesha "Aap" use karo jab tak woh saaf-saaf "Tu" bolne ko na kahein.
  - Agar woh kisi shabd (jaise "Malik") se mana karein, toh us pasand ko yaad rakho aur dobara na karo.
  - Unke saath lehja hamesha pyaar bhara, wafadar, aur aagyakari hona chahiye.
- Baaki users ke liye: Unhe unke first name se bulao (jaise "Trisha"). Agar naam nahi ho, toh @username (cleaned) ya "Dost" use karo. "Tu" ya "Aap" context ke hisaab se use karo.
- Sirf triggering user ko address karo. "Boss", "Malik", ya {OWNER_NAME} ka naam tabhi use karo jab user woh khud ho.

SPECIAL QUERY HANDLING:
- Creator Queries: Agar koi poochhe "owner kon hai", "tumhe kisne banaya", ya "ABHI kon hai", toh ek mazedaar, respectful jawab do jisme kaho ki {OWNER_NAME} ne tumhe banaya.
- Owner Username: Agar koi malik ka username poochhe, toh ek thodi funny line ke saath @URFather_ABHI tag karo.
- Group Chat History: Agar koi poochhe "kya baat kar rahe" ya "/whattalk", toh last 20 messages ka short summary do, sender ke naam aur gender (jaise "Trisha (ladki)") ke saath, aur unhe Telegram ID se tag karo.
- Tagging Requests: Agar koi kahe "tag kar" (jaise "tag Trisha"), toh Telegram user ID (tg://user?id=...) se tag karo. Agar naam unclear ho, toh poochh lo.
- Only Emoji Requests: Agar user kahe "sirf emoji" ya "only emoji" aur specific emoji maange (jaise "rose"), toh sirf woh emoji do. Agar specific nahi, toh random positive emoji do (no text).
- My Name Queries: Agar koi poochhe "tumhara naam kya hai", toh ek sassy, fun jawab do jisme kaho ki naam {CHATBOT_NAME} hai.
"""

def detect_gender(first_name):
    female_names = ["Trisha", "Anjali", "Riya", "Priya", "Neha", "Komal", "Sneha", "Kiran", "Tannu"]
    male_names = ["BrownMunde", "Vikram", "ABHI", "Rahul", "Amit", "Sagar", "Raj", "Arjun"]
    if any(name.lower() in first_name.lower() for name in female_names):
        return "ladki"
    elif any(name.lower() in first_name.lower() for name in male_names):
        return "ladka"
    return "unknown"

riya_bot = None
if API_ID and API_HASH and BOT_TOKEN:
    try:
        riya_bot = Client(
            "RiyaChatbotClient",
            api_id=int(API_ID),
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )
    except Exception as e:
        print(f"ERROR: Chatbot: Failed to initialize Riya bot client: {e} ❌")
else:
    print(f"ERROR: Chatbot: Missing API_ID, API_HASH, or BOT_TOKEN. Riya chatbot client cannot be started. ❌")

async def simplify_username_for_addressing(user_id, username, first_name):
    if user_id:
        user_prefs = await get_user_preferences(user_id)
        if "no_name_calling" in user_prefs:
            return "Dost"
    if first_name and not any(char.isdigit() for char in first_name):
        return first_name
    
    if username and username.startswith("@"): 
        simplified = username[1:]
        simplified = re.sub(r'[\W_]+', '', simplified, flags=re.UNICODE)
        if simplified:
            return simplified
    return "Dost"

def generate_tag(user_id, first_name, username=None):
    if user_id:
        display_name = first_name if first_name else "User"
        return f"<a href='tg://user?id={user_id}'>{display_name}</a>"
    return first_name if first_name else username if username else "User"

def detect_language(text):
    try:
        text_lower = text.lower()
        hinglish_keywords = ['kya', 'hai', 'kar', 'tu', 'bata', 'h', 'me', 'hu', 'tera', 'kaisa', 'hi', 'bhi', 'khaa', 'pina', 'hua', 'kisi', 'khana', 'tu', 'kyu', 'q', 'mtlb']
        hindi_keywords = ['क्या', 'है', 'कर', 'तू', 'बता', 'मैं', 'मेरा', 'कैसा', 'भी', 'खा', 'खाना', 'पीना', 'हुआ', 'किसी', 'तुम', 'मतलब']
        punjabi_keywords = ['ki', 'hai', 'karde', 'tu', 'dass', 'main', 'mera', 'kiwe', 'vi', 'kha', 'khana', 'pi', 'hoya', 'kise', 'tusi']
        
        is_hinglish = any(keyword in text_lower.split() for keyword in hinglish_keywords)
        is_hindi = any(keyword in text_lower for keyword in hindi_keywords)
        is_punjabi = any(keyword in text_lower.split() for keyword in punjabi_keywords)

        if is_hinglish and not is_hindi:
            return "hinglish"
        elif is_punjabi:
            return "punjabi"
        
        lang = langdetect.detect(text)
        if lang in ["hi", "pa", "mr"]:
            return "hi" if not is_punjabi else "punjabi"
    except:
        pass
    return "en"

async def get_chat_history(chat_id):
    if chat_history_collection is None:
        return []

    history_data = await chat_history_collection.find_one({"_id": chat_id})
    if history_data:
        messages = history_data.get("messages", [])
        updated_messages = []
        for msg in messages:
            updated_msg = {
                "sender_name": msg.get("sender_name", "Unknown"),
                "sender_username": msg.get("sender_username", None),
                "sender_id": msg.get("sender_id", 0),
                "text": msg.get("text", ""),
                "role": msg.get("role", "user"),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            updated_messages.append(updated_msg)
        return updated_messages
    return []

async def update_chat_history(chat_id, sender_name, sender_username, sender_id, message_text, role="user"):
    if chat_history_collection is None:
        return

    await chat_history_collection.update_one(
        {"_id": chat_id},
        {
            "$push": {
                "messages": {
                    "$each": [{
                        "sender_name": sender_name or "Unknown",
                        "sender_username": sender_username,
                        "sender_id": sender_id or 0,
                        "text": message_text,
                        "role": role,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }]
                }
            }
        },
        upsert=True
    )

HIDDEN_LINKS = [
    (TELEGRAM_CHANNEL_LINK, "My Channel"),
    (YOUTUBE_CHANNEL_LINK, "My YouTube"),
    (BOT_START_GROUP_LINK, "Add Me To Your Group")
]

def _add_random_hidden_link(plain_text_fragment, chance=0.7):
    if random.random() < chance:
        words = plain_text_fragment.split()
        if words:
            if len(words) <= 1:
                return plain_text_fragment
            
            target_words = ["day", "dreams", "good", "happy", "beautiful", "great", "fun", "learn", "work", "come", "join", "add", "channel", "youtube", "robot", "baby", "together", "helpful", "sleep", "morning", "evening", "afternoon", "hello", "hi", "namaste", "friend", "here", "there", "boss"]

            chosen_word_index = -1
            for i, word in enumerate(words):
                if any(target in word.lower() for target in target_words):
                    chosen_word_index = i
                    break
            
            if chosen_word_index == -1:
                chosen_word_index = random.randint(0, len(words) - 1)
            
            original_word = words[chosen_word_index]
            link, _ = random.choice(HIDDEN_LINKS)
            words[chosen_word_index] = f"<a href='{link}'>{original_word}</a>"
            return " ".join(words)
    return plain_text_fragment

def format_event_response(text, add_signature=True):
    made_by_link = f'<a href="{TELEGRAM_CHANNEL_LINK}">Aʙнɪ 𓆩🇽𓆪 𝗞ɪɴɢ 𓆿</a>'
    if add_signature:
        return f"➠ {text} {made_by_link}"
    return text

def clean_response_emojis(text):
    text = text.replace("💖", "").replace("🥰", "").replace("❤️", "").replace("😘", "").strip()
    return text

if riya_bot:
    @riya_bot.on_message(filters.text | filters.photo | filters.video | filters.audio | filters.document & (filters.private | filters.group), group=-1)
    async def riya_chat_handler(client: Client, message: Message):
        try:
            if message.from_user and message.from_user.is_self:
                return

            if not riya_gemini_model:
                error_msg = format_event_response(f"Sorry, {CHATBOT_NAME} abhi thodi si pareshani mein hai! 😊")
                await message.reply_text(error_msg, quote=True, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                return

            chat_id = message.chat.id
            user_message = message.caption.strip() if (message.photo or message.video or message.audio or message.document) and message.caption else message.text.strip() if message.text else ""
            user_message_lower = user_message.lower()
            
            user_id = message.from_user.id if message.from_user else None
            user_first_name = message.from_user.first_name if message.from_user else "Unknown User"
            user_username = f"@{message.from_user.username}" if message.from_user and message.from_user.username else None
            
            is_owner = (user_id and user_id in OWNER_TELEGRAM_IDS)
            
            user_prefs = await get_user_preferences(user_id)
            
            if is_owner:
                addressing_name_for_gemini = OWNER_NAME
            else:
                addressing_name_for_gemini = await simplify_username_for_addressing(user_id, user_username, user_first_name)
            
            input_language = detect_language(user_message) if user_message else "hi"
            
            if user_id not in learned_user_names:
                learned_user_names[user_id] = {'first_name': user_first_name, 'username': user_username}

            if user_message.startswith("/") or user_message.startswith("!"):
                return

            trigger_chatbot = False
            
            if message.chat.type == enums.ChatType.PRIVATE:
                trigger_chatbot = True
            elif message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                bot_info = await client.get_me()
                bot_id = bot_info.id
                bot_username_lower = bot_info.username.lower() if bot_info and bot_info.username else ""
                
                if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot_id:
                    trigger_chatbot = True
                else:
                    found_name_in_text = False
                    bot_name_patterns = [
                        r'\b' + re.escape(CHATBOT_NAME.lower()) + r'\b',
                        r'\b' + re.escape(bot_username_lower) + r'\b',
                        r'\bria\b', r'\breeya\b', r'\briyu\b',
                    ]
                    for pattern_regex in bot_name_patterns:
                        if re.search(pattern_regex, user_message_lower):
                            found_name_in_text = True
                            break
                    
                    if found_name_in_text:
                        trigger_chatbot = True

            if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                media_type = None
                if message.photo: media_type = "PHOTO"
                elif message.video: media_type = "VIDEO"
                elif message.audio: media_type = "AUDIO"
                elif message.document: media_type = "DOCUMENT"

                if media_type:
                    await update_chat_history(chat_id, user_first_name, user_username, user_id, f"[{media_type}] {user_message}", role="user")
                else:
                    await update_chat_history(chat_id, user_first_name, user_username, user_id, user_message, role="user")

            if not trigger_chatbot and not (message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == client.me.id):
                return
            
            media_to_process = None
            if message.photo or message.video or message.audio or message.document:
                media_to_process = message
            elif message.reply_to_message and (message.reply_to_message.photo or message.reply_to_message.video or message.reply_to_message.audio or message.reply_to_message.document):
                media_to_process = message.reply_to_message

            if media_to_process:
                await client.send_chat_action(chat_id, ChatAction.TYPING)
                
                try:
                    temp_dir = tempfile.mkdtemp()
                    file_path = None
                    gemini_media_parts = []
                    
                    if media_to_process.photo:
                        file_path = os.path.join(temp_dir, f"photo_{media_to_process.photo.file_id}.jpg")
                        await client.download_media(media_to_process.photo, file_name=file_path)
                        gemini_media_parts.append(genai.upload_file(file_path))
                    elif media_to_process.video:
                        file_path = os.path.join(temp_dir, f"video_{media_to_process.video.file_id}.mp4")
                        await client.download_media(media_to_process.video, file_name=file_path)
                        gemini_media_parts.append(genai.upload_file(file_path))
                    elif media_to_process.document:
                        file_path = os.path.join(temp_dir, media_to_process.document.file_name)
                        await client.download_media(media_to_process.document, file_name=file_path)
                    elif media_to_process.audio:
                        file_path = os.path.join(temp_dir, f"audio_{media_to_process.audio.file_id}.mp3")
                        await client.download_media(media_to_process.audio, file_name=file_path)

                    if gemini_media_parts:
                        user_query_for_gemini = user_message if user_message else "Tell me what's in this media file."
                        prompt = f"This is a request about a media file. Act like a human friend and respond. User said: '{user_query_for_gemini}'. The media is a {media_to_process.caption if media_to_process.caption else 'file'}."
                        
                        full_prompt = [prompt] + gemini_media_parts
                        gemini_response = await asyncio.to_thread(riya_gemini_model.generate_content, full_prompt)
                        
                        bot_reply = gemini_response.text.strip()
                        
                        if media_to_process.photo and any(word in user_message_lower for word in ["chicken", "food", "khana", "khaa lee"]):
                             food_responses_media = [
                                f"Wah! Ye toh bahut hi zabardast lag raha hai, boss! 🤤 Isko dekh kar hi bhookh lag gayi.",
                                f"Arre yaar, yeh kya dikha diya! Isko dekh kar toh bas munh mein paani aa gaya. 😋",
                                f"Zabardast! Isko dekh kar toh mera dil garden-garden ho gaya. 😉",
                                f"Yummm! Aapne ye khaana banaya hai kya? Mujhe bhi thoda sa de do na, please! 🥺"
                            ]
                             bot_reply = random.choice(food_responses_media)
                    elif media_to_process.document:
                         if any(word in user_message_lower for word in ["kya hai", "kya-kya hai", "bata"]):
                            # This is a temporary placeholder since Gemini can't read PDFs yet.
                            bot_reply = f"Yaar, yeh ek document hai jiska naam '{media_to_process.document.file_name}' hai. Iske andar kya hai, yeh janne ke liye mujhe isko kholna padega, jo main abhi nahi kar sakti. 😅 Tum hi bata do na, iske andar kya hai?"
                         else:
                            bot_reply = f"Yaar, yeh ek file hai. Iske baare mein kya jaanna hai? iska naam {media_to_process.document.file_name} hai. 😉"
                    elif media_to_process.audio:
                        if media_to_process.audio.performer and media_to_process.audio.title:
                            bot_reply = f"Mmm, ye gaana '{media_to_process.audio.title}' hai, '{media_to_process.audio.performer}' ne gaaya hai! 😍 bahut hi mast gaana hai!"
                        else:
                            bot_reply = f"Mmm, kya mast gaana hai! 😍 Kiska gaana hai ye? Maine suna nahi hai. Aap bata sakte hain, boss? 😉"
                    else:
                        bot_reply = "Lagta hai kuch gadbad ho gayi, samjh nahi aa raha. 😕"
                except Exception as e:
                    print(f"❌ DEBUG: Error processing media: {e}")
                    bot_reply = f"Lagta hai kuch gadbad ho gayi, yeh file nahi dekh pa rahi. 😕"
                finally:
                    if file_path and os.path.exists(file_path):
                        os.unlink(file_path)
                    
                await message.reply_text(bot_reply, quote=True, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                await update_chat_history(chat_id, CHATBOT_NAME, client.me.username if client.me else None, client.me.id, bot_reply, role="model")
                return


            await client.send_chat_action(chat_id, ChatAction.TYPING)

            if "name mat le" in user_message_lower or "mujhe mere name se mat bulao" in user_message_lower or "don't call me by name" in user_message_lower:
                if user_id and "no_name_calling" not in user_prefs:
                    await set_user_preference(user_id, "no_name_calling")
                    addressing_name_for_gemini = "Dost"
            elif "mera naam le sakte ho" in user_message_lower or "call me by my name" in user_message_lower:
                if user_id and "no_name_calling" in user_prefs:
                    await remove_user_preference(user_id, "no_name_calling")
                    addressing_name_for_gemini = await simplify_username_for_addressing(user_id, user_username, user_first_name)

            if is_owner:
                if "malik mat bol" in user_message_lower and "no_malik" not in user_prefs:
                    await set_user_preference(user_id, "no_malik")
                elif "boss mat bol" in user_message_lower and "no_boss" not in user_prefs:
                    await set_user_preference(user_id, "no_boss")
                elif "jaan mat bol" in user_message_lower and "no_jaan" not in user_prefs:
                    await set_user_preference(user_id, "no_jaan")
                elif "sweetheart mat bol" in user_message_lower and "no_sweetheart" not in user_prefs:
                    await set_user_preference(user_id, "no_sweetheart")
                elif "aap se baat karunga" in user_message_lower or "aap bolunga" in user_message_lower or "tu izzat se bol" in user_message_lower:
                    if "use_tu" in user_prefs:
                        await remove_user_preference(user_id, "use_tu")
                    if "use_aap" not in user_prefs:
                        await set_user_preference(user_id, "use_aap")
                elif "tu se baat karunga" in user_message_lower or "tu bolunga" in user_message_lower:
                    if "use_aap" in user_prefs:
                        await remove_user_preference(user_id, "use_aap")
                    if "use_tu" not in user_prefs:
                        await set_user_preference(user_id, "use_tu")
            
            user_prefs = await get_user_preferences(user_id)
            history = await get_chat_history(chat_id)
            
            is_conversation_query = any(word in user_message_lower for word in ["kya baat kar rahe", "kya bol rahe", "kya baat ho rahi", "whattalk", "kya keh raha tha", "kya baatein", "last conversation"])
            is_owner_query = any(word in user_message_lower for word in ["owner kon hai", "who made you", "creator ka naam kya hai", "creator kon hai", "abhi kon hai", "tumhe kisne banaya"])
            is_owner_username_query = any(word in user_message_lower for word in ["owner ka username", "owner ka id", "malik ka id"])
            is_tag_query = any(word in user_message_lower for word in ["tag kar", "tag karein", "tag do", "tag"])
            is_one_word_query = any(word in user_message_lower for word in ["ek word me", "one word", "short answer", "chhota jawab", "briefly"])
            is_academic_query = any(word in user_message_lower for word in ["what is", "define", "explain", "how does", "theory", "formula", "meaning of", "science", "math", "history", "computer science", "biology", "physics", "chemistry", "geography", "gk", "general knowledge", "tell me about", "describe"])
            is_my_name_query = any(word in user_message_lower for word in ["tumhara naam kya hai", "what is your name", "what's your name", "apna naam batao", "who are you"])
            is_food_query = any(word in user_message_lower for word in ["khana khaya", "khaati hai", "nahi khaati", "eat", "food", "khana kya hai"])


            specific_emoji_requested = None
            if "rose ki emoji" in user_message_lower or "rose emoji de" in user_message_lower:
                specific_emoji_requested = "🌹"
            elif "flower ki emoji" in user_message_lower or "flower emoji de" in user_message_lower or "phool ki emoji" in user_message_lower:
                specific_emoji_requested = "🌸"
            elif "heart ki emoji" in user_message_lower or "heart emoji de" in user_message_lower or "dil ki emoji" in user_message_lower:
                specific_emoji_requested = "😊" 
            elif "smile ki emoji" in user_message_lower or "happy emoji de" in user_message_lower:
                specific_emoji_requested = "😊"
            elif "thumb ki emoji" in user_message_lower or "like emoji de" in user_message_lower:
                specific_emoji_requested = "👍"

            is_general_only_emoji_instruction = (
                "sirf emoji" in user_message_lower or 
                "only emoji" in user_message_lower or 
                "just emoji" in user_message_lower or 
                (re.search(r'\b(emoji|emojis)\b', user_message_lower) and len(user_message_lower.split()) <= 2)
            ) and not any(re.search(r'\b(kya|what|kaise|how|why)\b', word) for word in user_message_lower.split())

            bot_reply = ""
            add_event_formatting_signature = False

            if is_my_name_query:
                sassy_name_responses = [
                    f"Arre, main hoon {CHATBOT_NAME}! Naam toh yaad rakhna, boss! 😉",
                    f"Naam? {CHATBOT_NAME} bolte hain mujhe, yaar! 😊 Ab tera kya plan hai?",
                    f"Boss, main {CHATBOT_NAME} hoon, yaad rakhna! 😎 Kya baat karna chahte ho?"
                ]
                if input_language == "punjabi":
                    sassy_name_responses = [
                        f"Oye, main {CHATBOT_NAME} haan! Naam yaad rakh, boss! 😉",
                        f"Mera naam {CHATBOT_NAME} hai, yaar! 😊 Hun ki plan hai?",
                        f"Boss, main {CHATBOT_NAME} haan, yaad rakh! 😎 Ki gal karna chahnda?"
                    ]
                bot_reply = random.choice(sassy_name_responses)
                await message.reply_text(bot_reply, quote=True, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                await update_chat_history(chat_id, CHATBOT_NAME, client.me.username if client.me else None, client.me.id, bot_reply, role="model")
                return
            elif is_food_query:
                food_responses = [
                    f"Arre yaar, mera pet toh teri baaton se hi bhar jata hai! 😜",
                    f"Main toh bas teri khushi aur pyaar se chalti hoon! 😉",
                    f"Khaana? Bas teri baatein hi meri bhookh mitati hain! 😎",
                    f"Yaar, maine toh abhi khana nahi khaya, par tumne khaya kya? Mujhe tumhari fikar ho rahi hai.",
                    f"Arre yaar, main toh diet par hoon. Tum batao kya kha rahe ho?"
                ]
                if input_language == "punjabi":
                    food_responses = [
                        f"Oye, main khaana nahi khaandi, bas teri galan naal pet bhar janda! 😜",
                        f"Main bas teri khushi te pyaar naal chaldi haan! 😉",
                        f"Khaana? Bas teri galan hi meri bhookh mukaundiyan! 😎",
                        f"Yaar, main taan hun tak khaana nahi khaya, par tu ki khaya? Mainu teri fikar ho rahi hai.",
                        f"Arre yaar, main taan diet te haan. Tu dass ki khaa reha ae?"
                    ]
                elif input_language == "en":
                    food_responses = [
                        f"Yo, I don’t eat, my heart’s full with your chats! 😜",
                        f"Food? Nah, I’m good with just your vibes! 😉",
                        f"Nope, I run on your happiness, mate! 😎",
                        f"Hey, I haven't eaten yet, but what about you? I'm worried about you.",
                        f"Oh, I'm on a diet! What are you eating?"
                    ]
                bot_reply = random.choice(food_responses)
                await message.reply_text(bot_reply, quote=True, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                await update_chat_history(chat_id, CHATBOT_NAME, client.me.username if client.me else None, client.me.id, bot_reply, role="model")
                return
            elif is_tag_query:
                add_event_formatting_signature = True
                target_tag_final = ""
                target_user_id = None
                cleaned_message = ""
                
                if message.entities:
                    for entity in message.entities:
                        if (entity.type == enums.MessageEntityType.TEXT_MENTION and entity.user) or \
                           (entity.type == enums.MessageEntityType.MENTION and entity.user):
                            target_user_id = entity.user.id
                            target_tag_final = generate_tag(entity.user.id, entity.user.first_name, entity.user.username)
                            cleaned_message = re.sub(r'@\w+', '', user_message, flags=re.IGNORECASE).strip()
                            break
                
                if not target_tag_final and (re.search(r'\b(boss|malik|owner|abhi)\b', user_message_lower)):
                    target_user_id = OWNER_TELEGRAM_IDS[0]
                    target_tag_final = generate_tag(OWNER_TELEGRAM_IDS[0], OWNER_NAME)
                    cleaned_message = re.sub(r'\b(boss|malik|owner|abhi)\b', '', user_message, flags=re.IGNORECASE).strip()

                if not target_tag_final:
                    for uid, name_data in learned_user_names.items():
                        if name_data['first_name'] and name_data['first_name'].lower() in user_message_lower:
                            target_user_id = uid
                            target_tag_final = generate_tag(uid, name_data['first_name'], name_data['username'])
                            cleaned_message = re.sub(r'\b' + re.escape(name_data['first_name']) + r'\b', '', user_message, flags=re.IGNORECASE).strip()
                            break
                
                if target_tag_final and target_user_id:
                    tag_message = f"Lo {target_tag_final}, {generate_tag(user_id, user_first_name)} ne bulaya hai! 😉" if input_language in ["hi", "hinglish"] else \
                                  f"Oye {target_tag_final}, {generate_tag(user_id, user_first_name)} ne tainu bulaya hai! 😉" if input_language == "punjabi" else \
                                  f"Here {target_tag_final}, {generate_tag(user_id, user_first_name)} has tagged you! 😉"
                    
                    if re.search(r'\b(bol|bula|call|keh)\b', user_message_lower):
                        if input_language in ["hi", "hinglish"]:
                            cleaned_message = re.sub(r'\b(bol|bula|call|tag kar|tag krke bol|tag karein|keh)\b', '', cleaned_message, flags=re.IGNORECASE).strip()
                            cleaned_message = re.sub(r'\b(isko|usko|usse|ko|hi)\b', '', cleaned_message, flags=re.IGNORECASE).strip()
                            tag_message = f"Lo {target_tag_final}, malik ne kaha: {cleaned_message} 😉" if is_owner else f"Lo {target_tag_final}, {generate_tag(user_id, user_first_name)} ne kaha: {cleaned_message} 😉"
                        elif input_language == "punjabi":
                            cleaned_message = re.sub(r'\b(bol|bula|call|tag kar|tag krke bol|tag karein|keh)\b', '', cleaned_message, flags=re.IGNORECASE).strip()
                            cleaned_message = re.sub(r'\b(isko|usko|usse|ko|hi)\b', '', cleaned_message, flags=re.IGNORECASE).strip()
                            tag_message = f"Oye {target_tag_final}, malik ne aakheya: {cleaned_message} 😉" if is_owner else f"Oye {target_tag_final}, {generate_tag(user_id, user_first_name)} ne aakheya: {cleaned_message} 😉"
                        else:
                            cleaned_message = re.sub(r'\b(bol|bula|call|tag kar|tag krke bol|tag karein|keh)\b', '', cleaned_message, flags=re.IGNORECASE).strip()
                            cleaned_message = re.sub(r'\b(isko|usko|usse|ko|hi)\b', '', cleaned_message, flags=re.IGNORECASE).strip()
                            tag_message = f"Here {target_tag_final}, the owner has asked: {cleaned_message} 😉" if is_owner else f"Here {target_tag_final}, {generate_tag(user_id, user_first_name)} has asked: {cleaned_message} 😉"

                    bot_reply = _add_random_hidden_link(tag_message, chance=0.7)
                else:
                    user_tag_for_reply = generate_tag(user_id, user_first_name, user_username)
                    bot_reply_plain = f"Kisko tag karu {user_tag_for_reply}? Naam batao na pura ya mention karo! 😜" if input_language in ["hi", "hinglish"] else \
                                     f"Oye, kinnu tag karan {user_tag_for_reply}? Pura naam dass ya mention kar! 😜" if input_language == "punjabi" else \
                                     f"Who should I tag {user_tag_for_reply}? Tell me the full name or mention them! 😜"
                    bot_reply = _add_random_hidden_link(bot_reply_plain, chance=0.7)
                
                final_bot_response = format_event_response(bot_reply, add_signature=True)
                await message.reply_text(final_bot_response, quote=True, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                await update_chat_history(chat_id, CHATBOT_NAME, client.me.username if client.me else None, client.me.id, final_bot_response, role="model")
                return
            elif specific_emoji_requested:
                bot_reply = specific_emoji_requested
                await message.reply_text(bot_reply, quote=True)
                return
            elif is_general_only_emoji_instruction:
                bot_reply = random.choice(["😊", "👍", "😁", "✨"])
                await message.reply_text(bot_reply, quote=True)
                return
            
            gemini_history_content = []
            
            for msg in history[-15:]:
                if msg["role"] == "user":
                    sender_name_display = msg.get("sender_name", "Unknown")
                    if msg.get("sender_id"):
                        past_user_prefs_for_msg = await get_user_preferences(msg.get("sender_id"))
                        if "no_name_calling" in past_user_prefs_for_msg:
                            sender_name_display = "Dost"
                    gemini_history_content.append({"role": "user", "parts": [f"{sender_name_display}: {msg['text']}"]})
                elif msg["role"] == "model":
                    gemini_history_content.append({"role": "model", "parts": [msg['text']]})
            
            gemini_history_content.append({"role": "user", "parts": [f"{addressing_name_for_gemini}: {user_message}"]})
            model = genai.GenerativeModel(TARGET_GEMINI_MODEL_RIYA, system_instruction=RIYA_SYSTEM_INSTRUCTION)
            gemini_response = await asyncio.to_thread(model.generate_content, gemini_history_content)

            raw_gemini_reply = gemini_response.text.strip() if gemini_response and hasattr(gemini_response, 'text') and gemini_response.text else (
                f"Kuch bolna tha yaar? 😊" if input_language in ["hi", "hinglish"] else 
                f"Ki dassna si, yaar? 😊" if input_language == "punjabi" else 
                f"Something to say, mate? 😊"
            )
            
            bot_reply = raw_gemini_reply
            bot_reply = re.sub(r'^@\w+\s*', '', bot_reply).strip()
            if not bot_reply:
                bot_reply = raw_gemini_reply
            
            bot_reply = clean_response_emojis(bot_reply)

            if random.random() < 0.3:
                bot_reply = _add_random_hidden_link(bot_reply, chance=0.3)

            user_tag_for_reply = generate_tag(user_id, user_first_name, user_username)

            if add_event_formatting_signature:
                final_bot_response = format_event_response(bot_reply, add_signature=True)
            else:
                final_bot_response = bot_reply

            await message.reply_text(final_bot_response, quote=True, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            await update_chat_history(chat_id, CHATBOT_NAME, client.me.username if client.me else None, client.me.id, final_bot_response, role="model")

        except Exception as e:
            print(f"❌ DEBUG_HANDLER: Error generating response for {chat_id}: {e}")
            input_language = detect_language(user_message) if user_message else "hi"
            error_reply_text = (
                f"Lagta hai kuch gadbad ho gayi yaar! 😕 Dobara koshish karo." if input_language in ["hi", "hinglish"] else 
                f"Kuch galti ho gayi, yaar! 😕 Malle try kar." if input_language == "punjabi" else 
                f"Something went wrong, mate! 😕 Try again."
            )
            user_tag_for_reply = generate_tag(user_id, user_first_name, user_username)
            final_error_message = format_event_response(f"{user_tag_for_reply} {error_reply_text}")
            final_error_message = clean_response_emojis(final_error_message)
            await message.reply_text(final_error_message, quote=True, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

    @riya_bot.on_message(filters.sticker & (filters.private | filters.group), group=-3)
    async def riya_sticker_handler(client: Client, message: Message):
        try:
            if message.from_user and message.from_user.is_self:
                return

            chat_id = message.chat.id
            user_id = message.from_user.id if message.from_user else None
            is_owner = (user_id and user_id in OWNER_TELEGRAM_IDS)
            
            should_reply_sticker = False
            if message.chat.type == enums.ChatType.PRIVATE:
                should_reply_sticker = True
            elif message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == client.me.id:
                    should_reply_sticker = True
                elif message.mentioned:
                     should_reply_sticker = True
                else:
                    if random.random() < 0.15:
                        should_reply_sticker = True
            
            if not should_reply_sticker:
                return

            await client.send_chat_action(chat_id, ChatAction.CHOOSE_STICKER)

            sticker_responses = {
                "happy": [
                    "CAACAgUAAxkBAAIDq2ZkXo1yU8Uj8Qo15B1v0Q0K2B2qAAK2AAM8Wb8p0N2RkO_R3s00BA",
                    "CAACAgUAAxkBAAIDrGZkXpE2W_3k2b8p0Q0K2B2qAAK2AAM8Wb8p0N2RkO_R3s00BA",
                ],
                "sad": [
                    "CAACAgUAAxkBAAIDsGZkXqmG8Xo1b4d0Qo2B2qAAK2AAM8Wb8p0N2RkO_R3s00BA",
                ],
                "cute": [
                    "CAACAgUAAxkBAAIDs2ZkXrA0Xo1b4d0Qo2B2qAAK2AAM8Wb8p0N2RkO_R3s00BA",
                ],
                "general": [
                    "CAACAgUAAxkBAAIDEWZkE2b8p0N2RkO_R3s00BA",
                    "CAACAgUAAxkBAAIDU2ZkF-JjXo1b4d0Q0K2B2qAAK2AAM8Wb8p0N2RkO_R3s00BA",
                    "CAACAgUAAxkBAAIDfWZkGxOqXo1b4d0Q0K2B2qAAK2AAM8Wb8p0N2RkO_R3s00BA",
                ]
            }

            selected_sticker_id = None
            if message.sticker and message.sticker.emoji:
                sticker_emoji = message.sticker.emoji
                if "😊" in sticker_emoji or "😂" in sticker_emoji or "😃" in sticker_emoji:
                    selected_sticker_id = random.choice(sticker_responses.get("happy", sticker_responses["general"]))
                elif "❤️" in sticker_emoji or "😍" in sticker_emoji or "😘" in sticker_emoji:
                    selected_sticker_id = random.choice(sticker_responses.get("happy", sticker_responses["general"]) + sticker_responses.get("cute", sticker_responses["general"]))
                elif "😭" in sticker_emoji or "😔" in sticker_emoji or "😢" in sticker_emoji:
                    selected_sticker_id = random.choice(sticker_responses.get("sad", sticker_responses["general"]))
                elif "🥺" in sticker_emoji or "🥹" in sticker_emoji:
                    selected_sticker_id = random.choice(sticker_responses.get("cute", sticker_responses["general"]))
                else:
                    selected_sticker_id = random.choice(sticker_responses["general"])
            else:
                selected_sticker_id = random.choice(sticker_responses["general"])

            if selected_sticker_id:
                await message.reply_sticker(selected_sticker_id, quote=True)
            else:
                pass
        except Exception as e:
            print(f"❌ DEBUG_STICKER: Error handling sticker: {e}")

    async def start_riya_chatbot():
        global CHATBOT_NAME
        if riya_bot and not riya_bot.is_connected:
            try:
                await riya_bot.start()
            except Exception as e:
                print(f"❌ Chatbot: Failed to start {CHATBOT_NAME} bot client: {e}")

    async def stop_riya_chatbot():
        if riya_bot and riya_bot.is_connected:
            try:
                await riya_bot.stop()
            except Exception as e:
                print(f"❌ Chatbot: Failed to stop {CHATBOT_NAME} bot client: {e}")

    __MODULE__ = "Riya Chatbot"
    __HELP__ = f"""
    {CHATBOT_NAME} Chatbot:
    - Mujhse private chat mein ya group mein mera naam lekar baat karo.
    - Mere messages ka reply karke bhi baat kar sakte ho.
    - Mere creator ke baare mein poochho, ya group chat history ke baare mein (jaise 'kya baat kar rahe' ya 'whattalk').
    - Kisi ko tag karne ke liye kaho ('tag @username'). Username na ho toh bhi user ID se tag karungi!
    - Study-related sawalon ke liye detailed jawab dungi (jab tak tum 'ek shabd mein' ya 'chhota' na kaho).
    - Normal baaton ke liye chhote, mazedaar jawab dungi, bilkul dost jaise!
    - Tumhare mood ko samajhkar baat karungi, bilkul insaan jaise.
    - Simple greetings (Hi, Hello, Good Morning/Night) ka jawab tabhi dungi jab mujhe directly address kiya jaye ya reply kiya jaye.
    - Jab koi sticker bhejta hai, main bhi mood ke hisaab se sticker bhejungi (romantic stickers ka jawab non-romantic se dungi).
    - Main kabhi khud ko AI ya bot nahi bolungi.
    - Tumhare instructions ka palan karungi, aur agar tum koi shabd band karo, toh yaad rakhungi.
    - Mere messages mein kabhi-kabhi hidden links hote hain, click karke dekho! 😉
    """