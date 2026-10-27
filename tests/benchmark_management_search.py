"""Explicit restricted-role search measurement; not a voice performance gate."""

import asyncio
import json
import statistics
import time

from alojan.auth import connection
from alojan.calls import COLUMNS, JOINS
from alojan.call_search import filters
from test_action_delivery import finalize
from test_call_search import window
import test_call_management as fixtures

accounts, database, dedicated = fixtures.accounts, fixtures.database, fixtures.dedicated
prepared, history = fixtures.prepared, fixtures.history


def test_measure_scoped_search_with_ten_thousand_calls(accounts, history):
    one, summaries, store = history
    token, scope, _ = one["author"]
    asyncio.run(finalize(summaries))
    with connection(accounts.dsn) as c:
        prototype = c.execute("SELECT call_id FROM call_route_snapshots LIMIT 1").fetchone()[0]
        c.execute(
            """CREATE TEMP TABLE benchmark_calls ON COMMIT DROP AS
            SELECT gen_random_uuid() AS id,n,now()-n*interval '1 second' AS created_at
            FROM generate_series(1,10000) n"""
        )
        c.execute(
            """INSERT INTO calls(id,sip_call_id,direction,status,started_at,ended_at)
            SELECT id,'synthetic-search-'||n,'inbound','ended',created_at,created_at
            FROM benchmark_calls"""
        )
        c.execute(
            """INSERT INTO call_route_snapshots
            (call_id,scope_id,number_id,binding_id,profile_id,release_id,node_id,
             called_e164,called_source,manifest_digest,created_at)
            SELECT k.id,s.scope_id,s.number_id,s.binding_id,s.profile_id,s.release_id,s.node_id,
                   s.called_e164,s.called_source,s.manifest_digest,k.created_at
            FROM benchmark_calls k CROSS JOIN call_route_snapshots s WHERE s.call_id=%s""",
            (prototype,),
        )
        c.execute(
            """INSERT INTO call_finalizations(call_id,scope_id,release_id,summary_status,payload)
            SELECT k.id,s.scope_id,s.release_id,'done',
                jsonb_build_object('summary',jsonb_build_object('subject',
                    CASE WHEN k.n%%10=0 THEN 'synthetic needle' ELSE 'synthetic neutral' END))
            FROM benchmark_calls k CROSS JOIN call_route_snapshots s WHERE s.call_id=%s""",
            (prototype,),
        )
        c.execute(
            """INSERT INTO utterances(id,call_id,speaker,text,is_final)
            SELECT gen_random_uuid(),k.id,'caller',
                CASE WHEN k.n%10=0 AND u=1 THEN 'synthetic needle'
                     ELSE repeat('synthetic neutral ',20) END,true
            FROM benchmark_calls k CROSS JOIN generate_series(1,5) u"""
        )
        for table in ("calls", "call_route_snapshots", "call_finalizations", "utterances"):
            c.execute("ANALYZE " + table)
    results = []
    for source in ("summary", "transcript"):
        for query in ("needle", "absent-needle"):
            values = window() | dict(search_in=source, query=query)
            clauses, args = filters(values)
            with store.accounts.workspace(token, scope) as (c, _):
                plan = c.execute(
                    "EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT "
                    + COLUMNS
                    + " "
                    + JOINS
                    + " WHERE s.scope_id=%s"
                    + clauses
                    + " ORDER BY s.created_at DESC,s.call_id DESC LIMIT 51",
                    [scope, *args],
                ).fetchone()[0][0]
            timings = []
            for _ in range(10):
                start = time.perf_counter()
                result = store.list(token, scope, **values)
                timings.append(1000 * (time.perf_counter() - start))
                assert len(result["calls"]) == (50 if query == "needle" else 0)
            results.append(
                dict(
                    source=source,
                    query=query,
                    samples=len(timings),
                    median_ms=round(statistics.median(timings), 2),
                    maximum_ms=round(max(timings), 2),
                    plan=plan,
                )
            )
    print("\nSEARCH_BENCHMARK=" + json.dumps(results))
