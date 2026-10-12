"""Interface Streamlit ; tous les accès aux données passent par l'API."""
import os
import sys
from pathlib import Path
import requests
import streamlit as st

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import load_env
from frontend.design import theme, hero, resource, navigate
load_env()

API=os.getenv('API_URL','http://127.0.0.1:8000').rstrip('/')
st.set_page_config(page_title='Bibliothèque intelligente',page_icon='📚',layout='wide')
theme()
st.caption('BIBLIOTHÈQUE UNIVERSITAIRE  /  ADNANE EDRISSI')

def call(method,path,data=None,params=None,files=None,form=None):
    headers={'Authorization':'Bearer '+st.session_state.get('token','')}
    try:
        response=requests.request(method,API+path,headers=headers,json=data,params=params,files=files,data=form,timeout=240)
        if response.status_code==401 and st.session_state.get('token'):
            st.session_state.pop('token',None);st.session_state.pop('user',None)
            st.error('Session expirée. Reconnectez-vous.');st.stop()
        if not response.ok:
            try:detail=response.json().get('detail',response.text)
            except ValueError:detail=response.text
            st.error(f'{response.status_code} · {detail}');return None
        return response.json()
    except requests.RequestException:
        st.error('API inaccessible. Démarrer le backend sur le port 8000.');return None

def table(rows):
    if rows:st.dataframe(rows,use_container_width=True,hide_index=True)
    else:st.info('Aucun élément pour le moment.')

def result(answer):
    if answer:
        st.markdown(answer['answer'])
        st.caption(f"Temps de traitement : {answer['processing_time_ms']} ms")
        st.markdown('**Sources documentaires retrouvées**')
        table(answer['sources'])
        st.session_state['last_interaction']=answer['interaction_id']

if 'token' not in st.session_state:
    hero('Apprendre. Explorer. Comprendre.','Retrouvez vos ressources, organisez vos lectures et interrogez les documents avec un assistant qui indique ses sources.')
    login,register=st.tabs(['Connexion','Créer un compte étudiant'])
    with login:
        with st.form('login'):
            email=st.text_input('Email');password=st.text_input('Mot de passe',type='password')
            if st.form_submit_button('Se connecter',type='primary'):
                value=call('POST','/api/auth/login',{'email':email,'password':password})
                if value:st.session_state.update(token=value['access_token'],user=value['user']);st.rerun()
    with register:
        with st.form('register'):
            name=st.text_input('Nom complet');email=st.text_input('Email étudiant');password=st.text_input('Mot de passe — 10 caractères minimum',type='password')
            if st.form_submit_button('Créer le compte'):
                if call('POST','/api/auth/register',{'name':name,'email':email,'password':password}):st.success('Compte créé. Connectez-vous.')
    st.stop()

current_user=call('GET','/api/me')
if current_user:st.session_state['user']=current_user
user=st.session_state['user'];staff=user['role'] in ('admin','librarian')
st.sidebar.write(f"**{user['name']}**");st.sidebar.caption(user['role'])
if st.sidebar.button('Se déconnecter'):
    call('POST','/api/auth/logout',{})
    st.session_state.clear();st.rerun()
pages=['Accueil','Catalogue','Documents','Assistant IA','Analyse documentaire','Espace personnel','Recommandations','Notifications']
if staff:pages+=['Gestion des emprunts','Gestion du catalogue']
if user['role']=='admin':pages+=['Administration']
if st.session_state.get('navigation','Accueil') not in pages:st.session_state['navigation']='Accueil'
page=st.sidebar.radio('Navigation',pages,key='navigation')
st.sidebar.divider()
st.sidebar.caption('Adnane Edrissi · AI & Data Science\n5ème année · 5IASDT G2 - G22')
st.title(page if page!='Accueil' else f"Bonjour, {user['name'].split()[0]}")

