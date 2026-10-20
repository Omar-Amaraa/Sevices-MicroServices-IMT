from flask import Flask, request, jsonify, make_response
import json
import requests
from werkzeug.exceptions import NotFound
from flask_jwt_extended import create_access_token, get_jwt_identity, JWTManager,jwt_required

app = Flask(__name__)

PORT = 3203
HOST = '0.0.0.0'
app.config["JWT_SECRET_KEY"] = "super-secret"
app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
app.config["JWT_COOKIE_SECURE"] = False

jwt = JWTManager(app)


with open('C:/Users/omara/Sevices-MicroServices-IMT/user/databases/users.json'.format("."), "r") as jsf:
   users = json.load(jsf)["users"]

def write(users):
    with open('C:/Users/omara/Sevices-MicroServices-IMT/user/databases/users.json'.format("."), 'w') as f:
        full = {'users': users}
        json.dump(full, f)
@app.route("/login", methods=["POST"])
def login ():
    username = request.json.get("username",None)
    password = request.json.get("password",None)
    if username != "test" or password != "test":
        return jsonify({"msg":"Bad username or password"}),401
    access_token=create_access_token(identity = username)
    return jsonify(access_token=access_token)


@app.route("/user/<username>", methods=["GET"])
@jwt_required()
def infos(username):
    current_user = get_jwt_identity()
    if username!=current_user:
        return make_response(jsonify({"error":"forbidden"}),403)
    for user in users : 
        if str(user["id"])==str(username):
            return make_response(jsonify(user),200)

    return make_response(jsonify({"error": "User not found"}), 404)

@app.route("/", methods=['GET'])
def home():
   return "<h1 style='color:blue'>Welcome to the User service!</h1>"

@app.route("/users", methods=['GET'])
def get_all_users():
    return make_response(jsonify(users), 200)

@app.route("/users/<userid>", methods=['GET'])
def get_user_byid(userid):
    for user in users:
        if str(user["id"]) == str(userid):
            return make_response(jsonify(user), 200)
    return make_response(jsonify({"error": "User not found"}), 404)

@app.route("/users/<userid>", methods=['POST'])
def add_user(userid):
    req = request.get_json()
    for user in users:
        if str(user["id"]) == str(userid):
            return make_response(jsonify({"error": "User ID already exists"}), 400)
    
    users.append(req)
    write(users)
    return make_response(jsonify({"message": "User added"}), 201)

@app.route("/users/<userid>", methods=['PUT'])
def update_user(userid):
    req = request.get_json()
    for user in users:
        if str(user["id"]) == str(userid):
            user.update(req)
            write(users)
            return make_response(jsonify(user), 200)
    return make_response(jsonify({"error": "User not found"}), 404)

@app.route("/users/<userid>", methods=['DELETE'])
def del_user(userid):
    for user in users:
        if str(user["id"]) == str(userid):
            users.remove(user)
            write(users)
            return make_response(jsonify({"message": "User deleted"}), 200)
    return make_response(jsonify({"error": "User not found"}), 404)


if __name__ == "__main__":
   print("Server running in port %s"%(PORT))
   app.run(host=HOST, port=PORT)
