
from flask import Flask, render_template, request, jsonify, send_from_directory, session
from openai import OpenAI
from datetime import datetime
import secrets
from src.agent import ZerePyAgent
import os
from pathlib import Path

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for session management
agent = None

# Static file serving
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/agent/status')
def agent_status():
    global agent
    return jsonify({
        'loaded': agent is not None,
        'name': agent.name if agent else None
    })

@app.route('/api/agent/list')
def list_agents():
    agents_dir = Path("agents")
    agents = [f.stem for f in agents_dir.glob("*.json") if f.stem not in ['general', 'example']]
    return jsonify(agents)

@app.route('/api/agent/load/<name>')
def load_agent(name):
    global agent
    try:
        agent = ZerePyAgent(name)
        return jsonify({'success': True, 'name': agent.name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/agent/start')
def start_agent():
    global agent
    if not agent:
        return jsonify({'success': False, 'error': 'No agent loaded'})
    try:
        agent.loop()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/music')
def music():
    return render_template('music.html')

@app.route('/phygital')
def phygital():
    return render_template('phygital.html')

@app.route('/conscience')
def conscience():
    return render_template('conscience.html')

@app.route('/api/transactions', methods=['POST'])
def log_transaction():
    if 'transactions' not in session:
        session['transactions'] = []

    transaction_data = request.json
    transaction_data['timestamp'] = int(time.time() * 1000) # Save current timestamp
    session['transactions'].append(transaction_data)
    return jsonify(success=True), 201

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    if 'transactions' not in session:
        session['transactions'] = []
    return jsonify(session['transactions'])

@app.route('/api/chat/history/<agent_name>')
def get_chat_history(agent_name):
    if 'chat_history' not in session:
        session['chat_history'] = {}
    return jsonify(session['chat_history'].get(agent_name, []))

@app.route('/api/chat', methods=['POST'])
def handle_chat():
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400

    try:
        client = OpenAI()
        message = request.json.get('message', '')
        current_agent = request.json.get('agent', '')

        if not message:
            return jsonify({'error': 'Message is required'}), 400
            
        # Initialize chat history for this agent if it doesn't exist
        if 'chat_history' not in session:
            session['chat_history'] = {}
        if current_agent not in session['chat_history']:
            session['chat_history'][current_agent] = []

        # Add user message to history
        session['chat_history'][current_agent].append({
            'message': message,
            'isUser': True
        })
            
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": message}
            ]
        )

        # Use loaded agent's persona, or fallback to default if no agent loaded
        system_prompt = ""
        if agent:
            system_prompt = agent._construct_system_prompt()
        else:
            # Load Luna as default personality if no agent is loaded
            try:
                default_agent = ZerePyAgent("Luna")
                system_prompt = default_agent._construct_system_prompt()
            except Exception:
                system_prompt = "You are a helpful assistant."

        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
        )

        response = completion.choices[0].message.content
        
        # Add agent response to history
        session['chat_history'][current_agent].append({
            'message': response,
            'isUser': False
        })
        session.modified = True

        # Store transaction
        if 'transactions' not in session:
            session['transactions'] = []
        
        transaction_id = len(session['transactions']) + 1
        session['transactions'].append({
            'timestamp': datetime.now().isoformat(),
            'transaction_id': f'CHAT_{transaction_id}',
            'message': response,
            'agent': current_agent,
            'blockchain_id': f'0x{secrets.token_hex(32)}'  # Simulate blockchain ID
        })
        session.modified = True
        
        return jsonify({'response': response})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