if page=='Accueil':
    hero('Votre prochaine découverte commence ici.','Explorez les cours, reliez les idées entre plusieurs documents et gardez les ressources utiles dans votre espace personnel.')
    books=call('GET','/api/books') or []
    docs=call('GET','/api/documents') or []
    favorites=call('GET','/api/favorites') or []
    metrics=st.columns(4)
    metrics[0].metric('Ressources au catalogue',len(books))
    metrics[1].metric('Documents prêts pour l’IA',sum(d['status']=='ready' for d in docs))
    metrics[2].metric('Domaines à explorer',len({b['category'] for b in books}))
    metrics[3].metric('Mes favoris',len(favorites))
    st.subheader('Que souhaitez-vous faire ?')
    for col,title,description,target in zip(st.columns(3),['Explorer les ressources','Poser une question','Comparer des documents'],['Cours, fiches et exemplaires disponibles.','Une réponse accompagnée de pages sources.','Résumés, notions clés et points de comparaison.'],['Catalogue','Assistant IA','Analyse documentaire']):
        with col,st.container(border=True):
            st.markdown('**'+title+'**');st.caption(description)
            st.button('Ouvrir',key='home_'+target,on_click=navigate,args=(target,),use_container_width=True)
    st.subheader('À découvrir dans la bibliothèque')
    cols=st.columns(3)
    for i,b in enumerate(books[-6:]):
        with cols[i%3],st.container(border=True):resource(b['title'],b['category'],(b['description'] or '')[:170],f"{b['available_copies']} exemplaire(s) disponible(s)")
    st.info('Les supports de démonstration sont des contenus pédagogiques originaux du projet. Les réponses IA restent à vérifier dans les pages citées.')

elif page=='Catalogue':
    st.caption('Des ressources pour vos cours, vos projets et vos prochaines recherches.')
    books=call('GET','/api/books') or []
    left,middle,right=st.columns([3,2,1])
    q=left.text_input('Rechercher',placeholder='Titre, auteur ou sujet…')
    category=middle.selectbox('Domaine',['Tous les domaines']+sorted({b['category'] for b in books}))
    available=right.checkbox('Disponibles uniquement')
    selected=[b for b in books if (not q or q.casefold() in (b['title']+' '+b['author']+' '+(b['description'] or '')).casefold()) and (category=='Tous les domaines' or b['category']==category) and (not available or b['available_copies']>0)]
    st.caption(f'{len(selected)} ressource(s) trouvée(s)')
    if not selected:st.info('Aucune ressource ne correspond à ces filtres.')
    cols=st.columns(3)
    for i,b in enumerate(selected):
        with cols[i%3],st.container(border=True):
            resource(b['title'],b['category'],(b['description'] or '')[:240],f"{b['available_copies']}/{b['total_copies']} exemplaires disponibles · Réf. {b['id']}")
            with st.expander('Détails et actions'):
                st.caption(b['author']);st.write(b['description'] or 'Description à compléter.')
                if st.button('Ajouter aux favoris',key=f"fav_{b['id']}"):
                    if call('POST','/api/favorites',{'book_id':b['id']}):st.success('Ajouté aux favoris')
                if user['role']=='student' and st.button('Réserver',key=f"reserve_{b['id']}"):
                    if call('POST','/api/reservations',{'book_id':b['id']}):st.success('Réservation enregistrée')
                if st.button('Voir les exemplaires',key=f"copies_{b['id']}"):table(call('GET',f"/api/books/{b['id']}/copies"))

elif page=='Documents':
    docs=call('GET','/api/documents') or []
    st.caption('Votre corpus documentaire : les pages indexées alimentent les réponses de l’assistant.')
    search=st.text_input('Rechercher un document',placeholder='RAG, réseaux, apprentissage…')
    visible=[d for d in docs if search.casefold() in d['title'].casefold()]
    cols=st.columns(3)
    labels={'ready':'Prêt pour l’IA','pending':'En attente','indexing':'Indexation en cours','failed':'À réindexer'}
    for i,doc in enumerate(visible):
        with cols[i%3],st.container(border=True):
            resource(doc['title'],labels.get(doc['status'],doc['status']),meta=f"{doc['page_count']} pages · {'Public' if doc['visibility']=='public' else 'Privé'}")
            if doc['error']:st.caption(doc['error'])
    if not visible:st.info('Aucun document correspondant. Le personnel peut enrichir le corpus depuis cette page.')
    if staff:
        with st.form('upload'):
            title=st.text_input('Titre du document');visibility=st.selectbox('Visibilité',['public','private'])
            pdf=st.file_uploader('PDF universitaire (20 Mo maximum)',type=['pdf'])
            if st.form_submit_button('Importer et indexer'):
                if pdf:
                    with st.spinner('Extraction et indexation…'):
                        value=call('POST','/api/documents',files={'file':(pdf.name,pdf.getvalue(),'application/pdf')},form={'title':title,'visibility':visibility})
                    if value:st.success('PDF indexé');st.rerun()
                else:st.error('Choisissez un PDF')
        failed=[doc for doc in docs if doc['status']=='failed']
        if failed:
            doc=st.selectbox('Relancer une indexation',failed,format_func=lambda d:d['title'])
            if st.button('Réindexer'):
                if call('POST',f"/api/documents/{doc['id']}/reindex",{}):st.rerun()
    if docs:
        doc=st.selectbox('Consulter le PDF',docs,format_func=lambda d:d['title'])
        if st.button('Préparer le téléchargement'):
            try:
                r=requests.get(API+f"/api/documents/{doc['id']}/file",headers={'Authorization':'Bearer '+st.session_state['token']},timeout=30)
                if r.ok:st.download_button('Télécharger le PDF',r.content,file_name=f"document-{doc['id']}.pdf",mime='application/pdf')
                else:st.error('PDF inaccessible')
            except requests.RequestException:st.error('API inaccessible')

