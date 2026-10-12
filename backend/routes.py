"""Contrat REST partagé par FastAPI et le serveur local de dépannage."""
import re
from dataclasses import dataclass
from .service import Problem

@dataclass
class Route:
    method: str
    path: str
    status: int
    handler: object
    public: bool = False

def route_table(s):
    return [
        Route('GET','/api/health',200,lambda u,d,q,i: {'status':'ok','database':s.settings.db_backend,'ai':'on-demand'},True),
        Route('POST','/api/auth/register',201,lambda u,d,q,i:s.register(d),True),
        Route('POST','/api/auth/login',200,lambda u,d,q,i:s.login(d),True),
        Route('GET','/api/me',200,lambda u,d,q,i:u),
        Route('GET','/api/books',200,lambda u,d,q,i:s.books(u,q.get('q',''),q.get('category',''))),
        Route('POST','/api/books',201,lambda u,d,q,i:s.add_book(u,d)),
        Route('PATCH','/api/books/{id}',200,lambda u,d,q,i:s.edit_book(u,i,d)),
        Route('DELETE','/api/books/{id}',200,lambda u,d,q,i:s.delete_book(u,i)),
        Route('GET','/api/books/{id}/copies',200,lambda u,d,q,i:s.copies(u,i)),
        Route('POST','/api/books/{id}/copies',201,lambda u,d,q,i:s.add_copy(u,i,d)),
        Route('GET','/api/documents',200,lambda u,d,q,i:s.documents(u)),
        Route('GET','/api/documents/{id}',200,lambda u,d,q,i:{k:v for k,v in s.document(u,i).items() if k!='filename'}),
        Route('POST','/api/documents/{id}/reindex',200,lambda u,d,q,i:s.index_document(u,i)),
        Route('GET','/api/loans',200,lambda u,d,q,i:s.loans(u)),
        Route('POST','/api/loans',201,lambda u,d,q,i:s.loan(u,d)),
        Route('PATCH','/api/loans/{id}/return',200,lambda u,d,q,i:s.return_loan(u,i)),
        Route('GET','/api/reservations',200,lambda u,d,q,i:s.reservations(u)),
        Route('POST','/api/reservations',201,lambda u,d,q,i:s.reserve(u,d)),
        Route('DELETE','/api/reservations/{id}',200,lambda u,d,q,i:s.cancel_reservation(u,i)),
        Route('POST','/api/questions',200,lambda u,d,q,i:s.question(u,d)),
        Route('POST','/api/summarize',200,lambda u,d,q,i:s.analyze(u,'summary',d)),
        Route('POST','/api/key-concepts',200,lambda u,d,q,i:s.analyze(u,'concepts',d)),
        Route('POST','/api/comparisons',200,lambda u,d,q,i:s.analyze(u,'comparison',d)),
        Route('GET','/api/recommendations',200,lambda u,d,q,i:s.recommendations(u,q.get('interests',''))),
        Route('GET','/api/history',200,lambda u,d,q,i:s.history(u)),
        Route('GET','/api/favorites',200,lambda u,d,q,i:s.favorites(u)),
        Route('POST','/api/favorites',201,lambda u,d,q,i:s.add_favorite(u,d)),
        Route('DELETE','/api/favorites/{id}',200,lambda u,d,q,i:s.delete_favorite(u,i)),
        Route('GET','/api/collections',200,lambda u,d,q,i:s.collections(u)),
        Route('POST','/api/collections',201,lambda u,d,q,i:s.add_collection(u,d)),
        Route('POST','/api/collections/{id}/items',201,lambda u,d,q,i:s.collection_item(u,i,d)),
        Route('GET','/api/notifications',200,lambda u,d,q,i:s.notifications(u)),
        Route('GET','/api/admin/statistics',200,lambda u,d,q,i:s.stats(u)),
        Route('GET','/api/admin/users',200,lambda u,d,q,i:s.users(u)),
        Route('PATCH','/api/admin/users/{id}',200,lambda u,d,q,i:s.edit_user(u,i,d)),
        Route('POST','/api/admin/reminders',200,lambda u,d,q,i:s.reminders(u)),
        Route('POST','/api/feedback',201,lambda u,d,q,i:s.feedback(u,d)),
    ]

class Router:
    def __init__(self, service):
        self.service = service
        self.routes = route_table(service)

    def dispatch(self, method, path, token='', data=None, query=None):
        data = {} if data is None else data
        if not isinstance(data,dict):raise Problem(422,'Objet JSON requis')
        for route in self.routes:
            match = re.fullmatch(re.escape(route.path).replace(r'\{id\}', r'(?P<id>\d+)'), path)
            if route.method==method and match:
                user = None if route.public else self.service.authenticate(token)
                identifier = int(match.group('id')) if 'id' in match.groupdict() else None
                if identifier is not None and identifier<1:raise Problem(422,'Identifiant invalide')
                return route.status, route.handler(user,data,query or {},identifier)
        raise Problem(404,'Endpoint introuvable')

