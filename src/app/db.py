from typing import Any, Optional, Dict, List

# Tiny D1 wrapper
class D1:
    def __init__(self, env: Any):
        self._db = env.DB  # requires binding "DB" in dashboard

    async def all(self, sql: str, *params) -> List[Dict]:
        stmt = self._db.prepare(sql)
        if params: stmt = stmt.bind(*params)
        return await stmt.all()

    async def first(self, sql: str, *params) -> Optional[Dict]:
        stmt = self._db.prepare(sql)
        if params: stmt = stmt.bind(*params)
        return await stmt.first()

    async def run(self, sql: str, *params) -> Dict:
        stmt = self._db.prepare(sql)
        if params: stmt = stmt.bind(*params)
        return await stmt.run()