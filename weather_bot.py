import requests
import json
from datetime import datetime, timedelta

# 配置資訊 (直接放在程式碼中)
TELEGRAM_TOKEN = "你的_TELEGRAM_BOT_TOKEN"
CHAT_ID = "你的_TELEGRAM_CHAT_ID"
AI_API_KEY = "sk_FvxLKDYP4nNlPdKvXju8wL753iMB3u1T"
AI_ENDPOINT = "https://gen.pollinations.ai/v1/chat/completions"

def get_weather_data():
    # 1. 獲取即時天氣 (元朗公園)
    r_current = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc")
    current_data = r_current.json()
    
    # 搵元朗公園溫度
    temp_list = current_data.get('temperature', {}).get('data', [])
    yuen_long_temp = next((item['value'] for item in temp_list if item['place'] == '元朗公園'), "未知")
    
    # 2. 獲取未來九天預報
    r_forecast = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc")
    forecast_data = r_forecast.json()
    tomorrow = forecast_data.get('weatherForecast', [])[0] # 聽日預報
    
    return {
        "current_temp": yuen_long_temp,
        "tomorrow_temp": f"{tomorrow['forecastMintemp']['value']}-{tomorrow['forecastMaxtemp']['value']}°C",
        "tomorrow_desc": tomorrow['forecastWeather'],
        "tomorrow_rh": f"{tomorrow['forecastMinrh']['value']}-{tomorrow['forecastMaxrh']['value']}%"
    }

def get_ai_suggestion(weather, is_night_mode):
    time_context = "準備聽日嘅衫" if is_night_mode else "準備今日出門口"
    prompt = f"""
    你係一個香港男仔穿衣助手。請用「地道廣東話」回覆。
    現在時間背景：{time_context}
    元朗公園現時氣溫：{weather['current_temp']}度
    聽日預測：{weather['tomorrow_temp']}, 濕度 {weather['tomorrow_rh']}, 天氣：{weather['tomorrow_desc']}

    請根據以上數據提供兩種建議：
    1. 學校 (校服清單：恤衫(夏季短/冬季長)、長褲、毛衣背心、長袖毛衣、PE風褸、校褸、底衣/褲(長/短/保暖/背心))
    2. 出街 (男仔休閒服裝)
    
    回覆要親切，直接列出建議，唔好講廢話。
    """

    models = ["gemini-fast", "openai-fast"]
    for model in models:
        try:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }
            headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
            res = requests.post(AI_ENDPOINT, json=payload, headers=headers, timeout=30)
            return res.json()['choices'][0]['message']['content']
        except:
            continue
    return "AI 暫時感冒咗，請自行根據溫度著衫。"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    # 判斷係夜晚定朝早
    hour = (datetime.now() + timedelta(hours=8)).hour # 轉為香港時間
    is_night = 18 <= hour <= 23
    
    weather = get_weather_data()
    advice = get_ai_suggestion(weather, is_night)
    
    title = "🌙 **夜晚預報：準備聽日衫物**" if is_night else "☀️ **早晨提醒：今日著咩好？**"
    full_msg = f"{title}\n\n📍 元朗公園現時：{weather['current_temp']}°C\n📅 聽日預告：{weather['tomorrow_temp']}\n☁️ 描述：{weather['tomorrow_desc']}\n\n---\n{advice}"
    
    send_telegram(full_msg)