elif page=='Assistant IA':
    docs=[d for d in (call('GET','/api/documents') or []) if d['status']=='ready']
    selection=st.selectbox('Périmètre documentaire',[None]+docs,format_func=lambda d:'Tous mes documents accessibles' if d is None else d['title'])
    st.caption('Posez une question sur les documents. Chaque demande est traitée avec le périmètre choisi et ses propres sources.')
    messages=st.session_state.setdefault('chat_messages',[])
    for message in messages:
        with st.chat_message(message['role']):
            if message['role']=='user':st.write(message['content'])
            else:result(message['content'])
    if not messages:
        st.info('Exemples : « Comment éviter le surapprentissage ? », « Quelle différence entre TCP et UDP ? », « Comment construire un pipeline RAG ? »')
    question=st.chat_input('Posez votre question à la bibliothèque…')
    if question:
        messages.append({'role':'user','content':question})
        with st.chat_message('user'):st.write(question)
        with st.spinner('Recherche et génération…'):
            value=call('POST','/api/questions',{'question':question,'document_id':selection['id'] if selection else None})
        if value:
            messages.append({'role':'assistant','content':value})
            with st.chat_message('assistant'):result(value)
    if messages and st.button('Nouvelle discussion'):
        st.session_state['chat_messages']=[];st.session_state.pop('last_interaction',None);st.rerun()
    if 'last_interaction' in st.session_state:
        with st.form('feedback'):
            rating=st.slider('Note de la réponse',1,5,3);comment=st.text_input('Observation')
            if st.form_submit_button('Évaluer'):
                if call('POST','/api/feedback',{'interaction_id':st.session_state['last_interaction'],'rating':rating,'comment':comment}):st.success('Évaluation enregistrée')

elif page=='Analyse documentaire':
    docs=[d for d in (call('GET','/api/documents') or []) if d['status']=='ready']
    if not docs:st.info('Importer et indexer au moins un document.')
    else:
        action=st.selectbox('Traitement',['Résumé','Notions clés','Comparaison'])
        if action=='Comparaison':selected=st.multiselect('2 à 5 documents',docs,format_func=lambda d:d['title'])
        else:selected=[st.selectbox('Document',docs,format_func=lambda d:d['title'])]
        if st.button('Analyser'):
            endpoint={'Résumé':'summarize','Notions clés':'key-concepts','Comparaison':'comparisons'}[action]
            payload={'document_ids':[d['id'] for d in selected]} if action=='Comparaison' else {'document_id':selected[0]['id']}
            with st.spinner('Analyse des sections…'):value=call('POST','/api/'+endpoint,payload)
            if value:st.session_state['analysis']=value
        result(st.session_state.get('analysis'))

elif page=='Espace personnel':
    favorites,collections,history,loans,reservations=st.tabs(['Favoris','Collections','Historique','Emprunts','Réservations'])
    with favorites:
        values=call('GET','/api/favorites') or [];table(values)
        if values:
            f=st.selectbox('Favori à retirer',values,format_func=lambda b:b['title'])
            if st.button('Retirer le favori'):
                if call('DELETE',f"/api/favorites/{f['favorite_id']}"):st.rerun()
    with collections:
        with st.form('collection'):
            name=st.text_input('Nom de la collection')
            if st.form_submit_button('Créer'):
                if call('POST','/api/collections',{'name':name}):st.rerun()
        values=call('GET','/api/collections') or []
        for value in values:
            with st.expander(value['name']):table(value['items'])
        if values:
            col=st.selectbox('Collection cible',values,format_func=lambda c:c['name'])
            book=st.number_input('ID du livre à ajouter',min_value=1,step=1)
            if st.button('Ajouter à la collection'):
                if call('POST',f"/api/collections/{col['id']}/items",{'book_id':int(book)}):st.rerun()
    with history:
        for h in call('GET','/api/history') or []:
            with st.expander(f"{h['created_at'][:19]} · {h['kind']} · {h['question'][:70]}"):
                st.write(h['answer']);table(h['sources'])
    with loans:table(call('GET','/api/loans'))
    with reservations:
        values=call('GET','/api/reservations') or [];table(values)
        active=[r for r in values if r['status']=='active']
        if active:
            r=st.selectbox('Réservation à annuler',active,format_func=lambda r:r['title'])
            if st.button('Annuler'):
                if call('DELETE',f"/api/reservations/{r['id']}"):st.rerun()

