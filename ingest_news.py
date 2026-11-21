"""本地 n8n Webhook 接收器：默认只监听 localhost；必须设置 INGEST_TOKEN。"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from services.db import initialize, save_news

TOKEN = os.getenv('INGEST_TOKEN', '')
HOST = os.getenv('INGEST_HOST', '127.0.0.1')
PORT = int(os.getenv('INGEST_PORT', '8765'))

class Handler(BaseHTTPRequestHandler):
    def answer(self, code, body):
        content = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path == '/health':
            self.answer(200, {'status':'ok'})
        else:
            self.answer(404, {'error':'not found'})

    def do_POST(self):
        if self.path != '/ingest/news':
            return self.answer(404, {'error':'not found'})
        if self.headers.get('Authorization','') != 'Bearer ' + TOKEN:
            return self.answer(401, {'error':'unauthorized'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > 1024*1024:
                return self.answer(413, {'error':'payload must be 1 byte to 1 MB'})
            body = json.loads(self.rfile.read(size))
            items = body if isinstance(body, list) else body.get('items', [body])
            if not isinstance(items, list) or len(items) > 100:
                raise ValueError('一次最多提交 100 条')
            for item in items:
                save_news(item)
            self.answer(200, {'received':len(items)})
        except (ValueError, TypeError, KeyError) as e:
            self.answer(400, {'error':str(e)})

if __name__ == '__main__':
    if not TOKEN:
        raise SystemExit('先设置 INGEST_TOKEN，接收器才会启动')
    initialize()
    print(f'n8n ingestion ready: http://{HOST}:{PORT}/ingest/news')
    ThreadingHTTPServer((HOST,PORT), Handler).serve_forever()
