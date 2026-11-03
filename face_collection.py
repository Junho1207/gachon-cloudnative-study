import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# 이 파일과 같은 폴더의 .env 읽기
load_dotenv(Path(__file__).parent / ".env")

client = boto3.client(
    "rekognition",
    region_name=os.environ["AWS_REGION"],
)

COLLECTION_ID = "tube-lite-team5-faces"

try:
    response = client.create_collection(
        CollectionId=COLLECTION_ID,
    )
    print("컬렉션 생성 완료!")
    print("이름:", COLLECTION_ID)
    print("ARN:", response["CollectionArn"])

except ClientError as e:
    code = e.response["Error"]["Code"]

    if code == "ResourceAlreadyExistsException":
        print("이미 생성된 컬렉션입니다:", COLLECTION_ID)
    else:
        raise