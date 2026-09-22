from flask import Flask, render_template, request, jsonify, make_response
import json
from werkzeug.exceptions import NotFound

app = Flask(__name__)
PORT = 3202
HOST = '0.0.0.0'

with open('{}/databases/times.json'.format("."), 'r') as jsf:
    schedules = json.load(jsf)["schedule"]

def write(schedules):
    with open('{}/databases/times.json'.format("."), 'w') as f:
        full = {'schedule': schedules}
        json.dump(full, f)

@app.route("/schedules", methods=['GET'])
def get_all_schedules():
    return make_response(jsonify(schedules), 200)

@app.route("/schedules/<date>", methods=['GET'])
def get_schedule_bydate(date):
    for sched in schedules:
        if str(sched["date"]) == str(date):
            return make_response(jsonify(sched), 200)
    return make_response(jsonify({"error": "No schedule found for this date"}), 404)

@app.route("/schedules/<date>", methods=['POST'])
def add_schedule(date):
    req = request.get_json()
    for sched in schedules:
        if str(sched["date"]) == str(date):
            return make_response(jsonify({"error": "Schedule for this date already exists"}), 400)
    
    schedules.append(req)
    write(schedules)
    return make_response(jsonify({"message": "Schedule added"}), 201)

@app.route("/schedules/<date>", methods=['DELETE'])
def del_schedule(date):
    for sched in schedules:
        if str(sched["date"]) == str(date):
            schedules.remove(sched)
            write(schedules)
            return make_response(jsonify({"message": "Schedule deleted"}), 200)
    return make_response(jsonify({"error": "Schedule not found"}), 404)

if __name__ == "__main__":
    app.run(host=HOST, port=PORT)