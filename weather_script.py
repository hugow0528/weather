import requests
import json
import datetime
import pytz

# ================= 配置區 =================
TG_TOKEN = "8780856101:AAHmuoXdAi50LjceLhzdTfXh-Ju2DGlM4E4"
TG_CHAT_ID = "7706163480" 
AI_API_KEY = "sk_FvxLKDYP4nNlPdKvXju8wL753iMB3u1T"
DEFAULT_LOCATION = "元朗公園"
# ==========================================

def log(msg):
    now = datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {msg}")

def get_uv_desc(val):
    try:
        v = float(val)
        if v <= 2: return "低 (舒服)"
        if v <= 5: return "中等 (出街啱啱好)"
        if v <= 7: return "高 (記得查防曬)"
        if v <= 10: return "甚高 (避免曝曬)"
        return "極高 (一定要帶傘/帽)"
    except: return None

def get_aqhi_desc(val):
    try:
        v = int(val)
        if v <= 3: return "低 (空氣清新)"
        if v <= 6: return "中 (普通)"
        if v <= 7: return "高 (少做劇烈運動)"
        if v <= 10: return "甚高 (盡量留喺室內)"
        return "嚴重 (戴口罩，唔好戶外運動)"
    except: return None

def safe_get_json(url, name):
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        return res.json()
    except:
        log(f"警告: {name} 暫時無法獲取，將會跳過。")
        return None

def get_weather_data():
    curr_data = safe_get_json("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc", "即時天氣")
    fore_data = safe_get_json("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc", "九天預測")
    aqhi_data = safe_get_json("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=aqhi&lang=tc", "空氣質素")
    
    res = {
        "ts": datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S (%A)'),
        "temp": None, "hum": None, "warn": None, "uv": None, "aqhi": None, "future": None
    }

    if curr_data:
        t_list = curr_data.get('temperature', {}).get('data', [])
        res["temp"] = next((i['value'] for i in t_list if i['place'] == DEFAULT_LOCATION), None)
        res["hum"] = curr_data.get('humidity', {}).get('data', [{}])[0].get('value', None)
        w_msg = " ".join(curr_data.get('warningMessage', []))
        if w_msg: res["warn"] = w_msg
        
        uv_val = curr_data.get('uvindex', {}).get('data', [{}])[0].get('value')
        if uv_val is not None: res["uv"] = get_uv_desc(uv_val)

    if aqhi_data:
        for item in aqhi_data.get('aqhi', []):
            if "元朗" in item['station']:
                res["aqhi"] = get_aqhi_desc(item['aqhi'])

    if fore_data:
        f_list = []
        for i in range(1, 4):
            f = fore_data['weatherForecast'][i]
            d = f"{f['forecastDate'][4:6]}/{f['forecastDate'][6:8]}({f['week']})"
            t = f"{f['forecastMintemp']['value']}-{f['forecastMaxtemp']['value']}°C"
            p = f.get('PSR', '未知')
            desc = f.get('forecastWeather', f.get('forecastForecast', ''))
            f_list.append(f"• <b>{d}</b>: {t} | 🌧️ {p}\n  <i>{desc}</i>")
        res["future"] = "\n".join(f_list)

    return res

def ask_ai(w):
    log("請求 AI 穿衣建議...")
    # 只將有的數據放入 Prompt
    info = f"現在氣溫：{w['temp']}度, 濕度：{w['hum']}%"
    if w['warn']: info += f", 警告：{w['warn']}"
    if w['uv']: info += f", 紫外線：{w['uv']}"
    if w['aqhi']: info += f", 空氣質素：{w['aqhi']}"
    
    prompt = f"""
    你係香港男仔生活助手。請用地道廣東話回覆。唔好用 Markdown（禁止 * ）。
    數據：{info}
    未來三日：{w['future']}
    
    穿衣清單：恤衫長/短袖, 長褲, 毛衣背心, 長袖毛衣, PE風褸, 校褸, 底衣/褲。
    
    指令：
    1. 20度以上唔好著校褸。
    2. 格式嚴格要求：
    【學校校服】
    (具體建議)
    【出街穿搭】
    (具體建議)
    3. 果斷決定，唔好畀選擇。
    """
    
    for model in ["gemini-fast", "openai-fast"]:
        try:
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你係果斷嘅香港穿衣顧問。回覆只用 HTML 標籤 <b>, <i>。唔好有廢話。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.4
                }, timeout=20
            )
            return res.json()['choices'][0]['message']['content'].strip()
        except: continue
    return "AI 忙碌中。"

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"})

if __name__ == "__main__":
    try:
        w = get_weather_data()
        advice = ask_ai(w)
        
        # 建立訊息，如果數據係 None 就唔顯示嗰行
        msg = f"🗓️ <b>{w['ts']}</b>\n"
        msg += f"📍 <b>{DEFAULT_LOCATION} 天氣報告</b>\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        
        if w['temp'] and w['hum']:
            msg += f"🌡️ 現在: <b>{w['temp']}°C</b> | 💧 <b>{w['hum']}%</b>\n"
        
        # 只有存在數據時才顯示 UV 同 AQHI
        if w['uv']:   msg += f"☀️ 紫外線: <b>{w['uv']}</b>\n"
        if w['aqhi']: msg += f"😷 空氣質素: <b>{w['aqhi']}</b>\n"
        if w['warn']: msg += f"⚠️ {w['warn']}\n"
        
        msg += f"━━━━━━━━━━━━━━━\n"
        if w['future']:
            msg += f"<b>🔮 未來三日預測:</b>\n{w['future']}\n"
            msg += f"━━━━━━━━━━━━━━━\n"
        
        msg += f"<b>👕 穿衣決策:</b>\n{advice}"
        
        send_telegram(msg)
        log("完成！")
    except Exception as e:
        log(f"出錯: {e}")
