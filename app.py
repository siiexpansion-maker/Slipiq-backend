from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests
import os

app = Flask(__name__)
CORS(app)

# Rate limiter — 20 requests per day per IP
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "mistralai/mistral-7b-instruct:free"

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/analyze", methods=["POST"])
@limiter.limit("20 per day")
def analyze():
    if not OPENROUTER_API_KEY:
        return jsonify({"error": "Server misconfigured: missing API key"}), 500

    data = request.get_json()
    if not data or "prompt" not in data:
        return jsonify({"error": "Missing prompt in request body"}), 400

    prompt = data["prompt"]

    # Basic prompt length guard
    if len(prompt) > 4000:
        return jsonify({"error": "Prompt too long"}), 400

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://slipiq.netlify.app",
                "X-Title": "SlipIQ"
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 1200
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        return jsonify({"result": content})

    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timed out. Try again."}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"OpenRouter error: {str(e)}"}), 502

@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({
        "error": "Daily limit reached (20 analyses/day). Come back tomorrow!"
    }), 429

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
