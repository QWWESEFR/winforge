# -*- coding: utf-8 -*-
"""
Windows 安装包发布平台 - 公开版主服务
Flask 应用：上传保存（待审目录）、脏话校验、公开统计、已上线文件下载
"""
import json
import os
import re
import time
import uuid
import datetime

from flask import Flask, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "pending")     # 待审目录
APPROVED_DIR = os.path.join(BASE_DIR, "uploads", "approved")  # 已上线目录
RECORDS_FILE = os.path.join(BASE_DIR, "uploads", "records.json")  # 发布记录（含审核状态）

ALLOWED_EXT = {".exe", ".msi", ".zip", ".7z", ".rar", ".appx", ".msix", ".bat", ".cmd", ".sb3", ".apk", ".dmg"}

app = Flask(__name__)

for d in (UPLOAD_DIR, APPROVED_DIR):
    os.makedirs(d, exist_ok=True)

# 脏话过滤词库（常见中文脏话与英文脏话，命中即拦截）
BAD_WORDS = [
    "傻逼", "煞笔", "妈的", "操你", "草你", "去死", "贱人", "婊子", "狗娘养的",
    "王八蛋", "混蛋", "他妈", "你妈", "滚蛋", "脑残", "智障", "白痴", "废物",
    "垃圾", "丑八怪", "臭不要脸", "不要脸", "欠揍", "揍你", "弄死你", "砍死你",
    "变态", "人渣", "败类", "畜牲", "畜生", "杂种", "野种", "龟儿子", "绿帽",
    "fuck", "shit", "bitch", "asshole", "damn", "cunt", "dick", "nigger", "retard",
    "cnm", "nmd", "wcnm", "sb", "md", "tm", "tmd",
]
BAD_PATTERN = re.compile("|".join(re.escape(w) for w in BAD_WORDS), re.IGNORECASE)


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_records():
    if not os.path.exists(RECORDS_FILE):
        return []
    try:
        with open(RECORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_records(records):
    with open(RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def add_record(record):
    records = load_records()
    records.append(record)
    save_records(records)


# ---------- 前台页面 ----------
@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/public/stats")
def api_public_stats():
    """公开统计：已上线与待审核数量（首页展示用）"""
    records = load_records()
    approved = sum(1 for r in records if r["status"] == "approved")
    pending = sum(1 for r in records if r["status"] == "pending")
    return jsonify({"ok": True, "approved": approved, "pending": pending})


@app.route("/publish.html")
def publish_page():
    return app.send_static_file("publish.html")


# ---------- 发布接口 ----------
@app.route("/api/publish", methods=["POST"])
def api_publish():
    """发布：校验文件名（脏话过滤）+ 保存文件到待审目录 + 生成审核中记录"""
    name = (request.form.get("name") or "").strip()
    file = request.files.get("file")

    if not name:
        return jsonify({"ok": False, "error": "请先为你的安装包起个名字"}), 400
    if len(name) > 50:
        return jsonify({"ok": False, "error": "名字太长了，请控制在 50 字以内"}), 400
    if BAD_PATTERN.search(name):
        return jsonify({"ok": False, "error": "名字包含不当词汇，请换个文明的名字哦"}), 400
    if not file or file.filename == "":
        return jsonify({"ok": False, "error": "请先拖入或选择要发布的安装包文件"}), 400

    raw_name = file.filename
    ext = os.path.splitext(raw_name)[1].lower()
    if ext and ext not in ALLOWED_EXT:
        return jsonify({"ok": False, "error": f"暂不支持该文件类型（{ext}），请上传 Windows 安装包（.exe/.msi/.zip 等）"}), 400

    # 使用安全文件名 + 时间戳前缀避免重名覆盖
    safe_base = secure_filename(os.path.splitext(raw_name)[0]) or "package"
    safe_ext = ext or ".bin"
    stored_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{safe_base}{safe_ext}"
    save_path = os.path.join(UPLOAD_DIR, stored_name)
    file.save(save_path)

    record = {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "file_name": stored_name,
        "original_name": raw_name,
        "status": "pending",            # pending=审核中, approved=已上线
        "created_at": now_str(),
        "approved_at": None,
        "size": os.path.getsize(save_path),
    }
    add_record(record)
    return jsonify({"ok": True, "id": record["id"], "status": "pending", "message": "发布成功，等待审核"})


@app.route("/api/check_name", methods=["POST"])
def api_check_name():
    """脏话校验接口（前端实时校验用）"""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": True, "clean": True, "message": ""})
    if BAD_PATTERN.search(name):
        return jsonify({"ok": False, "clean": False, "message": "名字包含不当词汇，请更换后重试"})
    return jsonify({"ok": True, "clean": True, "message": ""})


# ---------- 下载 ----------
@app.route("/download/<path:filename>")
def download_approved(filename):
    """已上线文件的公开直连下载地址"""
    if not os.path.exists(os.path.join(APPROVED_DIR, filename)):
        abort(404)
    return send_from_directory(APPROVED_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    print("=" * 56)
    print(" Windows 安装包发布平台（公开版）")
    print(" 前台首页:   http://127.0.0.1:5000/")
    print(" 发布页:     http://127.0.0.1:5000/publish.html")
    print("=" * 56)
    app.run(host="0.0.0.0", port=5000, debug=False)
