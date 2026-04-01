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
    print(f"[{datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def get_weather_data():
    log("獲取天文台數據...")
    try:
        curr_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc", timeout=20)
        fore_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc", timeout=20)
        curr_data = curr_res.json()
        fore_data = fore_res.json()
        
        temp_list = curr_data.get('temperature', {}).get('data', [])
        yl_temp = next((item['value'] for item in temp_list if item['place'] == DEFAULT_LOCATION), "N/A")
        humidity = curr_data.get('humidity', {}).get('data', [{}])[0].get('value', "N/A")
        warning = " ".join(curr_data.get('warningMessage', [])) or "暫無警告"
        
        forecast_list = []
        forecasts = fore_data.get('weatherForecast', [])
        for i in range(1, min(4, len(forecasts))): 
            f = forecasts[i]
            date_str = f.get('forecastDate', '00000000')
            formatted_date = f"{date_str[4:6]}/{date_str[6:8]}({f.get('week', '')})"
            t_min = f.get('forecastMintemp', {}).get('value', '??')
            t_max = f.get('forecastMaxtemp', {}).get('value', '??')
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
    log("請求 AI 決策建議...")
    prompt = f"""
    你係香港男仔穿衣助手。請用地道廣東話回覆。
    現在：{weather['temp']}度, 濕度{weather['humidity']}%, 警告:{weather['warning']}
    未來：{weather['future']}
    
    指令：
    1. 唔好畀選擇題（例如「可以著A或B」），你要幫我決定「著邊件」、「帶邊件」定係「唔使帶」。
    2. 學校校服限用清單：恤衫長/短袖, 長褲, 毛衣背心, 長袖毛衣, PE風褸, 校褸, 底衣/褲。
    3. 特別注意：校褸只有喺15度以下先會建議著。20度以上絕對唔使著。
    4. 回覆格式：禁止使用 * 或 Markdown，請直接用文字。
    
    請分為：
    【學校校服】(直接講決定)
    【出街穿搭】(直接講決定)
    """
    
    for model in ["gemini-fast", "openai-fast"]:
        try:
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是一個果斷的香港男裝顧問。回覆不使用Markdown符號，只使用純文字。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3 # 降低隨機性，令回覆更果斷
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
        
        # 組合純 HTML 訊息，確保 100% 渲染
        msg = f"<b>📍 {data['location']} 天氣提醒</b>\n"
        msg += f"🌡️ 現在: <b>{data['temp']}°C</b> | 💧 <b>{data['humidity']}%</b>\n"
        msg += f"⚠️ {data['warning']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>🔮 未來預測:</b>\n{data['future']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>👕 穿衣決策:</b>\n{advice}"
        
        send_telegram(msg)
        log("完成！")
    except Exception as e:
        log(f"最後出錯: {e}")
