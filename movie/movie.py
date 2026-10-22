import os
import json
from pathlib import Path
from functools import wraps


from ariadne import graphql_sync, make_executable_schema, load_schema_from_path, ObjectType, QueryType, MutationType
from flask import Flask, request, jsonify, make_response
from flask_jwt_extended import JWTManager, get_jwt, verify_jwt_in_request, jwt_required
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError
import resolvers as r

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "jwt-secret-key-for-microservices"
)
jwt = JWTManager(app)

PORT = 3200
HOST = '0.0.0.0'
mongo_uri = os.environ.get("MONGODB_URI")
if not mongo_uri:
    raise RuntimeError("Set the MONGODB_URI environment variable")
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
client.admin.command("ping")


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        if get_jwt().get("role") != "admin":
            return jsonify(error="Admin privileges required"), 403
        return fn(*args, **kwargs)

    return wrapper

db = client[os.environ.get("MONGODB_DATABASE", "movies")]
collection = db["movies"]
collection.create_index("id", unique=True)
movies_file = Path(__file__).parent / "databases" / "movies.json"
with movies_file.open("r", encoding="utf-8") as jsf:
    movie_seeds = json.load(jsf)["movies"]
for movie_data in movie_seeds:
    collection.update_one(
        {"id": movie_data["id"]},
        {"$setOnInsert": movie_data},
        upsert=True,
    )

actors_collection = db["actors"]
actors_collection.create_index("id", unique=True)
actors_file = Path(__file__).parent / "databases" / "actors.json"
with actors_file.open("r", encoding="utf-8") as jsf:
    actor_seeds = json.load(jsf)["actors"]
for actor_data in actor_seeds:
    actors_collection.update_one(
        {"id": actor_data["id"]},
        {"$setOnInsert": actor_data},
        upsert=True,
    )

type_defs = load_schema_from_path('movie.graphql')

query = QueryType()
mutation = MutationType()
movie = ObjectType('Movie')
actor = ObjectType('Actor')

query.set_field('movie_with_id', r.movie_with_id)
mutation.set_field('update_movie_rate', r.update_movie_rate)
movie.set_field('actors', r.resolve_actors_in_movie)

schema = make_executable_schema(type_defs, movie, query, mutation, actor)

# root message
@app.route("/", methods=['GET'])
def home():
    return make_response("<h1 style='color:blue'>Welcome to the Movie service!</h1>",200)

@app.route("/json", methods=['GET'])
def get_json():
    movies = list(collection.find({}, {"_id": 0}))
    res = make_response(jsonify(movies), 200)
    return res

@app.route("/movies/<movieid>", methods=['GET'])
def get_movie_byid(movieid):
    movie = collection.find_one({"id": str(movieid)}, {"_id": 0})
    if movie is not None:
        res = make_response(jsonify(movie), 200)
        return res
    return make_response(jsonify({"error":"Movie ID not found"}),500)

"""@app.route("/moviesbytitle", methods=['GET'])
def get_movie_bytitle():
    json = ""
    if request.args:
        req = request.args
        for movie in movies:
            if str(movie["title"]) == str(req["title"]):
                json = movie

    if not json:
        res = make_response(jsonify({"error":"movie title not found"}),500)
    else:
        res = make_response(jsonify(json),200)
    return res
"""
@app.route("/movies/<movieid>", methods=['POST'])
@admin_required
def add_movie(movieid):
    req = request.get_json(silent=True)
    if not isinstance(req, dict) or str(req.get("id")) != str(movieid):
        return make_response(jsonify({"error": "movie body id must match URL id"}), 400)
    try:
        collection.insert_one(req)
    except DuplicateKeyError:
        return make_response(jsonify({"error": "movie ID already exists"}), 500)
    res = make_response(jsonify({"message":"movie added"}),200)
    return res

@app.route("/movies/<movieid>/<rate>", methods=['PUT'])
@admin_required
def update_movie_rating(movieid, rate):
    try:
        rating = float(rate)
    except ValueError:
        return make_response(jsonify({"error": "rating must be numeric"}), 400)
    movie = collection.find_one_and_update(
        {"id": str(movieid)},
        {"$set": {"rating": rating}},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if movie is not None:
        res = make_response(jsonify(movie), 200)
        return res

    res = make_response(jsonify({"error":"movie ID not found"}),500)
    return res

@app.route("/movies/<movieid>", methods=['DELETE'])
@admin_required
def del_movie(movieid):
    movie = collection.find_one_and_delete(
        {"id": str(movieid)}, projection={"_id": 0}
    )
    if movie is not None:
        return make_response(jsonify(movie), 200)

    res = make_response(jsonify({"error":"movie ID not found"}),500)
    return res

# graphql entry points
@app.route('/graphql', methods=['POST'])
@jwt_required()
def graphql_server():
    data = request.get_json()
    success, result = graphql_sync(
                        schema,
                        data,
                        context_value={
                            "movies_collection": collection,
                            "actors_collection": actors_collection,
                        },
                        debug=app.debug
                    )
    status_code = 200 if success else 400
    return jsonify(result), status_code

if __name__ == "__main__":
    print("Server running in port %s"%(PORT))
    app.run(host=HOST, port=PORT)