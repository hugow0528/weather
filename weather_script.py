import requests
import json
import datetime
import pytz
import os

# ================= 配置區 =================
TG_TOKEN = "8780856101:AAHmuoXdAi50LjceLhzdTfXh-Ju2DGlM4E4"
AI_API_KEY = "sk_FvxLKDYP4nNlPdKvXju8wL753iMB3u1T"
DEFAULT_LOCATION = "元朗公園"
SUB_FILE = "subscribers.txt"
# ==========================================

def log(msg):
    now = datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {msg}")

# --- 用戶管理系統 ---
def update_subscribers():
    """透過 Telegram getUpdates 自動更新訂閱名單"""
    log("正在檢查新訂閱/取消請求...")
    if not os.path.exists(SUB_FILE):
        with open(SUB_FILE, "w") as f: f.write("7706163480\n") # 預設加入你的 ID
    
    with open(SUB_FILE, "r") as f:
        subs = set(line.strip() for line in f if line.strip())
    
    try:
        res = requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates", timeout=10).json()
        if res.get("ok"):
            for update in res.get("result", []):
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "").lower()
                
                if text == "/start":
                    subs.add(chat_id)
                elif text == "/stop":
                    if chat_id in subs: subs.remove(chat_id)
            
            with open(SUB_FILE, "w") as f:
                for s in subs: f.write(f"{s}\n")
    except Exception as e:
        log(f"更新訂閱名單失敗: {e}")
    return list(subs)

# --- 數據獲取 ---
def get_uv_desc(val):
    try:
        v = float(val)
        if v <= 2: return "低 (舒服)"
        if v <= 5: return "中等 (啱啱好)"
        if v <= 7: return "高 (要防曬)"
        return "極高 (避免曝曬)"
    except: return None

def get_aqhi_desc(val):
    try:
        v = int(val)
        if v <= 3: return "低"
        if v <= 6: return "中"
        if v <= 10: return "高 (少做劇烈運動)"
        return "嚴重"
    except: return None

def get_weather_data():
    log("獲取天氣數據...")
    curr = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc").json()
    fore = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc").json()
    aqhi = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=aqhi&lang=tc").json()
    
    res = {
        "ts": datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S (%A)'),
        "temp": None, "hum": None, "warn": None, "uv": None, "aqhi": None, "future": None
    }

    t_list = curr.get('temperature', {}).get('data', [])
    res["temp"] = next((i['value'] for i in t_list if i['place'] == DEFAULT_LOCATION), "N/A")
    res["hum"] = curr.get('humidity', {}).get('data', [{}])[0].get('value', "N/A")
    res["warn"] = " ".join(curr.get('warningMessage', []))
    
    uv_val = curr.get('uvindex', {}).get('data', [{}])[0].get('value')
    res["uv"] = get_uv_desc(uv_val)
    
    for item in aqhi.get('aqhi', []):
        if "元朗" in item['station']:
            res["aqhi"] = get_aqhi_desc(item['aqhi'])

    f_list = []
    for i in range(1, 4):
        f = fore['weatherForecast'][i]
        d = f"{f['forecastDate'][4:6]}/{f['forecastDate'][6:8]}({f['week']})"
        t = f"{f['forecastMintemp']['value']}-{f['forecastMaxtemp']['value']}°C"
        p = f.get('PSR', '未知')
        desc = f.get('forecastWeather', f.get('forecastForecast', ''))
        f_list.append(f"• <b>{d}</b>: {t} | 🌧️ {p}\n  <i>{desc}</i>")
    res["future"] = "\n".join(f_list)
    return res

# --- AI 穿衣建議 ---
def ask_ai(w):
    log("請求 AI 決策建議...")
    info = f"現在{w['temp']}度, 濕度{w['hum']}%"
    if w['warn']: info += f", 警告: {w['warn']}"
    if w['uv']: info += f", UV: {w['uv']}"
    if w['aqhi']: info += f", 空氣: {w['aqhi']}"
    
    prompt = f"""
    你係香港男仔生活助手。請用地道廣東話回覆。禁止使用 * 符號。
    
    【數據】
    現在：{info}
    未來三日：{w['future']}
    
    【指令】
    1. 決策外套：22度+有雨，你要決定係「著住」定「帶定備用」外套（PE風褸或薄外套）。校褸只有15度以下才出現。
    2. 決策雨具：根據未來三日降雨概率(PSR)，如果係「中」或以上，必須提醒帶遮。
    3. 【學校校服】清單：夏季短袖/冬季長袖恤衫, 長褲, 毛衣(背心/長袖), PE外套(風褸), 校褸, 底衣/褲。
    4. 【出街穿搭】：禁止出現校服項目，用休閒服(T-shirt, 衛衣, 褸, 牛仔褲等)。
    
    格式：
    【學校校服】
    (直接決定)
    【出街穿搭】
    (直接決定)
    【生活提醒】
    (遮/防曬/曬衫建議)
    """
    
    for model in ["gemini-fast", "openai-fast"]:
        try:
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "system", "content": "你係果斷嘅香港顧問。回覆只用 HTML 標籤 <b>, <i>。"},
                                 {"role": "user", "content": prompt}],
                    "temperature": 0.3
                }, timeout=20
            )
            return res.json()['choices'][0]['message']['content'].strip()
        except: continue
    return "AI 忙碌中。"

# --- 發送訊息 ---
def broadcast(text, user_ids):
    for uid in user_ids:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": uid, "text": text, "parse_mode": "HTML"})
    log(f"已發送給 {len(user_ids)} 位用戶。")

if __name__ == "__main__":
    try:
        user_list = update_subscribers()
        w = get_weather_data()
        advice = ask_ai(w)
        
        msg = f"🗓️ <b>{w['ts']}</b>\n"
        msg += f"📍 <b>{DEFAULT_LOCATION} 天氣報告</b>\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"🌡️ 現在: <b>{w['temp']}°C</b> | 💧 <b>{w['hum']}%</b>\n"
        if w['uv']:   msg += f"☀️ 紫外線: <b>{w['uv']}</b>\n"
        if w['aqhi']: msg += f"😷 空氣質素: <b>{w['aqhi']}</b>\n"
        if w['warn']: msg += f"⚠️ {w['warn']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>🔮 未來三日預測:</b>\n{w['future']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>👕 穿衣及生活決策:</b>\n{advice}"
        
        broadcast(msg, user_list)
        log("完成！")
    except Exception as e:
        log(f"出錯: {e}")