elif page=='Recommandations':
    interests=st.text_input('Vos centres d’intérêt')
    if st.button('Obtenir des suggestions'):
        value=call('GET','/api/recommendations',params={'interests':interests})
        if value:st.caption(value['strategy']);table(value['items'])

elif page=='Notifications':
    st.caption('Les disponibilités et rappels liés à vos emprunts apparaissent ici.')
    notifications=call('GET','/api/notifications') or []
    if not notifications:st.info('Vous êtes à jour. Aucune notification pour le moment.')
    for notification in notifications:
        with st.container(border=True):
            st.markdown('**Bibliothèque universitaire**')
            st.write(notification['message'])
            st.caption(notification['created_at'][:16].replace('T',' · '))

elif page=='Gestion des emprunts':
    table(call('GET','/api/loans'))
    st.subheader('Enregistrer un emprunt')
    students=[u for u in (call('GET','/api/admin/users') or []) if u['role']=='student' and u['active']]
    if students:
        student=st.selectbox('Étudiant',students,format_func=lambda u:f"{u['name']} · {u['email']}")
        cid=st.number_input('ID exemplaire',min_value=1,step=1)
        if st.button('Enregistrer l’emprunt'):
            if call('POST','/api/loans',{'copy_id':int(cid),'student_id':student['id']}):st.rerun()
    lid=st.number_input('ID emprunt à retourner',min_value=1,step=1)
    if st.button('Enregistrer le retour'):
        if call('PATCH',f'/api/loans/{int(lid)}/return',{}):st.rerun()
    if st.button('Créer les rappels de retard'):
        value=call('POST','/api/admin/reminders',{})
        if value:st.success(f"{value['created']} rappel(s) créé(s)")

elif page=='Gestion du catalogue':
    with st.form('book'):
        title=st.text_input('Titre');author=st.text_input('Auteur');category=st.text_input('Catégorie');description=st.text_area('Description')
        if st.form_submit_button('Ajouter un livre'):
            value=call('POST','/api/books',{'title':title,'author':author,'category':category,'description':description})
            if value:st.success(f"Livre ajouté : ID {value['id']}")
    bid=st.number_input('ID livre',min_value=1,step=1);code=st.text_input('Code unique exemplaire')
    if st.button('Ajouter un exemplaire'):
        if call('POST',f'/api/books/{int(bid)}/copies',{'code':code}):st.success('Exemplaire ajouté')
    with st.expander('Modifier ou supprimer un livre'):
        field=st.selectbox('Champ',['title','author','category','description']);value=st.text_input('Nouvelle valeur')
        if st.button('Modifier'):
            if call('PATCH',f'/api/books/{int(bid)}',{field:value}):st.success('Livre modifié')
        confirm=st.checkbox('Confirmer la suppression de ce livre')
        if st.button('Supprimer',disabled=not confirm):
            if call('DELETE',f'/api/books/{int(bid)}'):st.success('Livre supprimé')

elif page=='Administration':
    stats=call('GET','/api/admin/statistics')
    if stats:
        columns=st.columns(4)
        for col,key in zip(columns,['users','books','documents','interactions']):col.metric(key,stats[key])
        st.json(stats)
    users=call('GET','/api/admin/users') or [];table(users)
    if users:
        target=st.selectbox('Compte',users,format_func=lambda u:f"{u['name']} · {u['email']}")
        role=st.selectbox('Rôle',['student','librarian','admin'],index=['student','librarian','admin'].index(target['role']))
        active=st.checkbox('Compte actif',value=bool(target['active']))
        if st.button('Appliquer les droits'):
            if call('PATCH',f"/api/admin/users/{target['id']}",{'role':role,'active':active}):st.success('Compte mis à jour ; sessions révoquées')
