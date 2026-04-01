import requests
import json
import datetime
import pytz
import os

# ================= 配置區 =================
TG_TOKEN = "8780856101:AAHmuoXdAi50LjceLhzdTfXh-Ju2DGlM4E4"
AI_API_KEY = "sk_FvxLKDYP4nNlPdKvXju8wL753iMB3u1T"
DEFAULT_LOCATION = "元朗公園"
SUBSCRIBER_FILE = "subscribers.txt"
# ==========================================

def log(msg):
    now = datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {msg}")

def manage_subscribers():
    if not os.path.exists(SUBSCRIBER_FILE):
        with open(SUBSCRIBER_FILE, "w") as f: f.write("7706163480\n")
    with open(SUBSCRIBER_FILE, "r") as f:
        subs = set(line.strip() for line in f if line.strip())
    try:
        res = requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates", timeout=10).json()
        if res.get("ok"):
            for up in res.get("result", []):
                msg = up.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "").lower()
                if text == "/start": subs.add(chat_id)
                elif text == "/stop": subs.discard(chat_id)
            with open(SUBSCRIBER_FILE, "w") as f:
                for s in subs: f.write(f"{s}\n")
    except: pass
    return list(subs)

def get_uv_desc(val):
    try:
        v = float(val)
        if v <= 2: return "低"
        if v <= 5: return "中"
        if v <= 7: return "高"
        return "好鬼高"
    except: return None

def get_aqhi_desc(val):
    try:
        v = int(val)
        if v <= 3: return "清新"
        if v <= 6: return "普通"
        return "差"
    except: return None

def get_weather_data():
    curr = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc").json()
    fore = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc").json()
    aqhi = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=aqhi&lang=tc").json()
    
    w = {"ts": datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%m/%d %H:%M'),
         "temp": None, "hum": None, "warn": None, "uv": None, "aqhi": None, "future": ""}
    
    t_list = curr.get('temperature', {}).get('data', [])
    w["temp"] = next((i['value'] for i in t_list if i['place'] == DEFAULT_LOCATION), "N/A")
    w["hum"] = curr.get('humidity', {}).get('data', [{}])[0].get('value', "N/A")
    w["warn"] = " ".join(curr.get('warningMessage', []))
    uv_val = curr.get('uvindex', {}).get('data', [{}])[0].get('value')
    w["uv"] = get_uv_desc(uv_val)
    
    for item in aqhi.get('aqhi', []):
        if "元朗" in item['station']: w["aqhi"] = get_aqhi_desc(item['aqhi'])

    f_list = []
    for i in range(1, 4):
        f = fore['weatherForecast'][i]
        d = f"{f['forecastDate'][4:6]}/{f['forecastDate'][6:8]}({f['week']})"
        t = f"{f['forecastMintemp']['value']}-{f['forecastMaxtemp']['value']}°C"
        p = f.get('PSR', '未知')
        desc = f.get('forecastWeather', f.get('forecastForecast', ''))
        f_list.append(f"• <b>{d}</b>: {t} | 🌧️ {p}\n  <i>{desc}</i>")
    w["future"] = "\n".join(f_list)
    return w

def ask_ai(w):
    log("AI 決策中 (朋友口吻)...")
    prompt = f"""
    你係我一個好朋友。用地道廣東話幫我決定今日著乜，要簡單直接，唔好講「唔使著乜」，只講「要著乜」。
    
    數據：現在{w['temp']}度, 濕度{w['hum']}%, UV {w['uv']}, AQHI {w['aqhi']}, 警告 {w['warn']}
    未來：{w['future']}
    
    【學校校服】清單限定：
    恤衫(冬季長袖/夏季短袖), 長褲, 毛衣(背心/長袖), PE外套(風褸), 校褸, 底衫(長/短/保暖/背心), 打底褲(厚/薄/加薄)。
    
    規則：
    1. 任何時候都一定要喺「底衫」清單揀一件。
    2. 如果好凍，就要加「打底褲」。
    3. 20度以上用「夏季短袖恤衫」，15度以下先好提「校褸」。
    4. 睇PSR降雨概率決定帶邊種遮。
    
    【出街穿搭】：
    男仔休閒Style，唔好出現校服清單嘅字。
    
    格式：
    👕 【返學】
    (直接列出衣物)
    👟 【出街】
    (直接列出衣物)
    🌂 【記住帶】
    (遮或其他重要嘢)
    
    禁止 Markdown (*)，只准用 HTML (<b>, <i>, <u>)。唔好開場白。
    """
    
    for model in ["gemini-fast", "openai-fast"]:
        try:
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "system", "content": "你是一個說話直接的香港好朋友。"}, {"role": "user", "content": prompt}],
                    "temperature": 0.5
                }, timeout=25
            )
            return res.json()['choices'][0]['message']['content'].strip()
        except: continue
    return "執生啦朋友，連唔到 AI。"

def send_telegram(ids, text):
    for chat_id in ids:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

if __name__ == "__main__":
    try:
        user_ids = manage_subscribers()
        w = get_weather_data()
        advice = ask_ai(w)
        
        msg = f"📍 <b>{DEFAULT_LOCATION} ({w['ts']})</b>\n"
        msg += f"🌡️ <b>{w['temp']}°C</b> | 💧 <b>{w['hum']}%</b>\n"
        if w['uv']:   msg += f"☀️ UV: {w['uv']} | "
        if w['aqhi']: msg += f"😷 空氣: {w['aqhi']}\n"
        if w['warn']: msg += f"⚠️ {w['warn']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"{advice}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>🔮 未來預測:</b>\n{w['future']}\n\n"
        msg += f"<i>/stop 取消訂閱</i>"
        
        send_telegram(user_ids, msg)
        log("Done!")
    except Exception as e:
        log(f"Error: {e}")
