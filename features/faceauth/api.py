import os
from functools import wraps

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.security import check_password_hash

from core import db
from core.auth import login_required


bp = Blueprint("faceauth", __name__)

COLLECTION_ID = "tube-lite-team5-faces"


def rekognition_client():
    return boto3.client(
        "rekognition",
        region_name=os.environ["AWS_REGION"],
    )


def handle_errors(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)

        except ValueError as e:
            return jsonify(error=str(e)), 400

        except (ClientError, BotoCoreError):
            current_app.logger.exception("Rekognition request failed")
            return jsonify(
                error="얼굴 인증 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해주세요."
            ), 502

    return wrapped


def read_photo(client):
    photo = request.files.get("photo")

    if not photo:
        raise ValueError("촬영에 실패했습니다. 다시 시도해주세요.")

    max_size = 5 * 1024 * 1024
    data = photo.read(max_size + 1)

    if not data:
        raise ValueError("촬영에 실패했습니다. 다시 시도해주세요.")

    if len(data) > max_size:
        raise ValueError("촬영 이미지가 너무 큽니다. 카메라를 다시 연결한 후 시도해주세요.")

    result = client.detect_faces(
        Image={"Bytes": data},
    )

    if len(result.get("FaceDetails", [])) != 1:
        raise ValueError(
            "카메라에 얼굴이 한 명만 보이도록 화면 중앙에 맞춘 후 다시 촬영해주세요."
        )

    return data


# 기존 계정에 얼굴 등록
@bp.post("/register")
@login_required
@handle_errors
def register():
    uid = session["user_id"]
    user = db.get("users", uid)

    password = request.form.get("password", "")

    if not user or not check_password_hash(
        user.get("pw", ""), password
    ):
        return jsonify(
            error="현재 계정의 비밀번호가 틀렸습니다."
        ), 403

    if user.get("face_user_id"):
        return jsonify(
            error="이미 얼굴이 등록된 계정입니다."
        ), 409

    client = rekognition_client()
    image_data = read_photo(client)

    # 실제 앱 회원 ID와 Rekognition 사용자 ID 연결
    face_user_id = f"app-{uid}"

    try:
        client.create_user(
            CollectionId=COLLECTION_ID,
            UserId=face_user_id,
        )

    except ClientError as e:
        if e.response["Error"]["Code"] != "ConflictException":
            raise

    indexed = client.index_faces(
        CollectionId=COLLECTION_ID,
        Image={"Bytes": image_data},
        ExternalImageId=face_user_id,
        MaxFaces=1,
        QualityFilter="AUTO",
    )

    records = indexed.get("FaceRecords", [])

    if not records:
        raise ValueError(
            "얼굴을 등록하지 못했습니다. 밝은 곳에서 얼굴을 화면 중앙에 맞춘 후 다시 촬영해주세요."
        )

    face_id = records[0]["Face"]["FaceId"]

    associated = client.associate_faces(
        CollectionId=COLLECTION_ID,
        UserId=face_user_id,
        FaceIds=[face_id],
    )

    if associated.get("UnsuccessfulFaceAssociations"):
        current_app.logger.warning(
            "Face association failed: %s",
            associated["UnsuccessfulFaceAssociations"],
        )
        raise ValueError("계정에 얼굴을 등록하지 못했습니다. 잠시 후 다시 시도해주세요.")

    db.update(
        "users",
        uid,
        face_user_id=face_user_id,
    )

    return jsonify(
        message="얼굴 등록이 완료되었습니다. 다음 로그인부터 페이스 로그인을 사용할 수 있습니다."
    )


# 등록한 얼굴 삭제
@bp.post("/delete")
@login_required
@handle_errors
def delete_face():
    uid = session["user_id"]
    user = db.get("users", uid)

    password = request.form.get("password", "")

    if not user or not check_password_hash(
        user.get("pw", ""), password
    ):
        return jsonify(
            error="현재 계정의 비밀번호가 틀렸습니다."
        ), 403

    face_user_id = user.get("face_user_id")

    if not face_user_id:
        return jsonify(
            error="등록된 얼굴이 없습니다."
        ), 404

    client = rekognition_client()

    # ExternalImageId로 찾아야 등록 실패 때 남은 얼굴까지 지울 수 있다
    pages = client.get_paginator("list_faces").paginate(
        CollectionId=COLLECTION_ID,
    )
    face_ids = [
        face["FaceId"]
        for page in pages
        for face in page["Faces"]
        if face.get("ExternalImageId") == face_user_id
    ]

    # 이전 시도에서 이미 지워졌으면 그대로 진행
    try:
        client.delete_user(
            CollectionId=COLLECTION_ID,
            UserId=face_user_id,
        )

    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    if face_ids:
        deleted = client.delete_faces(
            CollectionId=COLLECTION_ID,
            FaceIds=face_ids,
        )

        if deleted.get("UnsuccessfulFaceDeletions"):
            current_app.logger.warning(
                "Face deletion failed: %s",
                deleted["UnsuccessfulFaceDeletions"],
            )
            raise ValueError("얼굴을 삭제하지 못했습니다. 잠시 후 다시 시도해주세요.")

    # AWS 삭제가 끝난 뒤에 연결을 끊어야 실패해도 다시 시도할 수 있다
    db.update(
        "users",
        uid,
        face_user_id=None,
    )

    return jsonify(
        message="등록된 얼굴을 삭제했습니다."
    )


# 웹캠 사진으로 앱 계정을 찾아 로그인
@bp.post("/login")
@handle_errors
def login():
    client = rekognition_client()
    image_data = read_photo(client)
    result = client.search_users_by_image(
        CollectionId=COLLECTION_ID,
        Image={"Bytes": image_data},
        UserMatchThreshold=95,
        MaxUsers=5,
    )
    linked = []
    for match in result.get("UserMatches", []):
        candidate = match["User"]
        identity = candidate["UserId"]
        if candidate.get("UserStatus") != "ACTIVE" or not identity.startswith("app-"):
            continue
        account = db.get("users", identity[4:])
        if account and account.get("face_user_id") == identity:
            linked.append(account)
    if len(linked) != 1:
        return jsonify(error="얼굴을 확인할 수 없습니다. 다시 시도해주세요. 계속 실패하면 비밀번호로 로그인한 후 얼굴 등록 상태를 확인해주세요."), 401
    session.clear()
    session["user_id"] = linked[0]["id"]
    return jsonify(message="얼굴 로그인 성공!")
