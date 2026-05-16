from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

PROCS = ["P1", "P2"]
RESS = {"R1": {"instances": 1}, "R2": {"instances": 1}}

DEAD_SCENARIO = [("P1", "R1"), ("R1", "P2"), ("P2", "R2"), ("R2", "P1")]
SAFE_SCENARIO = [("P1", "R1"), ("R1", "P2"), ("P2", "R2")]

state = {
    "mode": "deadlock",
    "scenario": DEAD_SCENARIO[:],
    "edges": [],
    "step": 0,
    "deadlock_count": 0,
    "custom": []
}

def detect_deadlock(edges):
    if not edges:
        return False, [], [], True

    alloc = {p: {} for p in PROCS}
    req = {p: {} for p in PROCS}

    for s, d in edges:
        if s.startswith("R") and d.startswith("P"):
            alloc[d][s] = alloc[d].get(s, 0) + 1
        elif s.startswith("P") and d.startswith("R"):
            req[s][d] = req[s].get(d, 0) + 1

    avail = {r: RESS[r]["instances"] for r in RESS}
    for p in PROCS:
        for r, c in alloc[p].items():
            avail[r] -= c

    finished = set()
    changed = True
    while changed:
        changed = False
        for p in PROCS:
            if p in finished:
                continue
            if all(avail.get(r, 0) >= c for r, c in req[p].items()):
                finished.add(p)
                for r, c in alloc[p].items():
                    avail[r] += c
                changed = True

    dead_processes = [p for p in PROCS if p not in finished]
    if not dead_processes:
        return False, [], [], True

    dead_nodes = set(dead_processes)
    dead_edges = []
    for s, d in edges:
        if s in dead_nodes or d in dead_nodes:
            dead_edges.append((s, d))
            dead_nodes.add(s)
            dead_nodes.add(d)

    involved_resources = [n for n in dead_nodes if n.startswith("R")]
    single = all(RESS[r]["instances"] == 1 for r in involved_resources)
    return True, list(dead_nodes), dead_edges, single

def run_safety(edges):
    alloc = {p: {} for p in PROCS}
    req = {p: {} for p in PROCS}

    for s, d in edges:
        if s.startswith("R") and d.startswith("P"):
            alloc[d][s] = alloc[d].get(s, 0) + 1
        elif s.startswith("P") and d.startswith("R"):
            req[s][d] = req[s].get(d, 0) + 1

    work = {r: RESS[r]["instances"] for r in RESS}
    for p in PROCS:
        for r, c in alloc[p].items():
            work[r] -= c

    finish = {p: False for p in PROCS}
    seq = []
    changed = True

    while changed:
        changed = False
        for p in PROCS:
            if finish[p]:
                continue
            if all(req[p].get(r, 0) <= work.get(r, 0) for r in RESS):
                for r, c in alloc[p].items():
                    work[r] += c
                finish[p] = True
                seq.append(p)
                changed = True

    return all(finish.values()), seq

def predict_next():
    if state["step"] >= len(state["scenario"]):
        return False, "No next step."
    edge = state["scenario"][state["step"]]
    found, _, _, _ = detect_deadlock(state["edges"] + [edge])
    if found:
        return True, f"Adding {edge[0]} → {edge[1]} will cause DEADLOCK."
    return False, f"Next edge {edge[0]} → {edge[1]} is safe."

