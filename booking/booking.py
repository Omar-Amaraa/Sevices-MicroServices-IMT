import os
from functools import wraps

from flask import Flask, render_template, request, jsonify, make_response
from flask_jwt_extended import (
    JWTManager,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    verify_jwt_in_request,
)
import requests
import json
from werkzeug.exceptions import NotFound

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "jwt-secret-key-for-microservices"
)
jwt = JWTManager(app)

PORT = 3201
HOST = '0.0.0.0'

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

@app.route("/", methods=['GET'])
def home():
   return "<h1 style='color:blue'>Welcome to the Booking service!</h1>"

@app.route("/bookings", methods=['GET'])
@admin_required
def get_all_bookings():
    return make_response(jsonify(bookings), 200)

@app.route("/bookings/<userid>", methods=['GET'])
@jwt_required()
def get_user_bookings(userid):
    if not owner_or_admin(userid):
        return jsonify(error="Forbidden"), 403
    user_entry = next((u for u in bookings if str(u["userid"]) == str(userid)), None)
    if user_entry:
        return make_response(jsonify(user_entry), 200)
    return make_response(jsonify({"error": "No bookings found for this user"}), 404)

@app.route("/bookings/<userid>/details", methods=['GET'])
@jwt_required()
def get_detailed_user_bookings(userid):
    if not owner_or_admin(userid):
        return jsonify(error="Forbidden"), 403
    user_entry = next((u for u in bookings if str(u["userid"]) == str(userid)), None)
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

    user_entry = next((u for u in bookings if str(u["userid"]) == str(userid)), None)
    if not user_entry:
        user_entry = {"userid": userid, "dates": []}
        bookings.append(user_entry)
        
    date_entry = next((d for d in user_entry["dates"] if str(d["date"]) == str(target_date)), None)
    if not date_entry:
        date_entry = {"date": target_date, "movies": []}
        user_entry["dates"].append(date_entry)
        
    if target_movie in date_entry["movies"]:
        return make_response(jsonify({"error": "Booking already exists"}), 400)
        
    date_entry["movies"].append(target_movie)
    write(bookings)
    
    return make_response(jsonify({"message": "Booking confirmed", "booking": user_entry}), 201)

@app.route("/bookings/<userid>/<date>/<movieid>", methods=['DELETE'])
@jwt_required()
def del_booking(userid, date, movieid):
    if not owner_or_admin(userid):
        return jsonify(error="Forbidden"), 403
    for user in bookings:
        if str(user["userid"]) == str(userid):
            for d in user["dates"]:
                if str(d["date"]) == str(date):
                    if str(movieid) in d["movies"]:
                        d["movies"].remove(str(movieid))
                        
                        if not d["movies"]:
                            user["dates"].remove(d)
                            
                        write(bookings)
                        return make_response(jsonify({"message": "Booking deleted"}), 200)
                        
    return make_response(jsonify({"error": "Booking not found"}), 404)

if __name__ == "__main__":
    print("Server running in port %s"%(PORT))
    app.run(host=HOST, port=PORT)