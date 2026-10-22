import os

import requests
from flask_jwt_extended import get_jwt, get_jwt_identity
from graphql import GraphQLError
from pymongo import MongoClient

mongo_uri = os.environ.get("MONGODB_URI")
if not mongo_uri:
    raise RuntimeError("Set the MONGODB_URI environment variable")
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[os.environ.get("MONGODB_DATABASE", "bookings")]
collection = db["bookings"]

MOVIE_URL = os.environ.get("MOVIE_URL", "http://localhost:3200")
SCHEDULE_URL = os.environ.get("SCHEDULE_URL", "http://localhost:3202")


def require_owner_or_admin(user_id):
    if (
        str(get_jwt_identity()) != str(user_id)
        and get_jwt().get("role") != "admin"
    ):
        raise GraphQLError("Forbidden")


def query_graphql(service_url, query, variables):
    response = requests.post(
        f"{service_url}/graphql",
        json={"query": query, "variables": variables},
        timeout=5,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("errors"):
        return None
    return result.get("data")


def get_all_bookings(_,info):
    if get_jwt().get("role") != "admin":
        raise GraphQLError("Admin privileges required")
    return list(collection.find({}, {"_id": 0}))

def get_user_bookings(_,info,_id):
    require_owner_or_admin(_id)
    return collection.find_one({"userid": _id}, {"_id": 0})

def get_detailed_user_bookings(_,info,_id):
    require_owner_or_admin(_id)
    result = []
    for booking in collection.find({"userid": _id}, {"_id": 0}):
        detailed_dates = []
        for d in booking['dates']:
            detailed_movies = []
            for mid in d['movies']:
                try:
                    movie_result = query_graphql(
                        MOVIE_URL,
                        "query MovieById($id: String!) { movie_with_id(_id: $id) { title } }",
                        {"id": mid},
                    )
                    movie = movie_result.get("movie_with_id") if movie_result else None
                    detailed_movies.append(movie["title"] if movie else mid)
                except requests.exceptions.RequestException:
                    detailed_movies.append(mid)
            detailed_dates.append({"date": d['date'], "movies": detailed_movies})
        result.append({"userid": booking['userid'], "dates": detailed_dates})
    return result

def add_booking(_,info,_id,date,movieid):
    require_owner_or_admin(_id)
    try:
        schedule_response = requests.get(
            f"{SCHEDULE_URL}/schedules/{date}", timeout=5
        )
        if schedule_response.status_code != 200:
            return None
        schedule = schedule_response.json()
        if not schedule or movieid not in schedule.get("movies", []):
            return None
    except requests.exceptions.RequestException:
        return None
    booking = collection.find_one({"userid": _id}, {"_id": 0})
    if not booking:
        booking = {"userid": _id, "dates": []}
    dateentry = None
    for d in booking['dates']:
        if d['date'] == date:
            dateentry = d
    if not dateentry:
        dateentry = {"date": date, "movies": []}
        booking['dates'].append(dateentry)
    if movieid in dateentry['movies']:
        return None
    dateentry['movies'].append(movieid)
    collection.replace_one({"userid": _id}, booking, upsert=True)
    return booking

def del_booking(_,info,_id,date,movieid):
    require_owner_or_admin(_id)
    booking = collection.find_one({"userid": _id}, {"_id": 0})
    if booking:
        for d in booking['dates']:
            if d['date'] == date and movieid in d['movies']:
                d['movies'].remove(movieid)
                if not d['movies']:
                    booking['dates'].remove(d)
                collection.replace_one({"userid": _id}, booking)
                return booking
    return None