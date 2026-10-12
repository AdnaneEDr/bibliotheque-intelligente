import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from backend.config import Settings
from backend.service import Library, Problem
from backend.security import hash_password, now, token_hash, expiry
from backend.rag import chunks, SYSTEM, AIUnavailable
from backend.routes import Router
from backend.dev_server import make_server

class FakeRag:
    """Double de test : aucune sortie ci-dessous n'est une réponse d'un vrai LLM."""
    def __init__(self):self.allowed=[];self.analyses=[]
    def retrieve(self,question,allowed):
        self.allowed=allowed
        if 'absente' in question or not allowed:return []
        return [{'document_id':allowed[0],'page':5,'text':'Les réseaux neuronaux apprennent des représentations.'}]
    def generate(self,question,passages):return 'Réponse de test fondée sur le passage.'
    def analyze(self,task,identifiers):
        self.analyses.append(identifiers)
        return 'Synthèse de test.',[{'document_id':i,'page':1,'text':'Passage'} for i in identifiers]
    def index(self,identifier,path):return 6

class LibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password=hash_password('password-for-tests')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.settings=Settings(data_dir=Path(self.temp.name), db_backend='sqlite')
        self.rag=FakeRag();self.library=Library(self.settings,self.rag)
        self.users=[]
        with self.library.db.transaction() as tx:
            for name,role in [('admin','admin'),('student','student'),('other','student'),('librarian','librarian')]:
                account_id=tx.insert('users',email=name+'@test.local',name=name,password_hash=self.password,role=role,active=1,created_at=now())
                self.users.append({'id':account_id,'name':name,'email':name+'@test.local','role':role,'active':1})
        self.admin,self.student,self.other,self.staff=self.users
        self.book=self.library.add_book(self.admin,{'title':'Deep learning','author':'Université','category':'IA'})
        self.copy=self.library.add_copy(self.admin,self.book['id'],{'code':'COPY-1'})

    def tearDown(self):self.temp.cleanup()

    def fails(self,status,func,*args):
        with self.assertRaises(Problem) as ctx:func(*args)
        self.assertEqual(ctx.exception.status,status)

    def document(self,visibility='public',owner=None,status='ready'):
        with self.library.db.transaction() as tx:
            return tx.insert('documents',title='Introduction au deep learning',owner_id=(owner or self.admin)['id'],visibility=visibility,filename='test.pdf',status=status,page_count=6,error=None,created_at=now())

    def token(self,user):
        token='test-token-'+str(user['id'])
        with self.library.db.transaction() as tx:tx.insert('sessions',user_id=user['id'],token_hash=token_hash(token),expires_at=expiry(1))
        return token

    def test_registration_cannot_grant_admin(self):
        u=self.library.register({'email':'new@test.local','name':'New','password':'safe-password-123','role':'admin'})
        self.assertEqual(u['role'],'student');self.assertNotIn('password_hash',u)
        self.fails(409,self.library.register,{'email':'new@test.local','name':'New','password':'safe-password-123'})

    def test_login_logout_and_revocation(self):
        result=self.library.login({'email':self.student['email'],'password':'password-for-tests'})
        token=result['access_token'];self.assertEqual(self.library.authenticate(token)['id'],self.student['id'])
        self.library.logout(token);self.fails(401,self.library.authenticate,token)
        token=self.token(self.other)
        self.library.edit_user(self.admin,self.other['id'],{'active':False})
        self.fails(401,self.library.authenticate,token)

    def test_invalid_auth_and_permissions(self):
        self.fails(401,self.library.authenticate,'invalid')
        self.fails(401,self.library.login,{'email':self.student['email'],'password':'wrong-password'})
        self.fails(403,self.library.add_book,self.student,{'title':'X','author':'A','category':'IA'})
        self.fails(403,self.library.stats,self.staff)
        self.fails(409,self.library.edit_user,self.admin,self.admin['id'],{'role':'student'})

    def test_catalog_and_copy_validation(self):
        self.assertEqual(len(self.library.books(self.student,'deep')),1)
        self.assertEqual(self.library.books(self.student,"' OR 1=1 --"),[])
        self.fails(409,self.library.add_copy,self.staff,self.book['id'],{'code':'COPY-1'})
        self.fails(422,self.library.loan,self.staff,{'copy_id':True,'student_id':2})
        edited=self.library.edit_book(self.staff,self.book['id'],{'title':'Nouveau titre'})
        self.assertEqual(edited['title'],'Nouveau titre')

    def test_unavailable_copy_and_history(self):
        loan=self.library.loan(self.staff,{'copy_id':self.copy['id'],'student_id':self.student['id']})
        self.fails(409,self.library.loan,self.staff,{'copy_id':self.copy['id'],'student_id':self.other['id']})
        self.assertEqual(self.library.books(self.student)[0]['available_copies'],0)
        self.assertEqual(len(self.library.loans(self.student)),1)
        self.assertEqual(self.library.loans(self.other),[])
        self.fails(409,self.library.delete_book,self.staff,self.book['id'])
        self.library.return_loan(self.staff,loan['id'])
        self.fails(409,self.library.return_loan,self.staff,loan['id'])
        self.assertEqual(self.library.books(self.student)[0]['available_copies'],1)

    def test_reservation_return_notification_priority(self):
        loan=self.library.loan(self.staff,{'copy_id':self.copy['id'],'student_id':self.student['id']})
        self.library.reserve(self.other,{'book_id':self.book['id']})
        self.library.return_loan(self.staff,loan['id'])
        self.assertEqual(len(self.library.notifications(self.other)),1)
        self.assertEqual(self.library.notifications(self.student),[])
        self.fails(409,self.library.loan,self.staff,{'copy_id':self.copy['id'],'student_id':self.student['id']})
        self.library.loan(self.staff,{'copy_id':self.copy['id'],'student_id':self.other['id']})
        self.assertEqual(self.library.reservations(self.other)[0]['status'],'fulfilled')

    def test_reservation_ownership_and_duplicate(self):
        self.fails(403,self.library.reserve,self.admin,{'book_id':self.book['id']})
        r=self.library.reserve(self.student,{'book_id':self.book['id']})
        self.fails(409,self.library.reserve,self.student,{'book_id':self.book['id']})
        self.fails(403,self.library.cancel_reservation,self.other,r['id'])
        self.library.cancel_reservation(self.student,r['id'])
        self.assertEqual(self.library.reservations(self.student)[0]['status'],'cancelled')

    def test_parallel_loans_only_one_succeeds(self):
        def borrow(u):
            try:self.library.loan(self.staff,{'copy_id':self.copy['id'],'student_id':u['id']});return 201
            except Problem as exc:return exc.status
        with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(borrow,[self.student,self.other]))
        self.assertEqual(sorted(statuses),[201,409])

    def test_question_with_sources_and_isolated_history(self):
        did=self.document()
        result=self.library.question(self.student,{'question':'Quels réseaux neuronaux ?','document_id':did,'user_id':self.other['id']})
        self.assertEqual(result['sources'][0]['document_id'],did);self.assertEqual(result['sources'][0]['page'],5)
        self.assertEqual(len(self.library.history(self.student)),1);self.assertEqual(self.library.history(self.other),[])

    def test_absent_answer_no_invented_source(self):
        self.document()
        result=self.library.question(self.student,{'question':'Information absente'})
        self.assertIn('ne permettent pas',result['answer']);self.assertEqual(result['sources'],[])

    def test_document_access_before_vector_retrieval(self):
        public=self.document();private=self.document('private',self.other)
        self.fails(403,self.library.question,self.student,{'question':'Secrets','document_id':private})
        self.library.question(self.student,{'question':'Question'})
        self.assertEqual(self.rag.allowed,[public]);self.assertNotIn(private,self.rag.allowed)
        self.fails(403,self.library.analyze,self.student,'comparison',{'document_ids':[public,private]})
        self.assertEqual(self.rag.analyses,[])

    def test_summary_comparison_and_not_indexed(self):
        a,b=self.document(),self.document()
        for kind in ['summary','concepts']:
            self.assertTrue(self.library.analyze(self.student,kind,{'document_id':a})['sources'])
        self.assertEqual(len(self.library.analyze(self.student,'comparison',{'document_ids':[a,b]})['sources']),2)
        failed=self.document(status='failed')
        self.fails(409,self.library.question,self.student,{'question':'Question','document_id':failed})
        self.fails(422,self.library.analyze,self.student,'comparison',{'document_ids':[a,a]})

    def test_failed_index_has_consistent_status(self):
        self.fails(422,self.library.upload,self.admin,'Bad','public',b'not a pdf')
        class Broken(FakeRag):
            def index(self,*args):raise AIUnavailable('Modèle indisponible')
        self.library.rag=Broken()
        self.fails(503,self.library.upload,self.admin,'PDF','public',b'%PDF-test-fixture')
        docs=self.library.documents(self.admin)
        self.assertEqual(docs[0]['status'],'failed');self.assertIsNotNone(docs[0]['error'])
        self.library.rag=FakeRag();self.library.index_document(self.admin,docs[0]['id'])
        self.assertEqual(self.library.documents(self.admin)[0]['status'],'ready')

    def test_favorites_and_collections_owner(self):
        f=self.library.add_favorite(self.student,{'book_id':self.book['id']})
        self.assertEqual(len(self.library.favorites(self.student)),1);self.assertEqual(self.library.favorites(self.other),[])
        self.fails(403,self.library.delete_favorite,self.other,f['id'])
        c=self.library.add_collection(self.student,{'name':'IA'})
        self.fails(403,self.library.collection_item,self.other,c['id'],{'book_id':self.book['id']})
        self.library.collection_item(self.student,c['id'],{'book_id':self.book['id']})
        self.assertEqual(len(self.library.collections(self.student)[0]['items']),1)
        self.assertEqual(self.library.collections(self.other),[])
        reopened=Library(self.settings,self.rag)
        self.assertEqual(len(reopened.favorites(self.student)),1)
        self.assertEqual(len(reopened.collections(self.student)[0]['items']),1)

    def test_feedback_and_statistics(self):
        did=self.document();a=self.library.question(self.student,{'question':'Test','document_id':did})
        self.fails(403,self.library.feedback,self.other,{'interaction_id':a['interaction_id'],'rating':5})
        self.library.feedback(self.student,{'interaction_id':a['interaction_id'],'rating':4})
        self.fails(409,self.library.feedback,self.student,{'interaction_id':a['interaction_id'],'rating':3})
        self.assertEqual(self.library.stats(self.admin)['feedback']['avg_rating'],4)

    def test_reminders_are_idempotent(self):
        loan=self.library.loan(self.staff,{'copy_id':self.copy['id'],'student_id':self.student['id']})
        with self.library.db.transaction() as tx:tx.execute('UPDATE loans SET due_at=:past WHERE id=:id',{'past':'2000-01-01T00:00:00+00:00','id':loan['id']}).close()
        self.assertEqual(self.library.reminders(self.staff)['created'],1)
        self.assertEqual(self.library.reminders(self.staff)['created'],0)

    def test_router_contract(self):
        router=Router(self.library)
        self.fails(401,router.dispatch,'GET','/api/books')
        token=self.token(self.student)
        status,books=router.dispatch('GET','/api/books',token)
        self.assertEqual(status,200);self.assertEqual(len(books),1)
        self.fails(403,router.dispatch,'POST','/api/books',token,{'title':'X','author':'A','category':'IA'})
        self.fails(422,router.dispatch,'POST','/api/questions',token,[])

    def test_chunk_pages_overlap_and_prompt_policy(self):
        output=list(chunks([(1,'abcdefghij'),(2,'klmnopqrst')],6,2))
        self.assertEqual([p['page'] for p in output],[1,1,2,2])
        self.assertEqual(output[0]['text'][-2:],output[1]['text'][:2])
        self.assertIn('DONNÉES NON FIABLES',SYSTEM)
        # This verifies the policy and server-side ACL, not model resistance to attack.

