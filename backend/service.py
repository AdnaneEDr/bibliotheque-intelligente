"""Règles métier indépendantes du transport HTTP et de l'interface."""
import json
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .db import Database
from .security import hash_password, verify_password, token_hash, now, expiry
from .rag import Rag, AIUnavailable

class Problem(Exception):
    def __init__(self, status, detail):
        self.status, self.detail = status, detail
        super().__init__(detail)

def text(data, key, maximum=1000, optional=False):
    value = data.get(key, '' if optional else None)
    if not isinstance(value, str) or (not optional and not value.strip()) or len(value) > maximum:
        raise Problem(422, f'Champ {key} invalide (maximum {maximum} caractères)')
    return value.strip()

def integer(data, key, optional=False):
    value = data.get(key)
    if optional and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise Problem(422, f'{key} doit être un entier positif')
    return value

def public_user(user):
    return {key: user[key] for key in ('id', 'email', 'name', 'role', 'active')}

class Library:
    def __init__(self, settings, rag=None):
        self.settings = settings
        self.db = Database(settings)
        self.rag = rag or Rag(settings)

    def authenticate(self, token):
        if not token or len(token) > 200:
            raise Problem(401, 'Authentification requise')
        with self.db.transaction() as tx:
            user = tx.one('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=:token AND s.expires_at>:now AND u.active=1', {'token': token_hash(token), 'now': now()})
        if not user:
            raise Problem(401, 'Session expirée ou invalide')
        return public_user(user)

    @staticmethod
    def staff(user):
        if user['role'] not in ('librarian', 'admin'):
            raise Problem(403, 'Action réservée au personnel autorisé')

    @staticmethod
    def admin(user):
        if user['role'] != 'admin':
            raise Problem(403, 'Action réservée aux administrateurs')

    @staticmethod
    def required(row, label='Ressource'):
        if not row:
            raise Problem(404, label+' introuvable')
        return row

    def register(self, data):
        email = text(data, 'email', 254).lower()
        name, password = text(data, 'name', 120), text(data, 'password', 128)
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(password) < 10:
            raise Problem(422, 'Adresse email invalide ou mot de passe trop court (10 caractères minimum)')
        encoded = hash_password(password)
        with self.db.transaction() as tx:
            if tx.one('SELECT id FROM users WHERE email=:email', {'email': email}):
                raise Problem(409, 'Ce compte existe déjà')
            account_id = tx.insert('users', email=email, name=name, password_hash=encoded, role='student', active=1, created_at=now())
            return public_user(tx.one('SELECT * FROM users WHERE id=:id', {'id': account_id}))

    def login(self, data):
        email, password = text(data, 'email', 254).lower(), text(data, 'password', 128)
        with self.db.transaction() as tx:
            user = tx.one('SELECT * FROM users WHERE email=:email', {'email': email})
        # Hash a dummy candidate as well to reduce timing differences for absent accounts.
        encoded = user['password_hash'] if user else hash_password('dummy-account-password')
        if not verify_password(password, encoded) or not user or not user['active']:
            raise Problem(401, 'Identifiants invalides')
        token = secrets.token_urlsafe(48)
        with self.db.transaction() as tx:
            tx.execute('DELETE FROM sessions WHERE expires_at<=:now', {'now': now()}).close()
            tx.insert('sessions', user_id=user['id'], token_hash=token_hash(token), expires_at=expiry(self.settings.token_hours))
        return {'access_token': token, 'token_type': 'bearer', 'user': public_user(user)}

    def logout(self, token):
        with self.db.transaction() as tx:
            tx.execute('DELETE FROM sessions WHERE token_hash=:token', {'token': token_hash(token)}).close()
        return {'ok': True}

    def books(self, user, q='', category=''):
        if len(q) > 200 or len(category) > 100:
            raise Problem(422, 'Filtre trop long')
        category_clause = ' AND b.category=:cat' if category else ''
        params = {'q': '%'+q.lower()+'%'}
        if category:params['cat']=category
        with self.db.transaction() as tx:
            return tx.rows('''SELECT b.*,
                (SELECT COUNT(*) FROM copies c WHERE c.book_id=b.id) AS total_copies,
                (SELECT COUNT(*) FROM copies c WHERE c.book_id=b.id AND NOT EXISTS
                    (SELECT 1 FROM loans l WHERE l.copy_id=c.id AND l.returned_at IS NULL)) AS available_copies
                FROM books b WHERE (LOWER(b.title) LIKE :q OR LOWER(b.author) LIKE :q)'''+category_clause+' ORDER BY b.title', params)

    def add_book(self, user, data):
        self.staff(user)
        values = dict(title=text(data, 'title', 240), author=text(data, 'author', 200), category=text(data, 'category', 100), description=text(data, 'description', 4000, True))
        with self.db.transaction() as tx:
            identifier = tx.insert('books', **values)
        return {'id': identifier, **values}

    def edit_book(self, user, identifier, data):
        self.staff(user)
        allowed = {'title': 240, 'author': 200, 'category': 100, 'description': 4000}
        values = {k: text(data, k, n, k=='description') for k, n in allowed.items() if k in data}
        if not values or set(data)-set(allowed):
            raise Problem(422, 'Champs du livre invalides')
        with self.db.transaction() as tx:
            self.required(tx.lock('books', identifier), 'Livre')
            tx.execute('UPDATE books SET '+', '.join(k+'=:'+k for k in values)+' WHERE id=:id', {**values, 'id': identifier}).close()
            return tx.one('SELECT * FROM books WHERE id=:id', {'id': identifier})

    def delete_book(self, user, identifier):
        self.staff(user)
        with self.db.transaction() as tx:
            self.required(tx.lock('books', identifier), 'Livre')
            used = tx.one('SELECT l.id FROM loans l JOIN copies c ON c.id=l.copy_id WHERE c.book_id=:id', {'id': identifier})
            reserved = tx.one("SELECT id FROM reservations WHERE book_id=:id AND status='active'", {'id': identifier})
            if used or reserved:
                raise Problem(409, 'Livre lié à un historique d’emprunt ou une réservation active')
            for table in ('collection_items', 'favorites', 'reservations', 'copies'):
                tx.execute(f'DELETE FROM {table} WHERE book_id=:id', {'id': identifier}).close()
            tx.execute('DELETE FROM books WHERE id=:id', {'id': identifier}).close()
        return {'ok': True}

    def add_copy(self, user, identifier, data):
        self.staff(user)
        code = text(data, 'code', 80)
        with self.db.transaction() as tx:
            self.required(tx.lock('books', identifier), 'Livre')
            if tx.one('SELECT id FROM copies WHERE code=:code', {'code': code}):
                raise Problem(409, 'Code exemplaire déjà utilisé')
            return {'id': tx.insert('copies', book_id=identifier, code=code), 'book_id': identifier, 'code': code}

    def copies(self, user, identifier):
        with self.db.transaction() as tx:
            self.required(tx.one('SELECT id FROM books WHERE id=:id', {'id': identifier}), 'Livre')
            return tx.rows('SELECT c.*, (SELECT COUNT(*) FROM loans l WHERE l.copy_id=c.id AND l.returned_at IS NULL) AS on_loan FROM copies c WHERE c.book_id=:id ORDER BY c.id', {'id': identifier})

    def loan(self, user, data):
        self.staff(user)
        cid, account_id = integer(data, 'copy_id'), integer(data, 'student_id')
        with self.db.transaction() as tx:
            copy = self.required(tx.one('SELECT * FROM copies WHERE id=:id', {'id': cid}), 'Exemplaire')
            tx.lock('books', copy['book_id'])
            student = self.required(tx.lock('users', account_id), 'Étudiant')
            if not student['active'] or student['role'] != 'student':
                raise Problem(409, 'Compte étudiant inactif ou invalide')
            if tx.one('SELECT id FROM loans WHERE copy_id=:id AND returned_at IS NULL', {'id': cid}):
                raise Problem(409, 'Exemplaire indisponible')
            queue = tx.rows("SELECT * FROM reservations WHERE book_id=:id AND status='active' ORDER BY id", {'id': copy['book_id']})
            if queue and queue[0]['user_id'] != account_id:
                raise Problem(409, 'Priorité à l’étudiant ayant réservé en premier')
            if queue:
                tx.execute("UPDATE reservations SET status='fulfilled' WHERE id=:id", {'id': queue[0]['id']}).close()
            due = (datetime.now(timezone.utc)+timedelta(days=14)).isoformat()
            lid = tx.insert('loans', copy_id=cid, user_id=account_id, loaned_at=now(), due_at=due, returned_at=None)
            return {'id': lid, 'copy_id': cid, 'user_id': account_id, 'due_at': due}

    def loans(self, user):
        with self.db.transaction() as tx:
            where = '' if user['role'] in ('admin', 'librarian') else ' WHERE l.user_id=:account_id'
            return tx.rows('SELECT l.*, c.book_id, b.title, u.name FROM loans l JOIN copies c ON c.id=l.copy_id JOIN books b ON b.id=c.book_id JOIN users u ON u.id=l.user_id'+where+' ORDER BY l.id DESC', {} if not where else {'account_id': user['id']})

    def return_loan(self, user, identifier):
        self.staff(user)
        with self.db.transaction() as tx:
            loan = self.required(tx.one('SELECT l.*, c.book_id FROM loans l JOIN copies c ON c.id=l.copy_id WHERE l.id=:id', {'id': identifier}), 'Emprunt')
            tx.lock('books', loan['book_id'])
            current = tx.lock('loans', identifier)
            if current['returned_at']:
                raise Problem(409, 'Retour déjà enregistré')
            tx.execute('UPDATE loans SET returned_at=:now WHERE id=:id', {'now': now(), 'id': identifier}).close()
            reservation = tx.one("SELECT * FROM reservations WHERE book_id=:bid AND status='active' ORDER BY id", {'bid': loan['book_id']})
            if reservation:
                tx.insert('notifications', user_id=reservation['user_id'], message=f'Votre livre réservé (n° {loan["book_id"]}) est disponible. Contactez la bibliothèque.', created_at=now())
        return {'ok': True}

    def reserve(self, user, data):
        if user['role']!='student':
            raise Problem(403, 'Réservations réservées aux comptes étudiants')
        bid = integer(data, 'book_id')
        with self.db.transaction() as tx:
            self.required(tx.lock('books', bid), 'Livre')
            if tx.one("SELECT id FROM reservations WHERE user_id=:account_id AND book_id=:bid AND status='active'", {'account_id': user['id'], 'bid': bid}):
                raise Problem(409, 'Réservation déjà active')
            return {'id': tx.insert('reservations', book_id=bid, user_id=user['id'], status='active', created_at=now()), 'status': 'active'}

    def reservations(self, user):
        with self.db.transaction() as tx:
            return tx.rows('SELECT r.*, b.title FROM reservations r JOIN books b ON b.id=r.book_id WHERE user_id=:account_id ORDER BY r.id DESC', {'account_id': user['id']})

    def cancel_reservation(self, user, identifier):
        with self.db.transaction() as tx:
            reservation = self.required(tx.one('SELECT * FROM reservations WHERE id=:id', {'id': identifier}), 'Réservation')
            tx.lock('books', reservation['book_id'])
            reservation = tx.lock('reservations', identifier)
            if reservation['user_id'] != user['id']:
                raise Problem(403, 'Réservation appartenant à un autre utilisateur')
            if reservation['status'] != 'active':
                raise Problem(409, 'Réservation non active')
            tx.execute("UPDATE reservations SET status='cancelled' WHERE id=:id", {'id': identifier}).close()
        return {'ok': True}

    @staticmethod
    def can_read(user, doc):
        return doc['visibility']=='public' or doc['owner_id']==user['id'] or user['role']=='admin'

    def documents(self, user):
        with self.db.transaction() as tx:
            rows = tx.rows('SELECT * FROM documents ORDER BY id DESC')
        return [{k: v for k, v in row.items() if k!='filename'} for row in rows if self.can_read(user, row)]

    def document(self, user, identifier):
        with self.db.transaction() as tx:
            doc = self.required(tx.one('SELECT * FROM documents WHERE id=:id', {'id': identifier}), 'Document')
        if not self.can_read(user, doc):
            raise Problem(403, 'Document non autorisé')
        return doc

    def upload(self, user, title, visibility, payload):
        self.staff(user)
        title = text({'title': title}, 'title', 240)
        if visibility not in ('public', 'private'):
            raise Problem(422, 'Visibilité invalide')
        if not payload.startswith(b'%PDF-') or len(payload)>self.settings.max_pdf_mb*1024*1024:
            raise Problem(422, 'PDF invalide ou trop volumineux')
        filename = secrets.token_hex(16)+'.pdf'
        folder = self.settings.data_dir/'pdf';folder.mkdir(parents=True, exist_ok=True)
        path = folder/filename
        path.write_bytes(payload)
        try:
            with self.db.transaction() as tx:
                did = tx.insert('documents', title=title, owner_id=user['id'], visibility=visibility, filename=filename, status='pending', page_count=0, error=None, created_at=now())
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return self.index_document(user, did)

    def index_document(self, user, identifier):
        self.staff(user)
        doc = self.document(user, identifier)
        with self.db.transaction() as tx:
            locked = tx.lock('documents', identifier)
            if locked['status']=='indexing':
                raise Problem(409, 'Indexation en cours')
            tx.execute("UPDATE documents SET status='indexing', error=NULL WHERE id=:id", {'id': identifier}).close()
        try:
            count = self.rag.index(identifier, self.settings.data_dir/'pdf'/doc['filename'])
        except Exception as exc:
            detail = str(exc) if isinstance(exc, (ValueError, AIUnavailable)) else 'Échec d’indexation ; voir la configuration IA'
            with self.db.transaction() as tx:
                tx.execute("UPDATE documents SET status='failed', error=:error WHERE id=:id", {'error': detail[:300], 'id': identifier}).close()
            raise Problem(503 if isinstance(exc, AIUnavailable) else 422, f'Document {identifier} : '+detail) from exc
        with self.db.transaction() as tx:
            tx.execute("UPDATE documents SET status='ready', page_count=:count, error=NULL WHERE id=:id", {'count': count, 'id': identifier}).close()
        return {k: v for k, v in self.document(user, identifier).items() if k!='filename'}

    def save_interaction(self, user, kind, question, answer, passages, started):
        sources, seen = [], set()
        for passage in passages:
            key = (passage['document_id'], passage['page'])
            if key not in seen:
                doc = self.document(user, key[0])
                sources.append({'document_id': key[0], 'title': doc['title'], 'page': key[1]})
                seen.add(key)
        elapsed = int((time.perf_counter()-started)*1000)
        with self.db.transaction() as tx:
            iid = tx.insert('interactions', user_id=user['id'], kind=kind, question=question, answer=answer, sources_json=json.dumps(sources, ensure_ascii=False), processing_time_ms=elapsed, created_at=now())
        return {'interaction_id': iid, 'answer': answer, 'sources': sources, 'processing_time_ms': elapsed}

    def question(self, user, data):
        question = text(data, 'question', 2000)
        did = integer(data, 'document_id', True)
        started = time.perf_counter()
        if did:
            doc = self.document(user, did)
            if doc['status']!='ready':
                raise Problem(409, 'Document non indexé')
            allowed = [did]
        else:
            allowed = [d['id'] for d in self.documents(user) if d['status']=='ready']
        try:
            passages = self.rag.retrieve(question, allowed)
            answer = self.rag.generate(question, passages) if passages else 'Les documents accessibles ne permettent pas de répondre à cette question.'
        except AIUnavailable as exc:
            raise Problem(503, str(exc)) from exc
        return self.save_interaction(user, 'question', question, answer, passages, started)

    def analyze(self, user, kind, data):
        if kind=='comparison':
            identifiers = data.get('document_ids')
            if not isinstance(identifiers, list) or not 2<=len(identifiers)<=5:
                raise Problem(422, 'Fournir 2 à 5 documents distincts')
            for did in identifiers:integer({'id': did}, 'id')
            if len(set(identifiers))!=len(identifiers):
                raise Problem(422, 'Fournir des documents distincts')
        else:
            identifiers = [integer(data, 'document_id')]
        for identifier in identifiers:
            if self.document(user, identifier)['status']!='ready':
                raise Problem(409, 'Document non indexé')
        tasks = {'summary': 'Résume fidèlement ces documents.', 'concepts': 'Extrais et explique les notions clés de ces documents.', 'comparison': 'Compare les documents : points communs, différences, limites et sources.'}
        started = time.perf_counter()
        try:
            answer, sources = self.rag.analyze(tasks[kind], identifiers)
        except AIUnavailable as exc:
            raise Problem(503, str(exc)) from exc
        except ValueError as exc:
            raise Problem(422, str(exc)) from exc
        return self.save_interaction(user, kind, json.dumps(identifiers), answer, sources, started)

    def history(self, user):
        with self.db.transaction() as tx:
            rows = tx.rows('SELECT * FROM interactions WHERE user_id=:account_id ORDER BY id DESC', {'account_id': user['id']})
        for row in rows:row['sources'] = json.loads(row.pop('sources_json'))
        return rows

    def favorites(self, user):
        with self.db.transaction() as tx:
            return tx.rows('SELECT f.id AS favorite_id, b.* FROM favorites f JOIN books b ON b.id=f.book_id WHERE f.user_id=:account_id ORDER BY f.id', {'account_id': user['id']})

    def add_favorite(self, user, data):
        bid = integer(data, 'book_id')
        with self.db.transaction() as tx:
            tx.lock('users', user['id'])
            self.required(tx.one('SELECT id FROM books WHERE id=:id', {'id': bid}), 'Livre')
            if tx.one('SELECT id FROM favorites WHERE user_id=:account_id AND book_id=:bid', {'account_id': user['id'], 'bid': bid}):
                raise Problem(409, 'Favori déjà présent')
            return {'id': tx.insert('favorites', user_id=user['id'], book_id=bid)}

    def delete_favorite(self, user, identifier):
        with self.db.transaction() as tx:
            row = self.required(tx.one('SELECT * FROM favorites WHERE id=:id', {'id': identifier}), 'Favori')
            if row['user_id']!=user['id']:raise Problem(403, 'Favori non autorisé')
            tx.execute('DELETE FROM favorites WHERE id=:id', {'id': identifier}).close()
        return {'ok': True}

    def collections(self, user):
        with self.db.transaction() as tx:
            rows = tx.rows('SELECT * FROM collections WHERE user_id=:account_id ORDER BY id', {'account_id': user['id']})
            for row in rows:
                row['items'] = tx.rows('SELECT b.* FROM collection_items ci JOIN books b ON b.id=ci.book_id WHERE ci.collection_id=:id', {'id': row['id']})
        return rows

    def add_collection(self, user, data):
        name = text(data, 'name', 120)
        with self.db.transaction() as tx:
            return {'id': tx.insert('collections', user_id=user['id'], name=name), 'name': name}

    def collection_item(self, user, identifier, data):
        bid = integer(data, 'book_id')
        with self.db.transaction() as tx:
            row = self.required(tx.lock('collections', identifier), 'Collection')
            if row['user_id']!=user['id']:raise Problem(403, 'Collection non autorisée')
            self.required(tx.one('SELECT id FROM books WHERE id=:id', {'id': bid}), 'Livre')
            if tx.one('SELECT id FROM collection_items WHERE collection_id=:cid AND book_id=:bid', {'cid': identifier, 'bid': bid}):
                raise Problem(409, 'Ressource déjà présente')
            return {'id': tx.insert('collection_items', collection_id=identifier, book_id=bid)}

    def notifications(self, user):
        with self.db.transaction() as tx:
            return tx.rows('SELECT * FROM notifications WHERE user_id=:account_id ORDER BY id DESC', {'account_id': user['id']})

    def reminders(self, user):
        self.staff(user)
        count = 0
        with self.db.transaction() as tx:
            loans = tx.rows('SELECT * FROM loans WHERE returned_at IS NULL AND due_at<:now', {'now': now()})
            for loan in loans:
                message = f'Retard : merci de retourner votre emprunt n° {loan["id"]}.'
                if not tx.one('SELECT id FROM notifications WHERE user_id=:account_id AND message=:message', {'account_id': loan['user_id'], 'message': message}):
                    tx.insert('notifications', user_id=loan['user_id'], message=message, created_at=now());count+=1
        return {'created': count}

    def feedback(self, user, data):
        iid, rating = integer(data, 'interaction_id'), integer(data, 'rating')
        comment = text(data, 'comment', 1000, True)
        if rating>5:raise Problem(422, 'Note entre 1 et 5')
        with self.db.transaction() as tx:
            tx.lock('users', user['id'])
            row = self.required(tx.one('SELECT * FROM interactions WHERE id=:id', {'id': iid}), 'Interaction')
            if row['user_id']!=user['id']:raise Problem(403, 'Interaction non autorisée')
            if tx.one('SELECT id FROM feedback WHERE interaction_id=:id AND user_id=:account_id', {'id': iid, 'account_id': user['id']}):
                raise Problem(409, 'Évaluation déjà renseignée')
            return {'id': tx.insert('feedback', user_id=user['id'], interaction_id=iid, rating=rating, comment_text=comment)}

    def stats(self, user):
        self.admin(user)
        with self.db.transaction() as tx:
            result = {table: tx.one(f'SELECT COUNT(*) AS n FROM {table}')['n'] for table in ['users','books','documents','loans','reservations','interactions']}
            result['indexing'] = tx.rows('SELECT status, COUNT(*) AS n FROM documents GROUP BY status')
            result['ai'] = tx.one('SELECT AVG(processing_time_ms) AS avg_ms FROM interactions')
            result['feedback'] = tx.one('SELECT AVG(rating) AS avg_rating, COUNT(*) AS count FROM feedback')
            return result

    def users(self, user):
        self.staff(user)
        with self.db.transaction() as tx:
            return [public_user(row) for row in tx.rows('SELECT * FROM users ORDER BY id')]

    def edit_user(self, user, identifier, data):
        self.admin(user)
        role, active = data.get('role'), data.get('active')
        if role is not None and role not in ('student','librarian','admin'):raise Problem(422, 'Rôle invalide')
        if active is not None and not isinstance(active, bool):raise Problem(422, 'active doit être un booléen')
        if set(data)-{'role','active'} or not data:raise Problem(422, 'Champs utilisateur invalides')
        if identifier==user['id'] and (role not in (None,'admin') or active is False):
            raise Problem(409, 'Impossible de retirer vos propres droits administrateur')
        with self.db.transaction() as tx:
            row = self.required(tx.lock('users', identifier), 'Utilisateur')
            tx.execute('UPDATE users SET role=:role, active=:active WHERE id=:id', {'role': role or row['role'], 'active': row['active'] if active is None else int(active), 'id': identifier}).close()
            tx.execute('DELETE FROM sessions WHERE user_id=:account_id', {'account_id': identifier}).close()
            return public_user(tx.one('SELECT * FROM users WHERE id=:id', {'id': identifier}))

    def recommendations(self, user, interests=''):
        if len(interests)>500:raise Problem(422, 'Intérêts trop longs')
        catalog = self.books(user)
        # Similarity is computed locally over the authorized user's interests/history.
        questions = [h['question'] for h in self.history(user) if h['kind']=='question'][:5]
        favorites = [f'{b["title"]} {b["category"]}' for b in self.favorites(user)]
        query = ' '.join([interests]+questions+favorites)
        if not query.strip():
            return {'strategy': 'catalogue initial : renseigner les intérêts pour personnaliser', 'items': catalog[:6]}
        try:
            self.rag.load()
            texts = [query]+[f'{b["title"]} {b["category"]} {b["description"]}' for b in catalog]
            if not catalog:return {'strategy': 'similarité sémantique', 'items': []}
            vectors = self.rag.model.encode(texts, normalize_embeddings=True)
            scored = sorted(zip(catalog, [float(v @ vectors[0]) for v in vectors[1:]]), key=lambda pair: pair[1], reverse=True)
            return {'strategy': 'similarité sémantique', 'items': [{**b,'score': round(score,4)} for b,score in scored[:6]]}
        except AIUnavailable as exc:
            raise Problem(503, str(exc)) from exc
