from flask import Flask, request, jsonify
import threading
import time

app = Flask(__name__)
shared_data = {
    "result": None,
    "ready": threading.Event()
}

@app.route('/send_prompt', methods=['POST'])
def send_prompt():
    prompt = request.json.get("prompt")
    print(f" Prompt received: {prompt}")

    shared_data["result"] = None
    shared_data["ready"].clear()

    # Wait up to 60 seconds for the result to be filled by /return_result
    if shared_data["ready"].wait(timeout=60):
        print(" Result ready. Sending back.")
        return jsonify({"result": shared_data["result"]}), 200
    else:
        print(" Timeout. No result received.")
        return jsonify({"error": "Timeout waiting for result"}), 504

@app.route('/return_result', methods=['POST'])
def return_result():
    result = request.json.get("result")
    print(f" Result received from Automa: {result}")
    shared_data["result"] = result
    shared_data["ready"].set()
    return "Result stored", 200

if __name__ == '__main__':
    print(" Flask waiting on /send_prompt and /return_result")
    app.run(port=5005)
