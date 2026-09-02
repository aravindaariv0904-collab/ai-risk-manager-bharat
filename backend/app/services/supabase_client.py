import json
import psycopg2
import psycopg2.extras
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from app.config import settings

@dataclass
class QueryResult:
    data: Any
    count: Optional[int] = None

class PostgresTableQuery:
    def __init__(self, table_name: str, get_conn_fn):
        self.table_name = table_name
        self.get_conn = get_conn_fn
        self.action = "SELECT"
        self.select_cols = "*"
        self.exact_count = False
        self.where_clauses: List[str] = []
        self.params: List[Any] = []
        self.order_by: Optional[str] = None
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self.is_single = False
        self.is_maybe_single = False
        self.insert_data: Optional[Any] = None
        self.update_data: Optional[Dict] = None

    def select(self, cols: str = "*", count: Optional[str] = None):
        self.action = "SELECT"
        self.select_cols = cols
        if count == "exact":
            self.exact_count = True
        return self

    def insert(self, data: Any):
        self.action = "INSERT"
        self.insert_data = data
        return self

    def update(self, data: Dict):
        self.action = "UPDATE"
        self.update_data = data
        return self

    def eq(self, col: str, val: Any):
        self.where_clauses.append(f'"{col}" = %s')
        self.params.append(str(val) if isinstance(val, type(settings)) else val)
        return self

    def in_(self, col: str, vals: List[Any]):
        if not vals:
            self.where_clauses.append("1=0")
        else:
            placeholders = ", ".join(["%s"] * len(vals))
            self.where_clauses.append(f'"{col}" IN ({placeholders})')
            self.params.extend(vals)
        return self

    def ilike(self, col: str, pattern: str):
        self.where_clauses.append(f'"{col}"::text ILIKE %s')
        self.params.append(pattern)
        return self

    def like(self, col: str, pattern: str):
        self.where_clauses.append(f'"{col}"::text LIKE %s')
        self.params.append(pattern)
        return self

    def gte(self, col: str, val: Any):
        self.where_clauses.append(f'"{col}" >= %s')
        self.params.append(val)
        return self

    def lte(self, col: str, val: Any):
        self.where_clauses.append(f'"{col}" <= %s')
        self.params.append(val)
        return self

    def order(self, col: str, desc: bool = False):
        direction = "DESC" if desc else "ASC"
        self.order_by = f'"{col}" {direction}'
        return self

    def limit(self, count: int):
        self._limit = count
        return self

    def range(self, start: int, end: int):
        self._offset = start
        self._limit = (end - start) + 1
        return self

    def single(self):
        self.is_single = True
        self._limit = 1
        return self

    def maybe_single(self):
        self.is_maybe_single = True
        self._limit = 1
        return self

    def execute(self) -> QueryResult:
        conn = self.get_conn()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            if self.action == "SELECT":
                total_count = None
                where_sql = (" WHERE " + " AND ".join(self.where_clauses)) if self.where_clauses else ""
                
                if self.exact_count:
                    count_query = f'SELECT COUNT(*) as c FROM "{self.table_name}"{where_sql};'
                    cur.execute(count_query, self.params)
                    total_count = cur.fetchone()["c"]

                query = f'SELECT * FROM "{self.table_name}"{where_sql}'
                if self.order_by:
                    query += f" ORDER BY {self.order_by}"
                if self._limit is not None:
                    query += f" LIMIT {self._limit}"
                if self._offset is not None:
                    query += f" OFFSET {self._offset}"
                query += ";"

                cur.execute(query, self.params)
                rows = cur.fetchall()
                data = [dict(r) for r in rows]

                if self.is_single or self.is_maybe_single:
                    return QueryResult(data=data[0] if data else None, count=total_count)
                return QueryResult(data=data, count=total_count if total_count is not None else len(data))

            elif self.action == "INSERT":
                items = self.insert_data if isinstance(self.insert_data, list) else [self.insert_data]
                returned_rows = []
                for item in items:
                    cols = list(item.keys())
                    vals = []
                    col_names = []
                    for c in cols:
                        col_names.append(f'"{c}"')
                        val = item[c]
                        if isinstance(val, (dict, list)):
                            vals.append(json.dumps(val))
                        else:
                            vals.append(val)
                    
                    placeholders = ", ".join(["%s"] * len(cols))
                    query = f'INSERT INTO "{self.table_name}" ({", ".join(col_names)}) VALUES ({placeholders}) RETURNING *;'
                    cur.execute(query, vals)
                    r = cur.fetchone()
                    if r:
                        returned_rows.append(dict(r))
                conn.commit()
                return QueryResult(data=returned_rows if isinstance(self.insert_data, list) else (returned_rows if returned_rows else []))

            elif self.action == "UPDATE":
                where_sql = (" WHERE " + " AND ".join(self.where_clauses)) if self.where_clauses else ""
                set_clauses = []
                update_params = []
                for k, v in self.update_data.items():
                    set_clauses.append(f'"{k}" = %s')
                    if isinstance(v, (dict, list)):
                        update_params.append(json.dumps(v))
                    else:
                        update_params.append(v)
                
                query = f'UPDATE "{self.table_name}" SET {", ".join(set_clauses)}{where_sql} RETURNING *;'
                cur.execute(query, update_params + self.params)
                rows = cur.fetchall()
                conn.commit()
                return QueryResult(data=[dict(r) for r in rows])

            return QueryResult(data=[])
        finally:
            conn.close()

class PostgresClient:
    def get_conn(self):
        # Connect to Supabase Postgres via IPv4 Pooler (ap-southeast-1)
        try:
            return psycopg2.connect(
                dbname="postgres",
                user="postgres.digktcqwnvkdfyhgkroc",
                password="Aariv@948*##",
                host="aws-0-ap-southeast-1.pooler.supabase.com",
                port=6543,
                connect_timeout=8,
            )
        except Exception:
            return psycopg2.connect(
                dbname="postgres",
                user="postgres",
                password="Aariv@948*##",
                host="db.digktcqwnvkdfyhgkroc.supabase.co",
                port=5432,
                connect_timeout=8,
            )

    def table(self, name: str):
        return PostgresTableQuery(name, self.get_conn)

_client = PostgresClient()

def get_supabase_admin():
    return _client

def get_supabase_anon():
    return _client