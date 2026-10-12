import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File, Form, Depends
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse, FileResponse
from .config import Settings
from .service import Library, Problem
from .routes import Router

log = logging.getLogger('library.api')

@asynccontextmanager
async def lifespan(app):
    app.state.library = Library(Settings())
    app.state.router = Router(app.state.library)
    yield

app = FastAPI(title='Bibliothèque universitaire intelligente',version='1.0.0',lifespan=lifespan)
attempts = defaultdict(deque)
bearer_scheme = HTTPBearer(auto_error=False)

def bearer(request):
    header=request.headers.get('Authorization','')
    return header[7:] if header.startswith('Bearer ') else ''

@app.exception_handler(Problem)
async def problem_handler(request, exc):
    return JSONResponse(status_code=exc.status,content={'detail':exc.detail},headers={'WWW-Authenticate':'Bearer'} if exc.status==401 else None)

@app.middleware('http')
async def timing(request, call_next):
    start=time.perf_counter()
    if request.url.path in ('/api/auth/login','/api/auth/register'):
        key=request.client.host if request.client else 'local'
        queue=attempts[key];stamp=time.monotonic()
        while queue and queue[0]<stamp-300:queue.popleft()
        if len(queue)>=30:return JSONResponse(status_code=429,content={'detail':'Trop de tentatives. Réessayer dans quelques minutes.'})
        queue.append(stamp)
    response=await call_next(request)
    elapsed=int((time.perf_counter()-start)*1000)
    response.headers['X-Processing-Time-Ms']=str(elapsed)
    log.info('%s %s %s %sms',request.method,request.url.path,response.status_code,elapsed)
    return response

def register_routes():
    # Each endpoint stays visible in Swagger even though business rules are shared.
    from .routes import route_table
    for route in route_table(None):
        def factory(spec):
            if '{id}' in spec.path and spec.method in ('POST','PATCH'):
                def endpoint(id: int, request: Request, payload: dict):
                    status,result=request.app.state.router.dispatch(spec.method,request.url.path,bearer(request),payload,dict(request.query_params))
                    return JSONResponse(status_code=status,content=result)
            elif '{id}' in spec.path:
                def endpoint(id: int, request: Request):
                    status,result=request.app.state.router.dispatch(spec.method,request.url.path,bearer(request),None,dict(request.query_params))
                    return JSONResponse(status_code=status,content=result)
            elif spec.method in ('POST','PATCH'):
                def endpoint(request: Request, payload: dict):
                    status,result=request.app.state.router.dispatch(spec.method,request.url.path,bearer(request),payload,dict(request.query_params))
                    return JSONResponse(status_code=status,content=result)
            else:
                def endpoint(request: Request):
                    status,result=request.app.state.router.dispatch(spec.method,request.url.path,bearer(request),None,dict(request.query_params))
                    return JSONResponse(status_code=status,content=result)
            endpoint.__name__=spec.method.lower()+'_'+spec.path.replace('/','_').replace('{','').replace('}','')
            return endpoint
        app.add_api_route(route.path,factory(route),methods=[route.method],status_code=route.status,dependencies=[] if route.public else [Depends(bearer_scheme)])

register_routes()

@app.post('/api/auth/logout',dependencies=[Depends(bearer_scheme)])
def logout(request: Request):
    token=bearer(request);request.app.state.library.authenticate(token)
    return request.app.state.library.logout(token)

@app.post('/api/documents',status_code=201,dependencies=[Depends(bearer_scheme)])
def upload_document(request: Request, title: str=Form(...), visibility: str=Form('public'), file: UploadFile=File(...)):
    library=request.app.state.library
    user=library.authenticate(bearer(request));library.staff(user)
    payload=file.file.read(library.settings.max_pdf_mb*1024*1024+1)
    return library.upload(user,title,visibility,payload)

@app.get('/api/documents/{id}/file',dependencies=[Depends(bearer_scheme)])
def download_document(id: int, request: Request):
    library=request.app.state.library;user=library.authenticate(bearer(request));doc=library.document(user,id)
    return FileResponse(library.settings.data_dir/'pdf'/doc['filename'],media_type='application/pdf',filename=f'document-{id}.pdf')

