from ariadne import graphql_sync, make_executable_schema, load_schema_from_path, ObjectType, QueryType, MutationType
from flask import Flask, request, jsonify, make_response
import json
import sys
from werkzeug.exceptions import NotFound

import resolvers as r

app = Flask(__name__)

PORT = 3200
HOST = '0.0.0.0'

with open('{}/databases/movies.json'.format("."), 'r') as jsf:
    movies = json.load(jsf)["movies"]
    print(movies)

def write(movies):
    with open('{}/databases/movies.json'.format("."), 'w') as f:
        full = {}
        full['movies']=movies
        json.dump(full, f)

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
    res = make_response(jsonify(movies), 200)
    return res

@app.route("/movies/<movieid>", methods=['GET'])
def get_movie_byid(movieid):
    for movie in movies:
        if str(movie["id"]) == str(movieid):
            res = make_response(jsonify(movie),200)
            return res
    return make_response(jsonify({"error":"Movie ID not found"}),500)

@app.route("/moviesbytitle", methods=['GET'])
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

@app.route("/movies/<movieid>", methods=['POST'])
def add_movie(movieid):
    req = request.get_json()

    for movie in movies:
        if str(movie["id"]) == str(movieid):
            print(movie["id"])
            print(movieid)
            return make_response(jsonify({"error":"movie ID already exists"}),500)

    movies.append(req)
    write(movies)
    res = make_response(jsonify({"message":"movie added"}),200)
    return res

@app.route("/movies/<movieid>/<rate>", methods=['PUT'])
def update_movie_rating(movieid, rate):
    for movie in movies:
        if str(movie["id"]) == str(movieid):
            movie["rating"] = rate
            res = make_response(jsonify(movie),200)
            write(movies)
            return res

    res = make_response(jsonify({"error":"movie ID not found"}),500)
    return res

@app.route("/movies/<movieid>", methods=['DELETE'])
def del_movie(movieid):
    for movie in movies:
        if str(movie["id"]) == str(movieid):
            movies.remove(movie)
            write(movies)
            return make_response(jsonify(movie),200)

    res = make_response(jsonify({"error":"movie ID not found"}),500)
    return res

# graphql entry points
@app.route('/graphql', methods=['POST'])
def graphql_server():
    data = request.get_json()
    success, result = graphql_sync(
                        schema,
                        data,
                        context_value=None,
                        debug=app.debug
                    )
    status_code = 200 if success else 400
    return jsonify(result), status_code

if __name__ == "__main__":
    #p = sys.argv[1]
    print("Server running in port %s"%(PORT))
    app.run(host=HOST, port=PORT)