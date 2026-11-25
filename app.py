import json
import os
import urllib.request
from datetime import datetime

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

from guide import Guide, lookup, split_guide

db = SQLAlchemy()


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(300), nullable=False)
    answered = db.Column(db.Boolean, default=False)
    section = db.Column(db.String(120))
    asked_at = db.Column(db.DateTime, default=datetime.now)


def ask_model(question, hits):
    # only used when LLM_URL, LLM_KEY and LLM_MODEL are set. any openai style chat endpoint
    url = os.environ.get("LLM_URL")
    key = os.environ.get("LLM_KEY")
    model = os.environ.get("LLM_MODEL")
    if not (url and key and model):
        return None

    context = "\n\n".join(h["title"] + ": " + h["text"] for h in hits)
    body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "Answer using only the guide sections below and say which section you used. "
                                          "If they do not answer the question, reply with exactly NOT_IN_GUIDE."},
            {"role": "user", "content": context + "\n\nQuestion: " + question},
        ],
    }
    req = urllib.request.Request(
        url,
        json.dumps(body).encode(),
        {"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("llm call failed, using plain answer:", e)
        return None


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")  # set a real one when deploying
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///questions.db"  # ends up in instance/
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    with open(os.path.join(app.root_path, "guide.md"), encoding="utf-8") as f:
        default_text = f.read()
    state = {"guide": Guide(default_text), "name": "sample guide (made up)"}

    @app.route("/", methods=["GET", "POST"])
    def index():
        question = ""
        result = None
        if request.method == "POST":
            question = request.form.get("question", "").strip()
            if question:
                result = lookup(state["guide"], question)
                if result["found"]:
                    from_model = ask_model(question, result["hits"])
                    if from_model == "NOT_IN_GUIDE":
                        result["found"] = False
                    elif from_model:
                        result["text"] = from_model

                best = result["hits"][0]["title"] if result["found"] else None
                db.session.add(Question(text=question[:300], answered=result["found"], section=best))
                db.session.commit()

        titles = [s["title"] for s in state["guide"].sections]
        return render_template("index.html", question=question, result=result, name=state["name"], titles=titles)

    @app.route("/guide", methods=["POST"])
    def set_guide():
        text = request.form.get("guide", "").strip()
        if len(split_guide(text)) < 2:
            flash("Need at least two sections, each starting with ## and a title.")
        else:
            state["guide"] = Guide(text)
            state["name"] = "the guide you pasted"
        return redirect(url_for("index"))

    @app.route("/guide/reset", methods=["POST"])
    def reset_guide():
        state["guide"] = Guide(default_text)
        state["name"] = "sample guide (made up)"
        return redirect(url_for("index"))

    @app.route("/log")
    def log():
        recent = Question.query.order_by(Question.asked_at.desc()).limit(30).all()
        total = Question.query.count()
        missed = Question.query.filter_by(answered=False).count()
        return render_template("log.html", recent=recent, total=total, missed=missed)

    @app.route("/api/ask")
    def api_ask():
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"error": "missing q"}), 400
        return jsonify(lookup(state["guide"], q))

    return app
