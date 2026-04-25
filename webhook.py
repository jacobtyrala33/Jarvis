import os
import requests
import logging
from flask import Flask, request, jsonify

VERIFY_TOKEN      = os.environ["VERIFY_TOKEN"]
WHATSAPP_TOKEN    = os.environ["WHATSAPP_TOKEN"]
PHONE_NUMBER_ID   = os.environ["PHONE_NUMBER_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
YOUR_NUMBER       = "353858105294"

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text[:4000]}}
    try:
        r = requests.post(url, headers=headers, json=data, timeout=10)
        r.raise_for_status()
        logging.info("WhatsApp sent OK")
    except requests.exceptions.RequestException as e:
        logging.error(f"WhatsApp error: {e}")

def ask_claude(message):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    data = {
        "model": "claude-haiku-4-5",
        "max_tokens": 500,
        "system": "You are Jarvis, an AI assistant that controls a Windows computer via WhatsApp. When the user asks you to open apps, play music, search the web, or do anything on their computer, confirm you are doing it and respond with: TASK: followed by the instruction. Keep replies short.",
        "messages": [{"role": "user", "content": message}]
    }
    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)
        logging.info(f"Claude status: {r.status_code}")
        logging.info(f"Claude response: {r.text}")
        if r.status_code == 200:
            result = r.json()
            if "content" in result and len(result["content"]) > 0:
                return result["content"][0].get("text", "No response")
        return "AI error. Try again!"
    except Exception as e:
        logging.error(f"Claude error: {e}")
        return "Error contacting AI. Try again!"

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def receive():
    data = request.get_json()
    logging.info(f"Incoming: {data}")
    try:
        value = data["entry"][0]["changes"][0]["value"]
        messages = value.get("messages", [])
        if not messages:
            return jsonify({"status": "ignored"}), 200
        msg = messages[0]
        from_number = msg.get("from", "")
        logging.info(f"From: {from_number}, Expected: {YOUR_NUMBER}")
        if from_number.replace("+", "") != YOUR_NUMBER.replace("+", ""):
            return jsonify({"status": "ignored"}), 200
        if msg.get("type") == "text":
            text = msg["text"]["body"]
            logging.info(f"Message: {text}")
            reply = ask_claude(text)
            send_whatsapp_message(from_number, reply)
    except Exception as e:
        logging.error(f"Error: {e}")
    return jsonify({"status": "ok"}), 200

@app.route("/")
def home():
    return "Jarvis is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
