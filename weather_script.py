import requests
import json
import datetime
import pytz
import os
import subprocess

# ================= 配置區 =================
TG_TOKEN = "8780856101:AAHmuoXdAi50LjceLhzdTfXh-Ju2DGlM4E4"
AI_API_KEY = "sk_FvxLKDYP4nNlPdKvXju8wL753iMB3u1T"
DEFAULT_LOCATION = "元朗公園"
# 你可以喺度填入你自己個 ID 作為保險名單
SUBSCRIBER_FILE = "subscribers.txt"
# ==========================================

def log(msg):
    now = datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {msg}")

# --- 訂閱管理系統 ---
def manage_subscribers():
    """從 Telegram 獲取 /start 和 /stop 指令並更新訂閱名單"""
    log("檢查訂閱更新...")
    if not os.path.exists(SUBSCRIBER_FILE):
        with open(SUBSCRIBER_FILE, "w") as f: f.write("7706163480\n") # 預設加入你的 ID

    with open(SUBSCRIBER_FILE, "r") as f:
        subs = set(line.strip() for line in f if line.strip())

    # 獲取 Telegram 更新
    updates_url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates"
    try:
        res = requests.get(updates_url, timeout=10).json()
        if res.get("ok"):
            for up in res.get("result", []):
                msg = up.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "").lower()
                
                if text == "/start":
                    subs.add(chat_id)
                elif text == "/stop":
                    subs.discard(chat_id)
            
            # 寫回檔案
            with open(SUBSCRIBER_FILE, "w") as f:
                for s in subs: f.write(f"{s}\n")
    except Exception as e:
        log(f"訂閱更新出錯: {e}")
    
    return list(subs)

# --- 天氣數據抓取 ---
def get_uv_desc(val):
    try:
        v = float(val)
        if v <= 2: return "低 (曬唔傷)"
        if v <= 5: return "中等 (出街啱啱好)"
        if v <= 7: return "高 (要做足防曬)"
        return "甚高/極高 (避免長時間戶外)"
    except: return None

def get_aqhi_desc(val):
    try:
        v = int(val)
        if v <= 3: return "清新"
        if v <= 6: return "普通"
        if v >= 7: return "衰咗 (空氣差，少做運動)"
        return "普通"
    except: return None

def safe_get_json(url, name):
    try:
        res = requests.get(url, timeout=15)
        return res.json()
    except:
        log(f"警告: {name} 獲取失敗")
        return None

def get_weather_data():
    curr = safe_get_json("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc", "即時天氣")
    fore = safe_get_json("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc", "預測")
    aqhi = safe_get_json("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=aqhi&lang=tc", "空氣質素")
    
    w = {
        "ts": datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%m月%d日 %H:%M (%A)'),
        "temp": None, "hum": None, "warn": None, "uv": None, "aqhi": None, "future": ""
    }
    
    if curr:
        t_list = curr.get('temperature', {}).get('data', [])
        w["temp"] = next((i['value'] for i in t_list if i['place'] == DEFAULT_LOCATION), None)
        w["hum"] = curr.get('humidity', {}).get('data', [{}])[0].get('value', None)
        w["warn"] = " ".join(curr.get('warningMessage', []))
        uv_val = curr.get('uvindex', {}).get('data', [{}])[0].get('value')
        w["uv"] = get_uv_desc(uv_val)
        
    if aqhi:
        for item in aqhi.get('aqhi', []):
            if "元朗" in item['station']: w["aqhi"] = get_aqhi_desc(item['aqhi'])

    if fore:
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

# --- AI 決策 ---
def ask_ai(w):
    log("AI 正在思考 (人性化建議)...")
    prompt = f"""
    你係一個貼心嘅大佬，幫細佬打點天氣同著衫。請用地道廣東話回覆，語氣要親切、果斷。
    
    【今日數據】
    氣溫：{w['temp']}度, 濕度：{w['hum']}%
    紫外線：{w['uv']}, 空氣質素：{w['aqhi']}, 警告：{w['warn'] or '無'}
    未來三日預測：{w['future']}
    
    【指令】
    1. 【學校校服】：只能從清單揀 (恤衫(夏季短袖/冬季長袖), 長褲, 毛衣(背心/長袖), PE外套(風褸), 校褸, 底衣/褲)。
    2. 【出街穿搭】：男仔休閒服，禁止出現校服字眼。
    3. 人性化判斷：
       - 外套：唔好只係講「著外套」，你要話我知「係咪涼到要著住行」，定係「帶定入書包預備」。
       - 遮：睇降雨概率(PSR)。如果「高/中高」就必帶長遮；「中」就帶縮骨遮；「低」就唔使帶。
       - 校褸：15度以下先著，20度以上絕對唔准提校褸。
    
    格式：
    【學校校服】
    (建議內容)
    【出街穿搭】
    (建議內容)
    【大佬溫馨提示】
    (關於遮同埋今日最重要嘅一句話)
    
    禁止使用 Markdown (*)，只可用 HTML (<b>, <i>)。
    """
    
    for model in ["gemini-fast", "openai-fast"]:
        try:
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "system", "content": "你係一個果斷且人性化嘅香港大佬助理。"}, {"role": "user", "content": prompt}],
                    "temperature": 0.6
                }, timeout=25
            )
            return res.json()['choices'][0]['message']['content'].strip()
        except: continue
    return "大佬今日好忙，自己睇住辦啦！"

def send_telegram(ids, text):
    log(f"發送訊息給 {len(ids)} 個訂閱者...")
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
        msg += f"━━━━━━━━━━━━━━━\n"
        if w_data['temp']: msg += f"🌡️ 現在: <b>{w_data['temp']}°C</b> | 💧 <b>{w_data['hum']}%</b>\n"
        if w_data['uv']:   msg += f"☀️ 紫外線: <b>{w_data['uv']}</b>\n"
        if w_data['aqhi']: msg += f"😷 空氣質素: <b>{w_data['aqhi']}</b>\n"
        if w_data['warn']: msg += f"⚠️ {w_data['warn']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>🔮 未來三日預測:</b>\n{w_data['future']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>👕 大佬嘅穿衣決策:</b>\n{advice}\n\n"
        msg += f"<i>(回覆 /stop 取消訂閱)</i>"
        
        send_telegram(user_ids, msg)
        log("所有任務完成！")
        
    except Exception as e:
        log(f"嚴重錯誤: {e}")