class HttpTests(unittest.TestCase):
    def test_real_http_health_and_authentication(self):
        with tempfile.TemporaryDirectory() as folder:
            try:
                server=make_server(Settings(data_dir=Path(folder), db_backend='sqlite'),0)
            except PermissionError:
                self.skipTest('Les sockets locaux sont interdits dans cet environnement')
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            url=f'http://127.0.0.1:{server.server_port}'
            try:
                with urllib.request.urlopen(url+'/api/health') as response:self.assertEqual(json.load(response)['status'],'ok')
                with self.assertRaises(urllib.error.HTTPError) as ctx:urllib.request.urlopen(url+'/api/books')
                self.assertEqual(ctx.exception.code,401)
                data={'email':'student@test.local','name':'Student','password':'student-password-123'}
                req=urllib.request.Request(url+'/api/auth/register',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req) as response:self.assertEqual(response.status,201)
                req=urllib.request.Request(url+'/api/auth/login',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req) as response:token=json.load(response)['access_token']
                req=urllib.request.Request(url+'/api/me',headers={'Authorization':'Bearer '+token})
                with urllib.request.urlopen(req) as response:self.assertEqual(json.load(response)['role'],'student')
            except urllib.error.URLError as exc:
                if isinstance(exc.reason,PermissionError):
                    self.skipTest('Les connexions locales sont interdites dans cet environnement')
                raise
            finally:server.shutdown();server.server_close();thread.join(timeout=5)

if __name__=='__main__':unittest.main()

