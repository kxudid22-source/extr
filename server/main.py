import asyncio
import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiohttp import web
import db
import repo

PORT = int(os.getenv("PORT", "8080"))
WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

routes = web.RouteTableDef()

@routes.get("/api/health")
async def health(request):
    return web.json_response({"status": "ok", "service": "messenger888"})

@routes.get("/api/products")
async def products(request):
    return web.json_response(repo.get_products())

@routes.post("/api/register")
async def register(request):
    data = await request.json()
    uid = int(data["user_id"])
    repo.upsert_user(uid, data.get("username"), data.get("first_name"), data.get("last_name"))
    repo.update_last_seen(uid)
    user = repo.get_user(uid)
    return web.json_response(user or {})

@routes.get("/api/user/{user_id}")
async def get_user(request):
    uid = int(request.match_info["user_id"])
    user = repo.get_user(uid)
    if not user:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(user)

@routes.get("/api/numbers")
async def numbers(request):
    uid = request.query.get("user_id")
    if uid:
        return web.json_response(repo.get_user_numbers(int(uid)))
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM numbers").fetchall()
    conn.close()
    return web.json_response([dict(r) for r in rows])

@routes.post("/api/numbers/buy")
async def buy_number_api(request):
    data = await request.json()
    uid = int(data["user_id"])
    repo.upsert_user(uid)
    num = repo.buy_number(uid)
    if not num:
        return web.json_response({"error": "no numbers"}, status=400)
    return web.json_response(num)

@routes.post("/api/numbers/import")
async def import_number_api(request):
    # номер, купленный в мессенджере, добавляется в бота
    data = await request.json()
    uid = int(data["user_id"])
    number = data["number"]
    repo.upsert_user(uid)
    conn = db.get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO numbers(number, owner_id, status, purchased_at) VALUES (?,?,?,?)",
                    (number, uid, "sold", db.now()))
    except Exception:
        pass
    conn.commit()
    conn.close()
    return web.json_response({"ok": True, "number": number})

@routes.post("/api/products/buy")
async def buy_product_api(request):
    data = await request.json()
    uid = int(data["user_id"])
    pid = int(data["product_id"])
    repo.upsert_user(uid)
    prod, status = repo.buy_product(uid, pid)
    if status != "ok":
        return web.json_response({"error": status}, status=400)
    return web.json_response({"product": prod, "status": "ok"})

@routes.get("/api/accounts/search")
async def search_accounts(request):
    q = request.query.get("q", "")
    return web.json_response(repo.search_accounts(q))

@routes.post("/api/accounts")
async def create_account(request):
    data = await request.json()
    uid = int(data["user_id"])
    repo.upsert_user(uid, data.get("username"), data.get("first_name"))
    repo.ensure_account(uid, data.get("username") or f"user{uid}", data.get("display_name"), data.get("bio"))
    return web.json_response({"ok": True})

@routes.get("/api/friends")
async def friends(request):
    uid = int(request.query["user_id"])
    return web.json_response({
        "friends": repo.get_friends(uid),
        "pending": repo.get_pending_requests(uid),
    })

@routes.post("/api/friends/request")
async def friend_request(request):
    data = await request.json()
    uid = int(data["user_id"])
    fid = int(data["friend_id"])
    repo.upsert_user(fid)
    ok, status = repo.send_friend_request(uid, fid)
    return web.json_response({"ok": ok, "status": status})

@routes.post("/api/friends/respond")
async def friend_respond(request):
    data = await request.json()
    repo.respond_friend(int(data["request_id"]), bool(data.get("accept", True)))
    return web.json_response({"ok": True})

@routes.post("/api/messages")
async def send_message_api(request):
    data = await request.json()
    fid = int(data["from_id"])
    tid = int(data["to_id"])
    text = data["text"]
    repo.upsert_user(fid)
    repo.upsert_user(tid)
    repo.send_message(fid, tid, text)
    repo.update_last_seen(fid)
    return web.json_response({"ok": True})

@routes.get("/api/messages")
async def get_messages_api(request):
    uid = int(request.query["user_id"])
    pid = int(request.query["peer_id"])
    since = int(request.query.get("since", "0"))
    repo.update_last_seen(uid)
    msgs = repo.get_messages(uid, pid, since)
    return web.json_response(msgs)

@routes.get("/api/conversations")
async def conversations_api(request):
    uid = int(request.query["user_id"])
    repo.update_last_seen(uid)
    return web.json_response(repo.get_conversations(uid))

@routes.post("/api/read")
async def read_api(request):
    data = await request.json()
    repo.mark_read(int(data["user_id"]), int(data["peer_id"]))
    return web.json_response({"ok": True})

@routes.get("/api/unread")
async def unread_api(request):
    uid = int(request.query["user_id"])
    return web.json_response({"count": repo.get_unread_count(uid)})

@routes.get("/api/numbers/check")
async def check_number_api(request):
    number = request.query.get("number", "").strip()
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM numbers WHERE number=? AND status='sold'", (number,)).fetchone()
    conn.close()
    if not row:
        return web.json_response({"ok": False, "error": "not_found"})
    return web.json_response({"ok": True, "number": number, "owner": row["owner_id"]})

@routes.get("/")
async def index(request):
    return web.FileResponse(os.path.join(WEB_DIR, "index.html"))

async def init_app():
    db.init_db()
    app = web.Application()
    app.add_routes(routes)
    # static
    app.router.add_static("/static/", path=WEB_DIR, name="static")
    # cors middleware
    async def cors_middleware(app, handler):
        async def middleware(request):
            if request.method == "OPTIONS":
                return web.Response(status=204, headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                })
            resp = await handler(request)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            return resp
        return middleware
    app.middlewares.append(cors_middleware)
    return app

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = loop.run_until_complete(init_app())
    web.run_app(app, port=PORT)

if __name__ == "__main__":
    main()
