import requests
import json
import datetime
import pytz

# ================= 配置區 =================
TG_TOKEN = "8780856101:AAHmuoXdAi50LjceLhzdTfXh-Ju2DGlM4E4"
TG_CHAT_ID = "7706163480"  # <--- 記得填返你嘅 Chat ID
AI_API_KEY = "sk_FvxLKDYP4nNlPdKvXju8wL753iMB3u1T"
DEFAULT_LOCATION = "元朗公園"
# ==========================================

def log(msg):
    print(f"[{datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def get_weather_data():
    log("獲取天文台數據...")
    curr_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc")
    fore_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc")
    
    curr_data = curr_res.json()
    fore_data = fore_res.json()
    
    # 1. 現時天氣
    temp_list = curr_data.get('temperature', {}).get('data', [])
    yl_temp = next((item['value'] for item in temp_list if item['place'] == DEFAULT_LOCATION), "N/A")
    humidity = curr_data.get('humidity', {}).get('data', [{}])[0].get('value', "N/A")
    warning = " ".join(curr_data.get('warningMessage', [])) or "暫無警告"
    
    # 2. 未來三日預測 (具體日期)
    forecast_list = []
    for i in range(1, 4): # 攞聽日、後日、大後日
        f = fore_data['weatherForecast'][i]
        date_str = f['forecastDate'] # YYYYMMDD
        formatted_date = f"{date_str[4:6]}/{date_str[6:8]}({f['week']})"
        t_range = f"{f['forecastMintemp']['value']}-{f['forecastMaxtemp']['value']}°C"
        desc = f['forecastForecast']
        forecast_list.append(f"• {formatted_date}: {t_range} ({desc})")
    
    return {
        "location": DEFAULT_LOCATION,
        "temp": yl_temp,
        "humidity": humidity,
        "warning": warning,
        "future": "\n".join(forecast_list)
    }

def ask_ai(weather):
    log("請求 AI 簡短建議...")
    # 嚴格限制 AI 字數及格式
    prompt = f"""
    你是香港男仔天氣助手。請用「地道廣東話」極簡短回覆。
    現在：{weather['temp']}度, 濕度{weather['humidity']}%, 警告:{weather['warning']}
    未來：{weather['future']}
    
    請分兩行回覆，每行限 30 字內：
    1. 學校：(限用:恤衫長/短袖,長褲,毛衣背心,長袖毛衣,PE風褸,校褸,底衣/褲)
    2. 出街：(男仔建議)
    不要廢話。
    """
    
    models = ["gemini-fast", "openai-fast"]
    for model in models:
        try:
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=20
            )
            return res.json()['choices'][0]['message']['content'].strip()
        except:
            continue
    return "AI 忙碌中，請自行決定。"

def send_telegram(text):
    log("發送 Telegram...")
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    # 使用 HTML 模式避免 Markdown 符號導致 render 失敗
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        log(f"失敗: {r.text}")

if __name__ == "__main__":
    try:
        data = get_weather_data()
        advice = ask_ai(data)
        
        # 組合最終訊息 (HTML 格式)
        msg = f"<b>📍 {data['location']} 天氣</b>\n"
        msg += f"🌡️ 現在: {data['temp']}°C | 💧 {data['humidity']}%\n"
        msg += f"⚠️ {data['warning']}\n\n"
        msg += f"<b>🔮 未來預測:</b>\n{data['future']}\n\n"
        msg += f"<b>👕 穿衣建議:</b>\n{advice}"
        
        send_telegram(msg)
        log("完成！")
    except Exception as e:
        log(f"出錯: {e}")
