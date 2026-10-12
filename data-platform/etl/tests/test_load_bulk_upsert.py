from etl.src.load import bulk_upsert

class _Result:
    def __iter__(self):
        return iter([])

class _Conn:
    def __init__(self):
        self.upserts = 0

    def execute(self, query, params=None):
        if str(query).lstrip().startswith("INSERT INTO t"):
            self.upserts += 1
        return _Result()

def test_bulk_upsert_executes_each_chunk_once_and_passes_real_connection():
    conn = _Conn()
    history_calls = []
    records = [{"k": i, "v": i} for i in range(3)]

    inserted, updated = bulk_upsert(
        None, "t", ["k", "v"], ["k"], records,
        connection=conn,
        history_copy_fn=lambda c, chunk: history_calls.append(c),
    )

    assert (inserted, updated) == (3, 0)
    assert conn.upserts == 1
    assert history_calls == [conn]
