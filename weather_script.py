import requests
import json
import datetime
import pytz
import os

# ================= 配置區 =================
TG_TOKEN = "8780856101:AAHmuoXdAi50LjceLhzdTfXh-Ju2DGlM4E4"
AI_API_KEY = "sk_FvxLKDYP4nNlPdKvXju8wL753iMB3u1T"
DEFAULT_LOCATION = "元朗公園"
DB_FILE = "subscribers.json"
# ==========================================

def log(msg):
    now = datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {msg}")

def load_subs():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return []

def save_subs(subs):
    with open(DB_FILE, 'w') as f:
        json.dump(list(set(subs)), f)

def handle_updates():
    log("檢查新訂閱者...")
    url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates"
    subs = load_subs()
    try:
        res = requests.get(url, timeout=10).json()
        if res.get("ok"):
            for up in res.get("result", []):
                chat_id = str(up.get("message", {}).get("chat", {}).get("id"))
                text = up.get("message", {}).get("text", "")
                if text == "/start" and chat_id not in subs:
                    subs.append(chat_id)
                    log(f"新訂閱者: {chat_id}")
                elif text == "/stop" and chat_id in subs:
                    subs.remove(chat_id)
                    log(f"取消訂閱: {chat_id}")
        save_subs(subs)
    except:
        log("無法檢查更新")

def get_weather_data():
    # (同之前一樣，獲取 API 數據)
    curr_data = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc").json()
    fore_data = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc").json()
    
    res = {
        "ts": datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S (%A)'),
        "temp": None, "hum": None, "warn": None, "future": None, "need_umbrella": False
    }
    
    t_list = curr_data.get('temperature', {}).get('data', [])
    res["temp"] = next((i['value'] for i in t_list if i['place'] == DEFAULT_LOCATION), 20)
    res["hum"] = curr_data.get('humidity', {}).get('data', [{}])[0].get('value', 50)
    res["warn"] = " ".join(curr_data.get('warningMessage', []))
    
    f_list = []
    for i in range(1, 4):
        f = fore_data['weatherForecast'][i]
        psr = f.get('PSR', '低')
        if psr in ['中', '中高', '高']: res["need_umbrella"] = True
        f_list.append(f"• <b>{f['forecastDate'][4:6]}/{f['forecastDate'][6:8]}</b>: {f['forecastMintemp']['value']}-{f['forecastMaxtemp']['value']}°C | 🌧️ {psr}")
    res["future"] = "\n".join(f_list)
    return res

def ask_ai(w):
    log("請求 AI 穿衣及雨具建議...")
    prompt = f"""
    你係香港男仔助手。請用地道廣東話回覆。唔好用 Markdown（禁止 * ）。
    數據：現在{w['temp']}度, 濕度{w['hum']}%, 降雨概率提醒：{'今日有機落雨' if w['need_umbrella'] else '今日唔太覺落雨'}。
    
    指令：
    1. 【學校校服】：清單限用: 恤衫(冬季長袖/夏季短袖), 長褲, 毛衣(背心/長袖), PE外套(風褸), 校褸, 底衣/褲。
       - 20度以上唔著校褸。
    2. 【出街穿搭】：休閒男仔衫。
    3. 外套決策：
       - 18度以下：必須著住。
       - 19-23度：帶定一件薄外套。
       - 24度以上：唔使外套。
    4. 雨具：如果降雨概率係中或以上，提醒「帶遮」。
    
    格式：
    【學校校服】
    (直接決定)
    【出街穿搭】
    (直接決定)
    【特別提醒】
    (雨傘/外套準備)
    """
    try:
        res = requests.post("https://gen.pollinations.ai/v1/chat/completions",
            json={"model": "gemini-fast", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}, timeout=20).json()
        return res['choices'][0]['message']['content'].strip()
    except: return "建議獲取失敗"

def send_all(text):
    subs = load_subs()
    for chat_id in subs:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

if __name__ == "__main__":
    handle_updates() # 處理 /start 同 /stop
    w = get_weather_data()
    advice = ask_ai(w)
    
    msg = f"🗓️ <b>{w['ts']}</b>\n📍 <b>{DEFAULT_LOCATION} 天氣報告</b>\n━━━━━━━━━━━━━━━\n"
    msg += f"🌡️ 現在: <b>{w['temp']}°C</b> | 💧 <b>{w['hum']}%</b>\n"
    if w['warn']: msg += f"⚠️ {w['warn']}\n"
    msg += f"━━━━━━━━━━━━━━━\n<b>🔮 未來預測:</b>\n{w['future']}\n"
    msg += f"━━━━━━━━━━━━━━━\n<b>👕 穿衣決策:</b>\n{advice}"
    
    send_all(msg)
    log("完成！")
