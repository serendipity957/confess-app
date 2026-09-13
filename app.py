# -*- coding: utf-8 -*-
"""
💌 表白回应应用 · 后端
============================================================
功能：
  GET  /            表白页（给 TA 看的，手机电脑都能开）
  POST /api/respond 接收 TA 的回应和留言（前端调用）
  GET  /admin       留言管理页（给你看的，需要密码）

运行：
  python app.py
  浏览器打开 http://127.0.0.1:5000

手机访问（同一 WiFi 下）：
  浏览器打开 http://<电脑IP>:5000
  电脑IP 启动时会自动打印出来

可修改的配置：
  ADMIN_PASSWORD  管理页密码（改成你自己的）
  PORT            端口（默认 5000）
============================================================
"""

import json
import os
import socket
import uuid
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

# ============ 配置区（按需修改） ============
ADMIN_PASSWORD = "520520"        # 管理页密码，改成你自己的
PORT = 5000                      # 服务端口
# ============================================

app = Flask(__name__)
app.secret_key = "confess-app-secret-2026"   # 管理页登录状态密钥，可随便改

# 留言数据文件（与 app.py 同目录）
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")


def load_data():
    """读取全部数据；文件不存在或损坏时返回空结构。
    数据结构：{"chat": [消息...], "records": [回应记录...]}
    """
    if not os.path.exists(DATA_FILE):
        return {"chat": [], "records": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):  # 兼容旧格式（纯记录列表）
            return {"chat": [], "records": data}
        data.setdefault("chat", [])
        data.setdefault("records", [])
        return data
    except (json.JSONDecodeError, OSError):
        return {"chat": [], "records": []}


