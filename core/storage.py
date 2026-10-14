"""상품 사진 저장소. 기능 코드는 저장 위치와 관계없이 이 함수들을 사용한다.

    storage.save(file)          # 업로드 파일 저장
    storage.put_bytes(data, ext) # 예시 이미지 저장
    storage.url(key)            # 브라우저에서 볼 주소
    storage.delete(key)         # 저장된 파일 삭제

STORAGE_BACKEND=local이면 uploads/ 폴더를 사용한다.
STORAGE_BACKEND=s3이면 비공개 S3 버킷을 사용한다.
S3 사진은 공개하지 않고, url()에서 1시간 유효한 임시 주소를 만든다.
"""
import mimetypes
import os
import shutil
import uuid
import boto3

from werkzeug.utils import secure_filename

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm', '.mov', '.pdf'}


def _s3():
    """설정한 AWS 리전으로 S3 연결을 만든다."""
    return boto3.client('s3', region_name=os.getenv('AWS_REGION'))


class NotAllowed(ValueError):
    pass


def save(file_storage) -> str:
    """업로드 파일을 저장하고 key(파일 이름)를 돌려준다.  파일이 없으면 ''.
    허용되지 않은 확장자면 NotAllowed 를 던진다 (app.py 가 400 JSON 으로 바꿔 준다)."""
    if not file_storage or not file_storage.filename:
        return ''
    ext = os.path.splitext(secure_filename(file_storage.filename))[1].lower()
    if ext not in ALLOWED:
        raise NotAllowed(f'허용되지 않는 파일 형식입니다: {ext or "(확장자 없음)"}')
    key = f'{uuid.uuid4().hex}{ext}'
    # 저장 위치 설정에 따라 S3 또는 로컬 uploads/ 폴더를 사용한다.
    if os.getenv('STORAGE_BACKEND', 'local') == 's3':
        _s3().put_object(
            Bucket=os.environ['S3_BUCKET'],
            Key=key,
            Body=file_storage.stream,
            ContentType=file_storage.mimetype or 'application/octet-stream',
        )
    else:
        file_storage.save(os.path.join(UPLOAD_DIR, key))
        _warn_if_full()
    return key


def put_bytes(data: bytes, ext: str) -> str:
    """바이트 데이터를 저장하고 파일 이름을 돌려준다."""
    key = f'{uuid.uuid4().hex}{ext}'
    if os.getenv('STORAGE_BACKEND', 'local') == 's3':
        # 예시 데이터의 이미지도 S3에 저장한다.
        content_type = mimetypes.guess_type(key)[0] or 'application/octet-stream'
        _s3().put_object(
            Bucket=os.environ['S3_BUCKET'],
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    else:
        with open(os.path.join(UPLOAD_DIR, key), 'wb') as f:
            f.write(data)
    return key


def url(key: str) -> str:
    """저장된 파일을 브라우저에서 열 수 있는 주소로 바꾼다."""
    if not key:
        return ''
    if os.getenv('STORAGE_BACKEND', 'local') == 's3':
        # 비공개 S3 파일을 1시간 동안 열 수 있는 임시 주소를 만든다.
        return _s3().generate_presigned_url(
            'get_object',
            Params={'Bucket': os.environ['S3_BUCKET'], 'Key': key},
            ExpiresIn=3600,
        )
    return f'/uploads/{key}'


def delete(key: str) -> None:
    """저장된 파일을 삭제한다."""
    if not key:
        return
    if os.getenv('STORAGE_BACKEND', 'local') == 's3':
        # 상품 사진을 삭제할 때 S3의 파일도 함께 삭제한다.
        _s3().delete_object(Bucket=os.environ['S3_BUCKET'], Key=key)
    else:
        try:
            os.remove(os.path.join(UPLOAD_DIR, key))
        except FileNotFoundError:
            pass


def _warn_if_full():
    """서버 디스크에 파일을 쌓으면 어떤 일이 생기는지 보여주는 경고 (2주차 장애 장면).
    서버 디스크는 채워질 수 있고, 서버가 꺼지면 이 폴더의 파일은 함께 사라질 수 있다."""
    total, used, free = shutil.disk_usage(UPLOAD_DIR)
    n = len(os.listdir(UPLOAD_DIR))
    if n and n % 20 == 0:
        print(f'[storage] uploads/ 에 파일 {n}개 · 디스크 남은 공간 {free // 2**30}GB — 이 폴더는 서버와 함께 사라집니다')