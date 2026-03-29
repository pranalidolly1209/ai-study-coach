from flask import Flask, request, jsonify, send_file
import sqlite3
import requests
import os
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

# ---------------- GEMINI API KEY ----------------
API_KEY = os.getenv("API_KEY")  # Set this in environment, DO NOT hardcode
if not API_KEY:
    print("⚠️ WARNING: API_KEY not set! Gemini API calls will fail.")

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, goal TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, task TEXT)')
    conn.commit()
    conn.close()

init_db()

# ---------------- CLEAN TEXT ----------------
def clean_text(text):
    for ch in ["*", "**", "•","#","##","###"]:
        text = text.replace(ch, "")
    return text

# ---------------- GEMINI API CALL ----------------
def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"
    data = {"contents":[{"parts":[{"text":prompt}]}]}
    try:
        res = requests.post(url, json=data)
        result = res.json()
        if "candidates" not in result:
            print("API ERROR:", result)
            return "⚠️ AI error. Check API key/quota"
        # Clean the text for frontend display
        return clean_text(result['candidates'][0]['content']['parts'][0]['text'])
    except Exception as e:
        print("SERVER ERROR:", e)
        return "⚠️ Server error occurred"

# ---------------- FRONTEND ----------------
@app.route('/')
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>AI Study Coach</title>
<link rel="icon" href="data:,">
<style>
body{margin:0;font-family:Segoe UI;display:flex;background:linear-gradient(135deg,#667eea,#764ba2);color:white;}
.sidebar{width:260px;background:rgba(255,255,255,0.12);backdrop-filter:blur(20px);padding:20px;}
.task{display:flex;gap:10px;margin:10px 0;}
.main{flex:1;padding:30px;}
h1{text-align:center;}
.card{background:rgba(255,255,255,0.15);padding:20px;border-radius:15px;margin-bottom:20px;transition:0.3s;}
.card:hover{transform:translateY(-6px);}
input{padding:10px;width:60%;border:none;border-radius:5px;}
button{padding:10px;background:#ff7e5f;color:white;border:none;border-radius:5px;margin:5px;cursor:pointer;}
</style>
</head>
<body>
<div class="sidebar">
<h2 id="goalTitle">🎯 Goal</h2>
<div id="tasks"></div>
</div>
<div class="main">
<h1>🤖 AI Study Coach</h1>
<div class="card">
<input id="goal" placeholder="Enter goal">
<button onclick="setGoal()">Set Goal</button>
<button onclick="generatePlan()">Generate Plan</button>
<button onclick="removeGoal()">❌ Remove</button>
</div>
<div class="card">
<h3>📅 Study Plan</h3>
<ul id="plan"></ul>
<button onclick="downloadPDF()">Download PDF</button>
</div>
<div class="card">
<h3>💬 Chat</h3>
<input id="msg">
<button onclick="chat()">Send</button>
<p id="chatbox"></p>
</div>
</div>
<script>
function setGoal(){
let goal=document.getElementById('goal').value;
fetch('/set_goal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({goal})})
.then(res=>res.json()).then(()=>{document.getElementById('goalTitle').innerText="🎯 "+goal;});
}
function removeGoal(){
fetch('/remove_goal',{method:'POST'}).then(()=>{document.getElementById('goalTitle').innerText="🎯 Goal";document.getElementById('tasks').innerHTML="";document.getElementById('plan').innerHTML="";});
}
function generatePlan(){
let goal=document.getElementById('goal').value;
fetch('/generate_plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({goal})})
.then(res=>res.json())
.then(data=>{
let html="";data.plan.forEach(p=>{html+="<li>"+p+"</li>";});document.getElementById('plan').innerHTML=html;
loadTasks();
});
}
function loadTasks(){
fetch('/get_tasks').then(res=>res.json()).then(data=>{
let html="";data.forEach(t=>{html+=`<div class="task"><input type="checkbox" onclick="updateTask(${t[0]})"><span style="font-weight:bold;">${t[1]}</span></div>`});
document.getElementById('tasks').innerHTML=html;
});
}
function updateTask(id){
fetch('/update_task',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}).then(loadTasks);
}
function downloadPDF(){
fetch('/download_pdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan:document.getElementById("plan").innerText})})
.then(()=>{window.location.href="/study_plan.pdf";});
}
function chat(){
fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:document.getElementById('msg').value})})
.then(res=>res.json()).then(d=>{document.getElementById('chatbox').innerText=d.reply;});
}
</script>
</body>
</html>
"""

# ---------------- BACKEND ----------------
@app.route('/set_goal', methods=['POST'])
def set_goal():
    goal = request.json['goal']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM users")
    c.execute("INSERT INTO users (goal) VALUES (?)", (goal,))
    conn.commit()
    conn.close()
    return jsonify({"goal": goal})

@app.route('/remove_goal', methods=['POST'])
def remove_goal():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM users")
    c.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()
    return jsonify({"message": "removed"})

@app.route('/generate_plan', methods=['POST'])
def generate_plan():
    goal = request.json['goal']
    reply = call_gemini(f"Create a detailed 5 day study plan for {goal}")
    lines = [l.strip() for l in reply.split("\n") if l.strip()]
    tasks = [l for l in lines if l.lower().startswith("day")]
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM tasks")
    for t in tasks:
        c.execute("INSERT INTO tasks (task) VALUES (?)", (t,))
    conn.commit()
    conn.close()
    return jsonify({"plan": lines})

@app.route('/get_tasks')
def get_tasks():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tasks")
    data = c.fetchall()
    conn.close()
    return jsonify(data)

@app.route('/update_task', methods=['POST'])
def update_task():
    task_id = request.json['id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "done"})

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    plan = request.json['plan']
    doc = SimpleDocTemplate("study_plan.pdf")
    styles = getSampleStyleSheet()
    content = [Paragraph(line, styles["Normal"]) for line in plan.split("\n")]
    doc.build(content)
    return jsonify({"file": "study_plan.pdf"})

@app.route('/study_plan.pdf')
def serve_pdf():
    return send_file("study_plan.pdf", as_attachment=True)

@app.route('/chat', methods=['POST'])
def chat():
    msg = request.json['message']
    reply = call_gemini(msg)
    return jsonify({"reply": reply})

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
