from flask_jwt_extended import get_jwt, verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from graphql import GraphQLError
from pymongo import ReturnDocument

def movie_with_id(_,info,_id):
    return info.context["movies_collection"].find_one(
        {"id": _id}, {"_id": 0}
    )

def update_movie_rate(_,info,_id,_rate):
    try:
        verify_jwt_in_request()
    except JWTExtendedException as error:
        raise GraphQLError("A valid access token is required") from error
    if get_jwt().get("role") != "admin":
        raise GraphQLError("Admin privileges required")
    return info.context["movies_collection"].find_one_and_update(
        {"id": _id},
        {"$set": {"rating": _rate}},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )

def resolve_actors_in_movie(movie, info):
    return list(
        info.context["actors_collection"].find(
            {"films": movie["id"]}, {"_id": 0}
        )
    )
