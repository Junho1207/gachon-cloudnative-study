import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# ACCESS_KEY / SECRET_KEY 로 작성된 경우 boto3 표준 환경변수로 매핑 지원
if os.getenv('ACCESS_KEY') and not os.getenv('AWS_ACCESS_KEY_ID'):
    os.environ['AWS_ACCESS_KEY_ID'] = os.environ['ACCESS_KEY']
if os.getenv('AWS_SECRET_KEY') and not os.getenv('AWS_SECRET_ACCESS_KEY'):
    os.environ['AWS_SECRET_ACCESS_KEY'] = os.environ['AWS_SECRET_KEY']
