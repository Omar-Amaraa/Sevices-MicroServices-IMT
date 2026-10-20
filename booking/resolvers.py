import requests
from pymongo import MongoClient

client = MongoClient("mongodb://root:example@localhost:27017/")
db = client["bookings"]
collection = db["bookings"]

MOVIE_URL = "http://localhost:3200"
SCHEDULE_URL = "http://localhost:3202"

def get_all_bookings(_,info):
    return list(collection.find({}, {"_id": 0}))

def get_user_bookings(_,info,_id):
    return collection.find_one({"userid": _id}, {"_id": 0})

def get_detailed_user_bookings(_,info,_id):
    result = []
    for booking in collection.find({"userid": _id}, {"_id": 0}):
        detailed_dates = []
        for d in booking['dates']:
            detailed_movies = []
            for mid in d['movies']:
                try:
                    res = requests.get(f"{MOVIE_URL}/movies/{mid}")
                    if res.status_code == 200:
                        detailed_movies.append(res.json()['title'])
                    else:
                        detailed_movies.append(mid)
                except requests.exceptions.RequestException:
                    detailed_movies.append(mid)
            detailed_dates.append({"date": d['date'], "movies": detailed_movies})
        result.append({"userid": booking['userid'], "dates": detailed_dates})
    return result

def add_booking(_,info,_id,date,movieid):
    try:
        res = requests.get(f"{SCHEDULE_URL}/schedules/{date}")
        if res.status_code != 200 or movieid not in res.json().get("movies", []):
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