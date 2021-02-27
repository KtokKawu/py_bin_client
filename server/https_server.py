# coding: utf-8

import http.server as serv
import ssl
from urllib.parse import urlparse
from urllib.parse import parse_qs
import gzip

class MyHandler(serv.BaseHTTPRequestHandler):
    def do_POST(self):
        content_len  = int(self.headers.get("content-length"))

        content = self.rfile.read(content_len)
        print(content)
        req_body = gzip.decompress(content)
        print(req_body)

        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream; charset=utf-8')
        self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', len(req_body))
        self.end_headers()
        # リクエストのバイナリを解凍してオウム返しする
        self.wfile.write(req_body)

host = '127.0.0.1'
port = 8000
httpd = serv.HTTPServer((host, port), MyHandler)
httpd.socket = ssl.wrap_socket(
    httpd.socket,
    keyfile="./server.key",
    certfile='./server.crt',
    server_side=True)
httpd.serve_forever()