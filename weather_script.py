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
    except: log("訂閱更新暫時失敗")
    return list(subs)

def get_weather_data():
    curr = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc", timeout=15).json()
    fore = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc", timeout=15).json()
    
    w = {
        "ts": datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%m月%d日 %H:%M (%A)'),
        "temp": None, "hum": None, "warn": "", "uv": "", "future": ""
    }
    
    t_list = curr.get('temperature', {}).get('data', [])
    w["temp"] = next((i['value'] for i in t_list if i['place'] == DEFAULT_LOCATION), "N/A")
    w["hum"] = curr.get('humidity', {}).get('data', [{}])[0].get('value', "N/A")
    w["warn"] = " ".join(curr.get('warningMessage', []))
    
    uv_val = curr.get('uvindex', {}).get('data', [{}])[0].get('value', 0)
    w["uv"] = "高" if uv_val >= 6 else "低"

    f_list = []
    for i in range(1, 4):
        f = fore['weatherForecast'][i]
        d = f"{f['forecastDate'][4:6]}/{f['forecastDate'][6:8]}({f['week']})"
        t = f"{f['forecastMintemp']['value']}-{f['forecastMaxtemp']['value']}°C"
        p = f.get('PSR', '中')
        f_list.append(f"• <b>{d}</b>: {t} | 🌧️ {p}")
    w["future"] = "\n".join(f_list)
    return w

def ask_ai(w):
    log("AI 諗緊建議...")
    prompt = f"""
    你係我嘅好朋友。請用廣東話口語簡短建議我今日點著衫。
    
    【今日天氣數據】
    氣溫：{w['temp']}度, 濕度：{w['hum']}%, 警告：{w['warn']}, 紫外線：{w['uv']}
    未來降雨：{w['future']}
    
    【規則】
    1. 唔好講廢話，唔好講「唔使著咩」，直接講「要著咩」。
    2. 【學校校服】清單：恤衫(夏季短袖/冬季長袖), 長褲, 毛衣(背心/長袖), PE外套(風褸), 校褸, 底衫(長/短/保暖/背心), 打底褲(厚/薄/加薄)。
    3. 20度以上請選擇「夏季短袖恤衫」。
    4. 必須包含一件「底衫」。
    5. 如果落雨概率(PSR)係中/高，提醒帶遮。
    
    格式：
    【返學】
    (清單內嘅衫)
    【出街】
    (休閒衫)
    【碎碎念】
    (一句起兩句止嘅天氣/遮提醒)
    
    禁止 Markdown，只准 HTML (<b>, <i>)。
    """
    
    for model in ["gemini-fast", "openai-fast"]:
        try:
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "system", "content": "你係一個說話直接、極簡風嘅朋友。"}, {"role": "user", "content": prompt}],
                    "temperature": 0.5
                }, timeout=25
            )
            return res.json()['choices'][0]['message']['content'].strip()
        except: continue
    return "執生啦，連唔到 AI。"

def send_telegram(ids, text):
    for chat_id in ids:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

if __name__ == "__main__":
    try:
        user_ids = manage_subscribers()
        w_data = get_weather_data()
        advice = ask_ai(w_data)
        
        msg = f"🗓️ <b>{w_data['ts']}</b>\n"
        msg += f"📍 <b>{DEFAULT_LOCATION} 天氣報告</b>\n"
        msg += f"🌡️ 現在: <b>{w_data['temp']}°C</b> | 💧 <b>{w_data['hum']}%</b>\n"
        if w_data['warn']: msg += f"⚠️ {w_data['warn']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>🔮 嚟緊幾日:</b>\n{w_data['future']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>👕 今日咁著就得：</b>\n\n{advice}"
        
        send_telegram(user_ids, msg)
        log("Done!")
    except Exception as e:
        log(f"Error: {e}")
