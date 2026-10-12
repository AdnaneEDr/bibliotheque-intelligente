"""Ajoute un corpus original de démonstration et ses notices, sans faux historique."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import Settings, ROOT
from backend.service import Library, public_user, Problem
from backend.security import now

def pdf_bytes(title, pages):
    import pymupdf as fitz
    pdf=fitz.open()
    for index,content in enumerate(pages,1):
        page=pdf.new_page(width=595,height=842)
        page.insert_text((40,45),title,fontsize=15,fontname='helv')
        note='Support original de demonstration - projet Adnane Edrissi'
        page.insert_text((40,65),note,fontsize=9,fontname='helv')
        remaining=page.insert_textbox(fitz.Rect(40,95,555,780),content,fontsize=12,fontname='helv',lineheight=1.3)
        if remaining<0:raise ValueError('Contenu trop long pour la page PDF : '+title)
        page.insert_text((280,812),str(index),fontsize=10)
    result=pdf.tobytes();pdf.close();return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--index',action='store_true',help='Indexer les PDF avec le modèle réel et Chroma')
    args=parser.parse_args()
    library=Library(Settings())
    corpus=json.loads((ROOT/'demo/corpus.json').read_text(encoding='utf-8'))
    with library.db.transaction() as tx:
        admin=tx.one("SELECT * FROM users WHERE role='admin' AND active=1 ORDER BY id")
    if not admin:raise SystemExit('Créer d’abord un administrateur avec scripts/bootstrap.py --generate-password')
    user=public_user(admin)
    folder=library.settings.data_dir/'pdf';folder.mkdir(parents=True,exist_ok=True)
    for item in corpus:
        # Build the valid PDF before any insert, so unavailable PyMuPDF changes no record.
        payload=pdf_bytes(item['title'],item['pages'])
        with library.db.transaction() as tx:
            book=tx.one('SELECT * FROM books WHERE title=:title',{'title':item['title']})
            if not book:
                bid=tx.insert('books',title=item['title'],author='Supports pédagogiques du projet Adnane Edrissi',category=item['category'],description=item['pages'][0][:400]+' — Support original de démonstration.')
                for n in range(1,4):tx.insert('copies',book_id=bid,code=f'CORPUS-{bid}-{n}')
            doc=tx.one('SELECT * FROM documents WHERE title=:title AND owner_id=:account_id',{'title':item['title'],'account_id':user['id']})
            if not doc:
                import secrets
                filename=secrets.token_hex(16)+'.pdf';(folder/filename).write_bytes(payload)
                did=tx.insert('documents',title=item['title'],owner_id=user['id'],visibility='public',filename=filename,status='pending',page_count=len(item['pages']),error=None,created_at=now())
            else:did=doc['id']
        print('Support disponible :',item['title'],flush=True)
        if args.index and (not doc or doc['status']!='ready'):
            try:
                library.index_document(user,did)
                print('  Indexation réussie',flush=True)
            except Problem as exc:
                print('  Indexation à relancer :',exc.detail,flush=True)
    print(f"{len(corpus)} supports / {sum(len(item['pages']) for item in corpus)} pages, notices et exemplaires disponibles sans doublons.")
    if not args.index:print('Pour activer les questions IA : relancer avec --index.')

if __name__=='__main__':main()
