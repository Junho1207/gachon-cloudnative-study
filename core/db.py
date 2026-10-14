"""데이터 저장. 기능 코드는 이 함수들만 부른다.

    db.put('items', {'id': ..., 'title': ...})   # 저장
    db.get('items', id)                          # 하나
    db.find('items', seller='kim')               # 조건으로 여럿
    db.all('items')                              # 전부 (최신순)
    db.update('items', id, price=9000)           # 일부 필드
    db.delete('items', id)

DB_BACKEND=sqlite이면 로컬 data.db를 사용한다.
DB_BACKEND=dynamodb이면 AWS DynamoDB를 사용한다.
기능 코드는 저장 위치가 바뀌어도 같은 함수를 호출한다.
"""
import builtins
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data.db')
_lock = threading.RLock()
_known = set()
_conn_obj = None


def _use_dynamodb() -> bool:
    """환경 설정으로 데이터 저장 위치를 선택한다."""
    return os.getenv('DB_BACKEND', 'sqlite') == 'dynamodb'


def _ddb_table(table: str):
    """예: items → carrot-lite-team7-items."""
    name = os.environ['DDB_PREFIX'] + table
    return boto3.resource(
        'dynamodb',
        region_name=os.getenv('AWS_REGION')
    ).Table(name)


def _to_dynamodb(value):
    """DynamoDB가 저장할 수 있도록 실수를 Decimal로 바꾼다."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamodb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb(v) for v in value]
    return value


def _from_dynamodb(value):
    """DynamoDB의 Decimal을 앱에서 쓰는 숫자로 되돌린다."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _from_dynamodb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamodb(v) for v in value]
    return value


def _scan(table: str, filter_expression=None) -> list:
    """Scan 결과가 여러 페이지여도 끝까지 읽는다."""
    ddb_table = _ddb_table(table)
    params = {}
    if filter_expression is not None:
        params['FilterExpression'] = filter_expression

    items = []
    while True:
        result = ddb_table.scan(**params)
        items.extend(result.get('Items', []))
        if 'LastEvaluatedKey' not in result:
            break
        params['ExclusiveStartKey'] = result['LastEvaluatedKey']

    return [_from_dynamodb(item) for item in items]


def _sort_items(items: list, desc: bool = True) -> list:
    """SQLite와 같은 기준으로 생성 시각, ID를 정렬한다."""
    return sorted(
        items,
        key=lambda item: (item.get('created_at', ''), item['id']),
        reverse=desc
    )


def _conn():
    """SQLite 연결은 프로세스에 하나만 둔다."""
    global _conn_obj
    if _conn_obj is None:
        _conn_obj = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn_obj.row_factory = sqlite3.Row
        _conn_obj.execute('PRAGMA journal_mode=WAL')
    return _conn_obj


def close():
    global _conn_obj
    if _conn_obj is not None:
        _conn_obj.close()
        _conn_obj = None
    _known.clear()


def _ensure(table):
    """SQLite에서 필요한 테이블을 만든다."""
    if table in _known:
        return
    with _lock:
        _conn().execute(
            f'CREATE TABLE IF NOT EXISTS "{table}" '
            '(id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT NOT NULL)'
        )
        _conn().commit()
    _known.add(table)


def init():
    if _use_dynamodb():
        print('[db] DynamoDB — 데이터가 AWS 테이블에 저장됩니다')
    else:
        print(f'[db] SQLite {DB_PATH} — 이 파일이 지워지면 데이터도 사라집니다')


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def put(table: str, item: dict) -> dict:
    item = dict(item)
    item.setdefault('id', uuid.uuid4().hex[:12])
    item.setdefault('created_at', now())

    if _use_dynamodb():
        # DynamoDB에서는 id가 같은 항목을 새 내용으로 저장한다.
        _ddb_table(table).put_item(Item=_to_dynamodb(item))
    else:
        _ensure(table)
        with _lock:
            _conn().execute(
                f'INSERT OR REPLACE INTO "{table}" '
                '(id, data, created_at) VALUES (?, ?, ?)',
                (item['id'], json.dumps(item, ensure_ascii=False), item['created_at'])
            )
            _conn().commit()

    return item


def get(table: str, id: str):
    if _use_dynamodb():
        result = _ddb_table(table).get_item(Key={'id': id})
        item = result.get('Item')
        return _from_dynamodb(item) if item is not None else None

    _ensure(table)
    with _lock:
        row = _conn().execute(
            f'SELECT data FROM "{table}" WHERE id=?', (id,)
        ).fetchone()
    return json.loads(row['data']) if row else None


def all(table: str, desc: bool = True) -> list:
    if _use_dynamodb():
        # DynamoDB Scan에는 정렬 기능이 없어 읽은 뒤 정렬한다.
        return _sort_items(_scan(table), desc)

    _ensure(table)
    order = 'DESC' if desc else 'ASC'
    with _lock:
        rows = _conn().execute(
            f'SELECT data FROM "{table}" '
            f'ORDER BY created_at {order}, id {order}'
        ).fetchall()
    return [json.loads(row['data']) for row in rows]


def find(table: str, **eq) -> list:
    """필드 값이 같은 항목을 최신순으로 찾는다."""
    if _use_dynamodb():
        if not eq:
            return all(table)

        # 값이 None이면 기존 SQLite 방식처럼 파이썬에서 비교한다.
        if any(value is None for value in eq.values()):
            return [
                item for item in all(table)
                if builtins.all(item.get(k) == v for k, v in eq.items())
            ]

        # 작은 수업용 데이터에서는 Scan + FilterExpression을 사용한다.
        condition = None
        for key, value in eq.items():
            part = Attr(key).eq(_to_dynamodb(value))
            condition = part if condition is None else condition & part
        return _sort_items(_scan(table, condition))

    return [
        item for item in all(table)
        if builtins.all(item.get(k) == v for k, v in eq.items())
    ]


def update(table: str, id: str, **fields):
    item = get(table, id)
    if item is None:
        return None
    item.update(fields)
    return put(table, item)


def delete(table: str, id: str) -> None:
    if _use_dynamodb():
        _ddb_table(table).delete_item(Key={'id': id})
        return

    _ensure(table)
    with _lock:
        _conn().execute(
            f'DELETE FROM "{table}" WHERE id=?', (id,)
        )
        _conn().commit()