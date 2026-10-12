"""Serveur REST de dépannage sans dépendances : localhost uniquement."""
import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from .config import Settings
from .service import Library, Problem
from .routes import Router

def make_server(settings, port=8000):
    library=Library(settings);router=Router(library)
    class Handler(BaseHTTPRequestHandler):
        def handle_request(self):
            path=urlsplit(self.path);query={k:v[-1] for k,v in parse_qs(path.query).items()}
            token=self.headers.get('Authorization','')
            token=token[7:] if token.startswith('Bearer ') else ''
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<=length<=1024*1024:raise Problem(413,'Requête trop volumineuse')
                data=json.loads(self.rfile.read(length)) if length else None
                if path.path=='/api/auth/logout' and self.command=='POST':
                    library.authenticate(token);status,result=200,library.logout(token)
                else:status,result=router.dispatch(self.command,path.path,token,data,query)
            except Problem as exc:status,result=exc.status,{'detail':exc.detail}
            except (json.JSONDecodeError,ValueError):status,result=422,{'detail':'Requête JSON invalide'}
            except Exception:
                logging.exception('Erreur interne');status,result=500,{'detail':'Erreur interne'}
            payload=json.dumps(result,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        do_GET=do_POST=do_PATCH=do_DELETE=handle_request
        def log_message(self, *args):pass
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.library=library
    return server

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    server=make_server(Settings(),args.port)
    print(f'API de dépannage : http://127.0.0.1:{server.server_port}/api/health',flush=True)
    print('PDF multipart et Swagger nécessitent FastAPI ; voir README.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

