import os
from functools import wraps

from functools import wraps

from flask import Flask, render_template, request, jsonify, make_response

from flask_jwt_extended import (
    JWTManager,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    verify_jwt_in_request,
)
from ariadne import graphql_sync, make_executable_schema, load_schema_from_path, ObjectType, QueryType, MutationType

import requests
import json
import os
from werkzeug.exceptions import NotFound
from pymongo import MongoClient
from bson.json_util import dumps
import resolvers as r

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "jwt-secret-key-for-microservices"
)
jwt = JWTManager(app)
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "jwt-secret-key-for-microservices"
)
jwt = JWTManager(app)

PORT = 3201
HOST = '0.0.0.0'
mongo_uri = os.environ.get("MONGODB_URI")
if not mongo_uri:
    raise RuntimeError("Set the MONGODB_URI environment variable")
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
client.admin.command("ping")

MOVIE_URL = os.environ.get("MOVIE_URL", "http://localhost:3200")
SCHEDULE_URL = os.environ.get("SCHEDULE_URL", "http://localhost:3202")


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        if get_jwt().get("role") != "admin":
            return jsonify(error="Admin privileges required"), 403
        return fn(*args, **kwargs)

    return wrapper


def owner_or_admin(userid):
    return (
        str(get_jwt_identity()) == str(userid)
        or get_jwt().get("role") == "admin"
    )

with open('{}/databases/bookings.json'.format("."), 'r') as jsf:
    bookings = json.load(jsf)["bookings"]

def write(bookings):
    with open('{}/databases/bookings.json'.format("."), 'w') as f:
        full = {'bookings': bookings}
        json.dump(full, f)
MOVIE_URL = os.environ.get("MOVIE_URL", "http://localhost:3200")
SCHEDULE_URL = os.environ.get("SCHEDULE_URL", "http://localhost:3202")
BASE = os.path.dirname(os.path.abspath(__file__))


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        if get_jwt().get("role") != "admin":
            return jsonify(error="Admin privileges required"), 403
        return fn(*args, **kwargs)

    return wrapper


def owner_or_admin(userid):
    return (
        str(get_jwt_identity()) == str(userid)
        or get_jwt().get("role") == "admin"
    )

db = client[os.environ.get("MONGODB_DATABASE", "bookings")]
collection = db["bookings"]
collection.create_index("userid", unique=True)
type_defs = load_schema_from_path('{}/booking.graphql'.format(BASE))
if collection.count_documents({}) == 0:
    with open('{}/databases/bookings.json'.format(BASE), 'r') as jsf:
        collection.insert_many(json.load(jsf)["bookings"])
query = QueryType()
mutation = MutationType()
dateMovie = ObjectType('DateMovie')
booking = ObjectType('Booking')

query.set_field('get_user_bookings', r.get_user_bookings)
query.set_field('get_all_bookings', r.get_all_bookings)

query.set_field('get_detailed_user_bookings', r.get_detailed_user_bookings)

mutation.set_field('add_booking', r.add_booking)
mutation.set_field('del_booking', r.del_booking)

schema = make_executable_schema(type_defs, booking, query, mutation, dateMovie)

@app.route("/graphql", methods=['POST'])
@jwt_required()
def graphql_server():
    data = request.get_json()
    success, result = graphql_sync(schema, data, context_value=request, debug=app.debug)
    return make_response(jsonify(result), 200 if success else 400)


@app.route("/", methods=['GET'])
def home():
    return make_response("<h1 style='color:blue'>Welcome to the Booking service!</h1>",200)


@app.route("/bookings", methods=['GET'])
@admin_required
def get_all_bookings():
    return make_response(jsonify(list(collection.find({}, {"_id": 0}))), 200)

@app.route("/bookings/<userid>", methods=['GET'])
@jwt_required()
def get_user_bookings(userid):
    user_entry = collection.find_one({"userid": userid}, {"_id": 0})
    if user_entry:
        return make_response(jsonify(user_entry), 200)
    return make_response(jsonify({"error": "No bookings found for this user"}), 404)

@app.route("/bookings/<userid>/details", methods=['GET'])
@jwt_required()
def get_detailed_user_bookings(userid):
    user_entry = collection.find_one({"userid": userid}, {"_id": 0})
    if not user_entry:
        return make_response(jsonify({"error": "User not found"}), 404)

    detailed_dates = []
    for d in user_entry["dates"]:
        detailed_movies = []
        for mid in d["movies"]:
            try:
                res = requests.get(f"{MOVIE_URL}/movies/{mid}")
                if res.status_code == 200:
                    detailed_movies.append(res.json())
                else:
                    detailed_movies.append({"id": mid, "error": "Details not found"})
            except requests.exceptions.RequestException:
                detailed_movies.append({"id": mid, "error": "Movie service unreachable"})

        detailed_dates.append({"date": d["date"], "movies": detailed_movies})

    return make_response(jsonify({"userid": userid, "dates": detailed_dates}), 200)

@app.route("/bookings/<userid>", methods=['POST'])
@jwt_required()
def add_booking(userid):
    if not owner_or_admin(userid):
        return jsonify(error="Forbidden"), 403
    req = request.get_json()
    target_date = req.get("date")
    target_movie = req.get("movieid")

    try:
        schedule_res = requests.get(f"{SCHEDULE_URL}/schedules/{target_date}")
        if schedule_res.status_code != 200:
            return make_response(jsonify({"error": "Date not found in schedule"}), 400)

        schedule_data = schedule_res.json()
        if target_movie not in schedule_data.get("movies", []):
            return make_response(jsonify({"error": "Movie not scheduled on this date"}), 400)
    except requests.exceptions.RequestException:
        return make_response(jsonify({"error": "Schedule service unreachable"}), 503)

    user_entry = collection.find_one({"userid": userid}, {"_id": 0})

    if not user_entry:
        user_entry = {"userid": userid, "dates": []}

    date_entry = next((d for d in user_entry["dates"] if str(d["date"]) == str(target_date)), None)
    if not date_entry:
        date_entry = {"date": target_date, "movies": []}
        user_entry["dates"].append(date_entry)

    if target_movie in date_entry["movies"]:
        return make_response(jsonify({"error": "Booking already exists"}), 400)

    date_entry["movies"].append(target_movie)
    collection.replace_one({"userid": userid}, user_entry, upsert=True)

    return make_response(jsonify({"message": "Booking confirmed", "booking": user_entry}), 201)

@app.route("/bookings/<userid>/<date>/<movieid>", methods=['DELETE'])
@jwt_required()
def del_booking(userid, date, movieid):
    user = collection.find_one({"userid": userid}, {"_id": 0})
    if user:
        for d in user["dates"]:
            if str(d["date"]) == str(date):
                if str(movieid) in d["movies"]:
                    d["movies"].remove(str(movieid))

                    if not d["movies"]:
                        user["dates"].remove(d)

                    collection.replace_one({"userid": userid}, user)
                    return make_response(jsonify({"message": "Booking deleted"}), 200)

    return make_response(jsonify({"error": "Booking not found"}), 404)
if __name__ == "__main__":
    print("Server running in port %s"%(PORT))
    app.run(host=HOST, port=PORT)