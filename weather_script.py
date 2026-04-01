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
        
        # 2. 未來三日預測 (不再截斷描述)
        forecast_list = []
        forecasts = fore_data.get('weatherForecast', [])
        
        for i in range(1, min(4, len(forecasts))): 
            f = forecasts[i]
            date_str = f.get('forecastDate', '00000000')
            formatted_date = f"{date_str[4:6]}/{date_str[6:8]}({f.get('week', '')})"
            t_min = f.get('forecastMintemp', {}).get('value', '??')
            t_max = f.get('forecastMaxtemp', {}).get('value', '??')
            # 使用 sample data 中的 forecastWeather
            desc = f.get('forecastWeather', f.get('forecastForecast', '無描述'))
            
            forecast_list.append(f"• <b>{formatted_date}</b>: {t_min}-{t_max}°C\n  <i>{desc}</i>")
        
        return {
            "location": DEFAULT_LOCATION,
            "temp": yl_temp,
            "humidity": humidity,
            "warning": warning,
            "future": "\n".join(forecast_list)
        }
    except Exception as e:
        log(f"數據獲取失敗: {e}")
        raise

def ask_ai(weather):
    log("請求 AI 具體穿衣建議...")
    prompt = f"""
    你係香港男仔穿衣助手。請用「地道廣東話」回覆。
    現在：{weather['temp']}度, 濕度{weather['humidity']}%, 警告:{weather['warning']}
    未來三日預測：{weather['future']}
    
    請提供具體建議（唔好太短，要解釋原因，但唔好有開場白同廢話）：
    1. 學校校服：(必須由呢度揀: 恤衫長/短袖, 長褲, 毛衣背心, 長袖毛衣, PE風褸, 校褸, 底衣/褲)
    2. 出街穿搭：(男仔風格)
    """
    
    models = ["gemini-fast", "openai-fast"]
    for model in models:
        try:
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是一個專業的男裝穿衣顧問。回覆要直接、實用、具體。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.6
                },
                timeout=20
            )
            return res.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            log(f"Model {model} Error: {e}")
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
        
        # 重新排版，增加可讀性
        msg = f"<b>📍 {data['location']} 天氣提醒</b>\n"
        msg += f"🌡️ 現在: <b>{data['temp']}°C</b> | 💧 <b>{data['humidity']}%</b>\n"
        msg += f"⚠️ {data['warning']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>🔮 未來三日預測:</b>\n{data['future']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>👕 穿衣建議:</b>\n{advice}"
        
        send_telegram(msg)
        log("完成！")
    except Exception as e:
        log(f"最後出錯: {e}")
