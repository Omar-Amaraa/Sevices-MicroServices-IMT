import json
import os
import re
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, make_response, request
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

PORT = 3203
HOST = "0.0.0.0"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "jwt-secret-key-for-microservices"
)
jwt = JWTManager(app)

mongo_uri = os.environ.get("MONGODB_URI")
if not mongo_uri:
    raise RuntimeError("Set the MONGODB_URI environment variable")

mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
mongo_client.admin.command("ping")
database = mongo_client[os.environ.get("MONGODB_DATABASE", "user_service")]
users_collection = database["users"]
users_collection.create_index("id", unique=True)
users_collection.create_index(
    "email",
    unique=True,
    partialFilterExpression={"email": {"$type": "string"}},
)

legacy_users_file = Path(__file__).parent / "databases" / "users.json"
migration_collection = database["_migrations"]
migration_id = "legacy-users-json-v1"
if not migration_collection.find_one({"_id": migration_id}):
    if users_collection.count_documents({}) == 0 and legacy_users_file.exists():
        with legacy_users_file.open("r", encoding="utf-8") as jsf:
            legacy_users = json.load(jsf)["users"]
        for user in legacy_users:
            user.setdefault("role", "user")
            users_collection.update_one(
                {"id": user["id"]}, {"$setOnInsert": user}, upsert=True
            )
    try:
        migration_collection.insert_one(
            {"_id": migration_id, "completed_at": int(time.time())}
        )
    except DuplicateKeyError:
        pass


def public_user(user):
    return {
        key: user[key]
        for key in ("id", "name", "email", "last_active", "role")
        if key in user
    }


@app.route("/", methods=["GET"])
def home():
    return "<h1 style='color:blue'>Welcome to the User service!</h1>"


@app.route("/signup", methods=["POST"])
def signup():
    req = request.get_json(silent=True)
    if not isinstance(req, dict):
        return jsonify(error="A JSON object is required"), 400

    name = req.get("name")
    email = req.get("email")
    password = req.get("password")
    
    if not all(isinstance(value, str) for value in (name, email, password)):
        return jsonify(error="name, email, and password are required"), 400

    name = name.strip()
    email = email.strip().lower()
    if not name or not EMAIL_PATTERN.fullmatch(email):
        return jsonify(error="A valid name and email are required"), 400
    if len(password) < 8:
        return jsonify(error="Password must be at least 8 characters"), 400
    if users_collection.find_one({"email": email}, {"_id": 1}):
        return jsonify(error="An account with that email already exists"), 409

    user = {
        "id": uuid.uuid4().hex,
        "name": name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "last_active": int(time.time()),
        "role": "user",
    }
    try:
        users_collection.insert_one(user)
    except DuplicateKeyError:
        return jsonify(error="An account with that email already exists"), 409
    return jsonify(user=public_user(user)), 201


@app.route("/login", methods=["POST"])
def login():
    req = request.get_json(silent=True)
    if not isinstance(req, dict):
        return jsonify(error="A JSON object is required"), 400

    email = req.get("email")
    password = req.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify(error="email and password are required"), 400

    email = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        return jsonify(error="A valid email is required"), 400
    user = users_collection.find_one({"email": email})
    password_hash = user.get("password_hash") if user else None
    if not password_hash or not check_password_hash(password_hash, password):
        return jsonify(error="Invalid credentials"), 401

    user["last_active"] = int(time.time())
    users_collection.update_one(
        {"id": user["id"]}, {"$set": {"last_active": user["last_active"]}}
    )
    access_token = create_access_token(
        identity=user["id"],
        additional_claims={"role": user.get("role", "user")},
    )
    return jsonify(access_token=access_token), 200


@app.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = users_collection.find_one({"id": str(user_id)})
    if user is None:
        return jsonify(error="User not found"), 404

    return jsonify(public_user(user)), 200


@app.route("/users", methods=["GET"])
@jwt_required()
def get_all_users():
    current_user = users_collection.find_one(
        {"id": str(get_jwt_identity())}, {"role": 1}
    )
    if current_user is None or current_user.get("role") != "admin":
        return jsonify(error="Admin privileges required"), 403

    user_summaries = list(
        users_collection.find(
            {}, {"_id": 0, "id": 1, "name": 1, "last_active": 1, "role": 1}
        )
    )
    return make_response(jsonify(user_summaries), 200)


@app.route("/users/<userid>", methods=["GET"])
@jwt_required()
def get_user_byid(userid):
    current_user = users_collection.find_one(
        {"id": str(get_jwt_identity())}, {"role": 1}
    )
    if str(get_jwt_identity()) != str(userid) and (
        current_user is None or current_user.get("role") != "admin"
    ):
        return jsonify(error="Forbidden"), 403
    user = users_collection.find_one({"id": str(userid)})
    if user is None:
        return make_response(jsonify({"error": "User not found"}), 404)
    return make_response(jsonify(public_user(user)), 200)


@app.route("/users/<userid>", methods=["PUT"])
@jwt_required()
def update_user(userid):
    current_user = users_collection.find_one(
        {"id": str(get_jwt_identity())}, {"role": 1}
    )
    if str(get_jwt_identity()) != str(userid) and (
        current_user is None or current_user.get("role") != "admin"
    ):
        return jsonify(error="Forbidden"), 403

    req = request.get_json(silent=True)
    if not isinstance(req, dict):
        return jsonify(error="A JSON object is required"), 400

    name = req.get("name")
    if not isinstance(name, str) or not name.strip():
        return jsonify(error="name must be a non-empty string"), 400

    result = users_collection.update_one(
        {"id": str(userid)}, {"$set": {"name": name.strip()}}
    )
    if result.matched_count == 0:
        return make_response(jsonify({"error": "User not found"}), 404)
    user = users_collection.find_one({"id": str(userid)})
    return make_response(jsonify(public_user(user)), 200)


@app.route("/users/<userid>", methods=["DELETE"])
@jwt_required()
def del_user(userid):
    current_user = users_collection.find_one(
        {"id": str(get_jwt_identity())}, {"role": 1}
    )
    if str(get_jwt_identity()) != str(userid) and (
        current_user is None or current_user.get("role") != "admin"
    ):
        return jsonify(error="Forbidden"), 403
    result = users_collection.delete_one({"id": str(userid)})
    if result.deleted_count == 0:
        return make_response(jsonify({"error": "User not found"}), 404)
    return make_response(jsonify({"message": "User deleted"}), 200)


if __name__ == "__main__":
    print("Server running in port %s" % PORT)
    app.run(host=HOST, port=PORT)