def snapshot(message="System ready."):
    found, nodes, dead_edges, single = detect_deadlock(state["edges"])
    pred_warn, pred_msg = predict_next()

    return {
        "edges": state["edges"],
        "step": state["step"],
        "total": len(state["scenario"]),
        "resources": RESS,
        "deadlock": found,
        "deadNodes": nodes,
        "deadEdges": dead_edges,
        "deadlockCount": state["deadlock_count"],
        "message": message,
        "mode": state["mode"],
        "predictionWarning": pred_warn,
        "prediction": pred_msg,
        "ai": "DEADLOCK DETECTED" if found else "SAFE STATE",
        "details": (
            "Circular wait detected. Some processes cannot finish because each process is waiting for a resource held by another process."
            if found else
            "The system is currently safe. The processes can still complete without being permanently blocked."
        )
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/state")
def api_state():
    return jsonify(snapshot())

@app.route("/api/next", methods=["POST"])
def api_next():
    if state["step"] < len(state["scenario"]):
        edge = state["scenario"][state["step"]]
        state["edges"].append(edge)
        state["step"] += 1
        found, _, _, _ = detect_deadlock(state["edges"])
        if found:
            state["deadlock_count"] += 1
            return jsonify(snapshot(f"Step {state['step']}: {edge[0]} → {edge[1]} caused deadlock."))
        return jsonify(snapshot(f"Step {state['step']}: {edge[0]} → {edge[1]} added."))
    return jsonify(snapshot("All steps are already shown."))

@app.route("/api/reset", methods=["POST"])
def api_reset():
    state["edges"] = []
    state["step"] = 0
    return jsonify(snapshot("System reset."))

@app.route("/api/mode", methods=["POST"])
def api_mode():
    mode = request.json.get("mode", "deadlock")
    state["mode"] = mode
    state["scenario"] = SAFE_SCENARIO[:] if mode == "safe" else DEAD_SCENARIO[:]
    state["edges"] = []
    state["step"] = 0
    return jsonify(snapshot(f"{mode.title()} scenario loaded."))

@app.route("/api/custom", methods=["POST"])
def api_custom():
    edges = request.json.get("edges", [])
    cleaned = []
    valid = {"P1", "P2", "R1", "R2"}
    for e in edges:
        if len(e) == 2 and e[0] in valid and e[1] in valid and e[0] != e[1]:
            cleaned.append((e[0], e[1]))
    state["custom"] = cleaned
    state["scenario"] = cleaned
    state["mode"] = "custom"
    state["edges"] = []
    state["step"] = 0
    return jsonify(snapshot("Custom scenario loaded."))

@app.route("/api/resource", methods=["POST"])
def api_resource():
    name = request.json.get("name")
    delta = int(request.json.get("delta", 0))
    if name in RESS:
        RESS[name]["instances"] = max(1, min(9, RESS[name]["instances"] + delta))
    return jsonify(snapshot(f"{name} instances: {RESS[name]['instances']}"))

@app.route("/api/banker", methods=["POST"])
def api_banker():
    safe, seq = run_safety(state["edges"])
    if safe:
        return jsonify(snapshot("Banker's Algorithm: already safe. Safe sequence: " + (" → ".join(seq) if seq else "No active requests")))

    for rem in [e for e in state["edges"] if e[0].startswith("P")]:
        test = [e for e in state["edges"] if e != rem]
        safe, seq = run_safety(test)
        if safe:
            state["edges"] = test
            return jsonify(snapshot(f"Banker's solved it by denying request {rem[0]} → {rem[1]}. Safe sequence: {' → '.join(seq)}"))

    for rem in [e for e in state["edges"] if e[0].startswith("R")]:
        test = [e for e in state["edges"] if e != rem]
        safe, seq = run_safety(test)
        if safe:
            state["edges"] = test
            return jsonify(snapshot(f"Banker's solved it by releasing {rem[0]} → {rem[1]}. Safe sequence: {' → '.join(seq)}"))

    return jsonify(snapshot("Banker's Algorithm could not solve it with one action."))

@app.route("/api/chat", methods=["POST"])
def api_chat():
    question = request.json.get("question", "").strip()
    if not question:
        return jsonify({"answer": "Please type a question first."})

    try:
        from openai import OpenAI
        token = os.getenv("HF_TOKEN")
        if not token:
            return jsonify({"answer": "HF_TOKEN is missing. Set it first in terminal."})

        client = OpenAI(base_url="https://router.huggingface.co/v1", api_key=token)
        response = client.chat.completions.create(
            model=os.getenv("AI_MODEL", "meta-llama/Llama-3.1-8B-Instruct:novita"),
            messages=[
                {"role": "system", "content": "You are a short educational assistant for OS deadlocks, RAG, detection, prevention, and Banker's algorithm. Answer in maximum 4 short lines."},
                {"role": "user", "content": question}
            ],
            max_tokens=120
        )
        return jsonify({"answer": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"answer": f"AI Error: {e}"})

if __name__ == "__main__":
    app.run(debug=True)
