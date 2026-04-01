import requests
import json
import datetime
import pytz

# ================= 配置區 =================
TG_TOKEN = "8780856101:AAHmuoXdAi50LjceLhzdTfXh-Ju2DGlM4E4"
TG_CHAT_ID = "7706163480"  # <--- 記得填返
AI_API_KEY = "sk_FvxLKDYP4nNlPdKvXju8wL753iMB3u1T"
DEFAULT_LOCATION = "元朗公園"
# ==========================================

def log(msg):
    print(f"[{datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def get_weather_data():
    log("獲取天文台數據...")
    try:
        curr_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc", timeout=20)
        fore_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc", timeout=20)
        
        curr_data = curr_res.json()
        fore_data = fore_res.json()
        
        # 1. 現時天氣
        temp_list = curr_data.get('temperature', {}).get('data', [])
        yl_temp = next((item['value'] for item in temp_list if item['place'] == DEFAULT_LOCATION), "N/A")
        humidity = curr_data.get('humidity', {}).get('data', [{}])[0].get('value', "N/A")
        warning = " ".join(curr_data.get('warningMessage', [])) or "暫無警告"
        
        # 2. 未來三日預測 (加入容錯處理)
        forecast_list = []
        forecasts = fore_data.get('weatherForecast', [])
        
        # 攞嚟緊 3 日 (由 index 1 開始係聽日)
        for i in range(1, min(4, len(forecasts))): 
            f = forecasts[i]
            date_str = f.get('forecastDate', '00000000')
            formatted_date = f"{date_str[4:6]}/{date_str[6:8]}({f.get('week', '')})"
            
            # 兼容不同版本的 API Key Name
            t_min = f.get('forecastMintemp', {}).get('value', '??')
            t_max = f.get('forecastMaxtemp', {}).get('value', '??')
            # 優先試 forecastForecast，唔得就試 forecastWeather
            desc = f.get('forecastForecast', f.get('forecastWeather', '無天氣描述'))
            
            forecast_list.append(f"• {formatted_date}: {t_min}-{t_max}°C ({desc[:15]}...)")
        
        return {
            "location": DEFAULT_LOCATION,
            "temp": yl_temp,
            "humidity": humidity,
            "warning": warning,
            "future": "\n".join(forecast_list) if forecast_list else "暫無預測數據"
        }
    except Exception as e:
        log(f"API 解析失敗: {e}")
        raise

def ask_ai(weather):
    log("請求 AI 極簡建議...")
    prompt = f"""
    你是香港男仔天氣助手。請用「地道廣東話」回覆。
    現在：{weather['temp']}度, 濕度{weather['humidity']}%, 警告:{weather['warning']}
    未來：{weather['future']}
    
    請只回覆兩行，每行限 25 字內：
    學校：(建議校服項目)
    出街：(建議穿搭)
    不要開場白。
    """
    
    models = ["gemini-fast", "openai-fast"]
    for model in models:
        try:
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5
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
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        log(f"TG 發送失敗: {r.text}")

if __name__ == "__main__":
    try:
        data = get_weather_data()
        advice = ask_ai(data)
        
        # 組合 HTML 訊息
        msg = f"<b>📍 {data['location']} 天氣提醒</b>\n"
        msg += f"🌡️ 現在: {data['temp']}°C | 💧 {data['humidity']}%\n"
        msg += f"⚠️ {data['warning']}\n\n"
        msg += f"<b>🔮 未來預測:</b>\n{data['future']}\n\n"
        msg += f"<b>👕 穿衣建議:</b>\n{advice}"
        
        send_telegram(msg)
        log("腳本運行成功！")
    except Exception as e:
        log(f"最終錯誤: {e}")
