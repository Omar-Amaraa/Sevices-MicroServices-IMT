import json
import os
import time
import re
from uuid import UUID
from pathlib import Path

from flask import Flask, request, jsonify, make_response
from flask_jwt_extended import JWTManager, get_jwt, jwt_required
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "jwt-secret-key-for-microservices"
)
jwt = JWTManager(app)
PORT = 3202
HOST = '0.0.0.0'


mongo_uri = os.environ.get("MONGODB_URI")
if not mongo_uri:
    raise RuntimeError("Set the MONGODB_URI environment variable")

mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
mongo_client.admin.command("ping")
database = mongo_client[os.environ.get("MONGODB_DATABASE", "schedule_service")]
schedules_collection = database["schedules"]
schedules_collection.create_index("date", unique=True)

legacy_schedules_file = Path(__file__).parent / "databases" / "times.json"
migration_collection = database["_migrations"]
migration_id = "legacy-schedules-json-v1"
if not migration_collection.find_one({"_id": migration_id}):
    if schedules_collection.count_documents({}) == 0 and legacy_schedules_file.exists():
        with legacy_schedules_file.open("r", encoding="utf-8") as jsf:
            legacy_schedules = json.load(jsf)["schedule"]
        for schedule in legacy_schedules:
            schedules_collection.update_one(
                {"date": schedule["date"]},
                {"$setOnInsert": schedule},
                upsert=True,
            )
    try:
        migration_collection.insert_one(
            {"_id": migration_id, "completed_at": int(time.time())}
        )
    except DuplicateKeyError:
        pass

@app.route("/schedules", methods=['GET'])
def get_all_schedules():
    schedules = list(schedules_collection.find({}, {"_id": 0}))
    return make_response(jsonify(schedules), 200)

@app.route("/schedules/<date>", methods=['GET'])
def get_schedule_bydate(date):
    schedule = schedules_collection.find_one({"date": str(date)}, {"_id": 0})
    if schedule is None:
        return make_response(jsonify({"error": "No schedule found for this date"}), 404)
    return make_response(jsonify(schedule), 200)

@app.route("/schedules/<date>", methods=['POST'])
@jwt_required()
def add_schedule(date):
    if get_jwt().get("role") != "admin":
        return jsonify(error="Admin privileges required"), 403

    req = request.get_json(silent=True)
    if not re.fullmatch(r"\d{8}", date):
        return jsonify(error="date must use YYYYMMDD format"), 400
    if not isinstance(req, dict):
        return jsonify(error="A JSON schedule object is required"), 400
    movie_ids = req.get("movies")
    if req.get("date") != date or not isinstance(movie_ids, list):
        return jsonify(error="date must match the URL and movies must be a list"), 400
    try:
        for movie_id in movie_ids:
            UUID(movie_id)
    except (TypeError, ValueError, AttributeError):
        return jsonify(error="movies must contain valid UUIDs"), 400

    if schedules_collection.find_one({"date": str(date)}, {"_id": 1}):
        return make_response(jsonify({"error": "Schedule for this date already exists"}), 400)
    try:
        schedules_collection.insert_one(req)
    except DuplicateKeyError:
        return make_response(jsonify({"error": "Schedule for this date already exists"}), 400)
    return make_response(jsonify({"message": "Schedule added"}), 201)

@app.route("/schedules/<date>", methods=['DELETE'])
@jwt_required()
def del_schedule(date):
    if get_jwt().get("role") != "admin":
        return jsonify(error="Admin privileges required"), 403

    result = schedules_collection.delete_one({"date": str(date)})
    if result.deleted_count:
        return make_response(jsonify({"message": "Schedule deleted"}), 200)
    return make_response(jsonify({"error": "Schedule not found"}), 404)

if __name__ == "__main__":
    app.run(host=HOST, port=PORT)