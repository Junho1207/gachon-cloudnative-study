# TubeLite (tube-lite) — 유튜브 클론

유튜브를 그대로 베낀 클론입니다. 다크 테마, 상단 검색바, 왼쪽 사이드바, 썸네일 그리드(재생시간 배지 · 채널 아바타 · "조회수 1.2만회 · 3일 전"),
시청 페이지(플레이어 · 채널 · 구독 · 좋아요/싫어요 · 설명 더보기 · 댓글 · 오른쪽 추천), 채널 페이지, 구독 피드, 시청 기록, 좋아요 표시한 동영상, 내 동영상,
업로드(드래그 앤 드롭 · 영상에서 썸네일 자동 추출 · 재생시간 자동 계산).

로컬에서 돌아가는 모놀리식 원본입니다. **Flask(JSON API) + React(Vite)**. 데이터·파일·알림·주기작업은 전부 이 서버 한 대 안에 있습니다.
5주차에 받아서, 매주 조각 하나를 AWS로 옮깁니다.

## 실행 (Python 만 있으면 됩니다)

```bash
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
python seed.py                # 채널 4개 (kim / lee / park / choi · 비밀번호 1234), 동영상 12개
python app.py                 # → http://localhost:5000
```

화면(React) 빌드 결과 `static/app/` 이 저장소에 들어 있어서 Node 없이 바로 돕니다.

