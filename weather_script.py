import requests
import json
import datetime
import pytz

# ================= 配置區 =================
TG_TOKEN = "8780856101:AAHmuoXdAi50LjceLhzdTfXh-Ju2DGlM4E4"
TG_CHAT_ID = "7706163480" # <--- 填入你啱啱攞到嘅 Chat ID
AI_API_KEY = "sk_FvxLKDYP4nNlPdKvXju8wL753iMB3u1T"
DEFAULT_LOCATION = "元朗公園"
# ==========================================

def log(msg):
    print(f"[{datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def get_weather_data():
    log("正在從香港天文台獲取即時數據...")
    curr_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc")
    
    log("正在獲取九天預測數據...")
    fore_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc")
    
    curr_data = curr_res.json()
    fore_data = fore_res.json()
    
    # 提取元朗公園溫度
    temp_list = curr_data.get('temperature', {}).get('data', [])
    yl_temp = next((item['value'] for item in temp_list if item['place'] == DEFAULT_LOCATION), "未知")
    
    humidity = curr_data.get('humidity', {}).get('data', [{}])[0].get('value', "未知")
    warning = curr_data.get('warningMessage', "目前無特別警告")
    
    # 提取今日/聽日預測
    forecast = fore_data.get('weatherForecast', [])[0] # 攞最近嗰一日嘅預測
    
    return {
        "location": DEFAULT_LOCATION,
        "temp": yl_temp,
        "humidity": humidity,
        "warning": warning,
        "forecast_desc": forecast.get('forecastForecast', ''),
        "forecast_temp": f"{forecast.get('forecastMintemp', {}).get('value')} - {forecast.get('forecastMaxtemp', {}).get('value')}°C"
    }

def ask_ai(weather):
    log("正在向 AI 請求穿衣建議...")
    prompt = f"""
    你係一個香港男仔穿衣助手。請用地道廣東話回覆。
    
    【當前天氣 - {weather['location']}】
    氣溫：{weather['temp']}°C
    濕度：{weather['humidity']}%
    警告：{weather['warning']}
    
    【未來預測】
    預測概況：{weather['forecast_desc']}
    預測氣溫：{weather['forecast_temp']}
    
    請根據以上資料，考慮埋未來天氣變化，分兩部分建議：
    1. 學校校服 (清單限制：恤衫長/短袖、長褲、毛衣背心、長袖毛衣、PE風褸、校褸、底衣/底褲(長/短/保暖/背心))。
    2. 出街休閒 (男仔風格)。
    """
    
    models = ["gemini-fast", "openai-fast"]
    for model in models:
        try:
            log(f"嘗試使用模型: {model}")
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
            return res.json()['choices'][0]['message']['content']
        except Exception as e:
            log(f"模型 {model} 發生錯誤: {str(e)}")
            continue
    return "AI 暫時罷工，請自行決定穿衣。"

def send_telegram(text):
    log("正在發送訊息至 Telegram...")
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    r = requests.post(url, json=payload)
    if r.status_code == 200:
        log("發送成功！")
    else:
        log(f"發送失敗: {r.text}")

if __name__ == "__main__":
    try:
        data = get_weather_data()
        advice = ask_ai(data)
        
        final_msg = f"📍 *{data['location']} 天氣提醒*\n"
        final_msg += f"🌡️ 現在：{data['temp']}°C | 💧 {data['humidity']}%\n"
        final_msg += f"🔮 預測：{data['forecast_temp']}\n"
        final_msg += f"⚠️ {data['warning']}\n\n"
        final_msg += f"{advice}"
        
        send_telegram(final_msg)
    except Exception as e:
        log(f"程式運行出錯: {str(e)}")
