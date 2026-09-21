from replyqueue.match.fts_backend import FTSBackend, query_terms
from tests.conftest import make_item


def test_fts_ranks_relevant_above_irrelevant(conn, cfg):
    a = make_item(conn, "t3_a", "How do I find my first customers?",
                  "I am struggling to get customers for my startup, what worked for you?")
    b = make_item(conn, "t3_b", "Best mechanical keyboard?",
                  "Looking for a clicky keyboard for gaming.")
    backend = FTSBackend(cfg)
    items = [dict(r) for r in conn.execute("SELECT id, title, body FROM items").fetchall()]
    backend.index(conn, items)
    ranked = backend.rank(conn, cfg.icp, cfg.keywords)
    assert ranked[a] > ranked[b]


def test_query_terms_strip_stopwords():
    terms = query_terms("I sell to founders who want customers and growth", ["lead gen"])
    assert "founders" in terms and "customers" in terms
    assert "the" not in terms and "and" not in terms

def test_single_match_gets_a_nonzero_score(conn, cfg):
    item_id = make_item(
        conn,
        "t3_single",
        "Founder wants customer acquisition advice",
        "Looking for community-led growth recommendations",
    )
    backend = FTSBackend(cfg)
    backend.index(conn, [dict(conn.execute(
        "SELECT id, title, body FROM items WHERE id = ?", (item_id,)
    ).fetchone())])

    ranked = backend.rank(conn, "community growth", ["recommend"])

    assert ranked == {item_id: 1.0}


def test_tied_matches_are_not_dropped(conn, cfg):
    first = make_item(
        conn, "t3_tie_0", "Need community growth", "recommend community growth"
    )
    conn.execute(
        "INSERT INTO items(source, source_id, channel, title, body, ingested_at, "
        "content_hash, prefilter_pass) VALUES (?, ?, ?, ?, ?, datetime('now'), ?, 1)",
        ("reddit_rss", "t3_tie_1", "startups", "Need community growth",
         "recommend community growth", "distinct-ingest-hash"),
    )
    conn.commit()
    second = conn.execute("SELECT id FROM items WHERE source_id='t3_tie_1'").fetchone()["id"]
    ids = [first, second]
    rows = conn.execute(
        "SELECT id, title, body FROM items WHERE id IN (?, ?)", ids
    ).fetchall()
    backend = FTSBackend(cfg)
    backend.index(conn, [dict(row) for row in rows])

    ranked = backend.rank(conn, "community growth", ["recommend"])

    assert ranked == {item_id: 1.0 for item_id in ids}