def save_data(data):
    """把全部数据写入本地 JSON 文件。"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fix_text(text):
    """修复中文被错误解码的乱码（如 '浣犳槸璋?' → '你是谁'）。"""
    if not text:
        return text
    for enc in ("latin-1", "gbk", "cp1252"):
        try:
            fixed = text.encode(enc).decode("utf-8")
            if any("\u4e00" <= ch <= "\u9fff" for ch in fixed):
                return fixed
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return text


def load_records():
    """兼容：取回应记录列表。"""
    return load_data()["records"]


@app.route("/")
def index():
    """表白页。"""
    return render_template("index.html")


@app.route("/celebrate")
def celebrate():
    """庆祝页：对方选择"我愿意"后跳转到这里。支持 ?id=xxx 查看回复。"""
    rid = request.args.get("id", "")
    record = None
    for r in load_records():
        if r.get("id") == rid:
            record = r
            break
    return render_template("celebrate.html", record=record)


@app.route("/result")
def result():
    """结果页：其他选项（有喜欢的人/做朋友/没想好）跳转到这里。"""
    choice = request.args.get("choice", "")
    rid = request.args.get("id", "")
    record = None
    for r in load_records():
        if r.get("id") == rid:
            record = r
            break
    return render_template("result.html", choice=choice, record=record)


@app.route("/api/respond", methods=["POST"])
def respond():
    """
    接收 TA 的回应。
    请求体 JSON：
      {"choice": "我愿意" / "让我再想想" / "有喜欢的人了" / "还是做朋友吧",
       "message": "留言（可选）",
       "crush": "喜欢的人是谁（可选，仅当选择'有喜欢的人了'时可能填写）"}
    返回：{"ok": true, "id": "xxx"} 或 {"ok": false, "error": "原因"}
    """
    data = request.get_json(silent=True) or request.form
    choice = (data.get("choice") or "").strip()
    message = fix_text(data.get("message") or "").strip()
    crush = fix_text(data.get("crush") or "").strip()

    # 校验
    if choice not in ("我愿意", "让我再想想", "有喜欢的人了", "还是做朋友吧"):
        return jsonify({"ok": False, "error": "无效的选择"}), 400
    if len(message) > 500:
        return jsonify({"ok": False, "error": "留言太长了（最多500字）"}), 400
    if len(crush) > 100:
        return jsonify({"ok": False, "error": "名字太长了"}), 400

    # 存一条记录，id 用于生成对方的专属交流空间
    data = load_data()
    record_id = uuid.uuid4().hex[:10]
    records = data["records"]
    messages = []
    if message:
        messages.append({
            "who": "ta",
            "text": message,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    records.append({
        "id": record_id,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "choice": choice,
        "crush": crush,
        "messages": messages,
        "contact": "",
    })
    save_data(data)
    return jsonify({"ok": True, "id": record_id})


@app.route("/api/contact", methods=["POST"])
def save_contact():
    """对方在庆祝页填写联系方式：{"id": 记录id, "contact": "微信号/手机号等"}。"""
    body = request.get_json(silent=True) or request.form
    rid = (body.get("id") or "").strip()
    contact = fix_text(body.get("contact") or "").strip()

    if not contact:
        return jsonify({"ok": False, "error": "联系方式不能为空"}), 400
    if len(contact) > 200:
        return jsonify({"ok": False, "error": "内容太长了"}), 400

    data = load_data()
    for r in data["records"]:
        if r.get("id") == rid:
            r["contact"] = contact
            save_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "记录不存在"}), 404


@app.route("/chat")
def chat():
    """交流空间：确认前的聊天页，双方都能看和发。"""
    data = load_data()
    return render_template("chat.html", messages=data["chat"])


@app.route("/api/chat", methods=["POST"])
def add_chat():
    """在交流空间发消息（对方视角）：{"text": "内容"}。"""
    body = request.get_json(silent=True) or request.form
    text = fix_text(body.get("text") or "").strip()

    if not text:
        return jsonify({"ok": False, "error": "内容不能为空"}), 400
    if len(text) > 500:
        return jsonify({"ok": False, "error": "内容太长了（最多500字）"}), 400

    data = load_data()
    data["chat"].append({
        "who": "ta",
        "text": text,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_data(data)
    return jsonify({"ok": True})


@app.route("/api/chat_reply", methods=["POST"])
def chat_reply():
    """管理页在交流空间回复：{"text": "回复内容"}。"""
    if not session.get("admin_ok"):
        return jsonify({"ok": False, "error": "请先登录管理页"}), 403
    body = request.get_json(silent=True) or request.form
    text = fix_text(body.get("text") or "").strip()

    if not text:
        return jsonify({"ok": False, "error": "内容不能为空"}), 400
    if len(text) > 500:
        return jsonify({"ok": False, "error": "内容太长了（最多500字）"}), 400

    data = load_data()
    data["chat"].append({
        "who": "me",
        "text": text,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_data(data)
    return jsonify({"ok": True})


@app.route("/api/message", methods=["POST"])
def add_message():
    """对方在专属交流空间里继续发消息：{"id": 记录id, "text": "内容"}。"""
    body = request.get_json(silent=True) or request.form
    rid = (body.get("id") or "").strip()
    text = fix_text(body.get("text") or "").strip()

    if not text:
        return jsonify({"ok": False, "error": "内容不能为空"}), 400
    if len(text) > 500:
        return jsonify({"ok": False, "error": "内容太长了（最多500字）"}), 400

    data = load_data()
    for r in data["records"]:
        if r.get("id") == rid:
            r.setdefault("messages", []).append({
                "who": "ta",
                "text": text,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            save_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "记录不存在"}), 404


@app.route("/api/reply", methods=["POST"])
def reply():
    """管理页回复对方：{"id": 记录id, "reply": "回复内容"}，追加进交流空间。"""
    body = request.get_json(silent=True) or request.form
    rid = (body.get("id") or "").strip()
    reply_text = fix_text(body.get("reply") or "").strip()

    if len(reply_text) > 500:
        return jsonify({"ok": False, "error": "回复太长了（最多500字）"}), 400

    data = load_data()
    for r in data["records"]:
        if r.get("id") == rid:
            r.setdefault("messages", []).append({
                "who": "me",
                "text": reply_text,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            save_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "记录不存在"}), 404


@app.route("/admin", methods=["GET", "POST"])
def admin():
    """留言管理页：先输密码登录，再展示 TA 的所有回应。"""
    error = None

    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin_ok"] = True
            return redirect(url_for("admin"))
        error = "密码不对，再试试"

    if not session.get("admin_ok"):
        return render_template("admin.html", locked=True, error=error)

    # 已登录：读取数据，记录最新排最前面
    data = load_data()
    records = list(reversed(data["records"]))
    chat_messages = data["chat"]
    stats = {
        "total": len(records),
        "yes": sum(1 for r in records if r["choice"] == "我愿意"),
        "think": sum(1 for r in records if r["choice"] == "让我再想想"),
        "crush": sum(1 for r in records if r["choice"] in ("有喜欢的人了", "还是做朋友吧")),
        "message": sum(1 for r in records if r.get("messages")),
    }
    return render_template("admin.html", locked=False, records=records,
                           chat_messages=chat_messages, stats=stats)


@app.route("/admin/logout")
def admin_logout():
    """退出登录。"""
    session.pop("admin_ok", None)
    return redirect(url_for("admin"))


if __name__ == "__main__":
    # 获取本机局域网 IP，方便手机访问
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except OSError:
        pass

    print("=" * 54)
    print("  💌 表白应用已启动")
    print(f"  电脑打开:   http://127.0.0.1:{PORT}")
    print(f"  手机打开:   http://{local_ip}:{PORT}   (需同一WiFi)")
    print(f"  管理页:     http://{local_ip}:{PORT}/admin   密码: {ADMIN_PASSWORD}")
    print("  关闭服务:   直接关闭这个窗口，或按 Ctrl+C")
    print("=" * 54)
    app.run(host="0.0.0.0", port=PORT, debug=False)