## 화면을 고칠 때 (Node 18+)

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173 · API 는 5000 으로 자동 전달 (파이썬 서버도 켜 두세요)
npm run build                 # ../static/app 에 결과물 → python app.py 만으로 반영
```

## 조각 지도 — 어디에 무엇이 있나

| 조각 | 파일 | 어느 주에 어디로 가나 |
|---|---|---|
| 동영상 · 썸네일 파일 | `core/storage.py` | **6주차 → S3** |
| users · videos · comments · subscriptions · history · trending · notifications | `core/db.py` | **7주차 → DynamoDB** |
| 댓글 · 새 구독자 알림 | `core/notify.py` ← `features/comments`, `features/channels` | **9주차 → Lambda + SNS** |
| 매일 인기 동영상 집계 | `core/jobs.py` ← `features/videos/compute_trending` | **9주차 → Lambda + EventBridge** |
| 남은 Flask 서버 | `app.py` | **10주차 → EC2** |
| 화면 (정적 파일) | `static/app/` | 선택 과제 → S3 정적 호스팅 |

## 구조

```
core/                       storage.py  db.py  notify.py  jobs.py  auth.py       ← 매주 하나씩 클라우드로
features/<기능>/api.py       auth  videos  channels  comments  notifications  _template   ← 백엔드: 기능 = 폴더 하나 (/api/<기능>/…)
frontend/src/features/       auth  videos  channels  notifications  _template          ← 프론트: 기능 = 폴더 하나 (routes.jsx 자동 등록)
frontend/src/components/    Layout(상단바·사이드바)  VideoCard  Avatar  Icons  ui  RequireLogin
frontend/src/               api.js  auth.jsx  format.js(조회수·시간 표기)  styles.css(유튜브 다크 테마)
static/app/                 npm run build 결과 (Flask 가 서빙)
app.py  seed.py
```

기능은 파일·데이터·알림·주기작업을 **`core/` 를 통해서만** 씁니다.
그래서 `core/storage.py` 를 S3로 바꾸면 모든 기능의 파일이 그날 S3로 갑니다. 여러분이 추가한 기능도요.

## 기능

- `videos` 홈(전체 · 인기 · 조회수순 칩) · 검색 결과 · 시청(조회수 · 좋아요/싫어요 · 설명 · 추천) · 업로드 · 시청 기록 · 좋아요한 동영상 · 내 동영상 · 구독 피드 · 인기 집계(주기 작업)
- `channels` 채널 페이지(배너 · 아바타 · 구독자 수 · 동영상 그리드) · 구독 토글 → 채널 주인에게 알림 · 구독 목록(사이드바)
- `comments` 댓글 · 댓글 좋아요 → 업로더에게 알림
- `auth` 가입(아이디 = 채널 핸들, 아바타 색 자동) · 로그인 · `notifications` 알림함(🔔 배지)

조 기능 아이디어: 재생목록 / 해시태그·카테고리 / 댓글 답글 / Shorts 탭 / 나중에 볼 동영상 / 영상 신고 / 채널 배너 이미지 업로드 / 자막 파일 첨부

## 우리 조 기능 추가하기

`features/_template/README.md`. 백엔드 폴더 복사 + 프론트 폴더 복사 → 이름 바꾸기 → 서버 재시작·빌드. 사이드바 메뉴는 `routes.jsx` 의 `nav` 에 `icon` 을 주면 붙습니다.

## 서버가 꺼지면 사라지는 것 (5주차 해부 힌트)

- `uploads/` 폴더의 동영상·썸네일 → 6주차
- `data.db` 파일의 모든 데이터 → 7주차
- 서버 안에서 돌던 인기 집계 → 9주차
- 로그인 세션 (서명된 쿠키) → 마무리 강의에서

## API 한눈에

| 메서드 | 경로 | 하는 일 |
|---|---|---|
| POST | `/api/auth/signup` `/login` `/logout` · GET `/api/auth/me` | 계정 |
| GET | `/api/videos/?q=&sort=latest|popular|trending` | 목록 · 검색 |
| POST | `/api/videos/` (multipart: title, desc, video, thumb, duration) | 업로드 |
| GET | `/api/videos/<id>` | 시청 (조회수 +1, 시청 기록) → video · channel · comments · related |
| POST | `/api/videos/<id>/react` {value: like · dislike · null} | 좋아요/싫어요 |
| GET | `/api/videos/history` `/liked` `/mine` `/feed` | 보관함 |
| GET | `/api/channels/<uid>` · POST `/<uid>/subscribe` · GET `/subscriptions` | 채널 · 구독 |
| POST | `/api/comments/<video_id>` · `/api/comments/<id>/like` | 댓글 |
| GET | `/api/notifications/` · POST `/read` | 알림 |

+

## 얼굴 로그인 실행을 위한 AWS 설정

### 1. IAM 권한 추가

**IAM → 사용자 → 액세스 키를 발급한 사용자 → 권한 → 인라인 정책 생성 → JSON**

아래 `본인_AWS_계정_ID`를 본인의 12자리 AWS 계정 ID로 바꿔 추가합니다. 기존 DB·S3 권한은 유지하세요.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rekognition:CreateCollection",
        "rekognition:IndexFaces",
        "rekognition:CreateUser",
        "rekognition:AssociateFaces",
        "rekognition:SearchUsersByImage",
        "rekognition:ListFaces",
        "rekognition:DeleteUser",
        "rekognition:DeleteFaces"
      ],
      "Resource": "arn:aws:rekognition:ap-northeast-2:본인_AWS_계정_ID:collection/tube-lite-team5-faces"
    },
    {
      "Effect": "Allow",
      "Action": "rekognition:DetectFaces",
      "Resource": "*"
    }
  ]
}
```

### 2. 컬렉션 생성 — 최초 1회

프로젝트 최상위 폴더에서 실행합니다.

```powershell
python -m pip install -r requirements.txt
python face_collection.py
```

`컬렉션 생성 완료` 또는 `이미 생성된 컬렉션입니다`가 나오면 됩니다.

컬렉션 이름은 코드와 동일한 `tube-lite-team5-faces`를 사용합니다. 계정이 다르므로 이름이 같아도 서로 별개입니다.

### 3. 최초 얼굴 등록

비밀번호 로그인 → 왼쪽 **얼굴 등록** → 카메라 권한 허용 → 현재 비밀번호 입력 → **촬영하고 얼굴 등록**

등록 후 로그아웃하고 로그인 화면에서 **페이스 로그인하기**를 선택하면 됩니다.

각자의 AWS 환경에서 얼굴을 새로 등록해야 합니다. 웹캠은 `localhost` 또는 HTTPS에서 사용할 수 있습니다.

### 4. 얼굴 삭제

로그인 → 왼쪽 **얼굴 등록** → 현재 비밀번호 입력 → **얼굴 삭제**

삭제 후에는 페이스 로그인이 되지 않으며, 다시 등록할 수 있습니다.
