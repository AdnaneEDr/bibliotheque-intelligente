# Contrat REST

Tous les endpoints sauf health, register et login nécessitent `Authorization: Bearer <jeton>`. Les rôles et les données personnelles sont contrôlés côté serveur.

| Méthode | Endpoint | Succès |
|---|---|---|
| GET | `/api/health` | 200 |
| POST | `/api/auth/register` | 201 |
| POST | `/api/auth/login` | 200 |
| GET | `/api/me` | 200 |
| GET | `/api/books` | 200 |
| POST | `/api/books` | 201 |
| PATCH | `/api/books/{id}` | 200 |
| DELETE | `/api/books/{id}` | 200 |
| GET | `/api/books/{id}/copies` | 200 |
| POST | `/api/books/{id}/copies` | 201 |
| GET | `/api/documents` | 200 |
| GET | `/api/documents/{id}` | 200 |
| POST | `/api/documents/{id}/reindex` | 200 |
| GET | `/api/loans` | 200 |
| POST | `/api/loans` | 201 |
| PATCH | `/api/loans/{id}/return` | 200 |
| GET | `/api/reservations` | 200 |
| POST | `/api/reservations` | 201 |
| DELETE | `/api/reservations/{id}` | 200 |
| POST | `/api/questions` | 200 |
| POST | `/api/summarize` | 200 |
| POST | `/api/key-concepts` | 200 |
| POST | `/api/comparisons` | 200 |
| GET | `/api/recommendations` | 200 |
| GET | `/api/history` | 200 |
| GET | `/api/favorites` | 200 |
| POST | `/api/favorites` | 201 |
| DELETE | `/api/favorites/{id}` | 200 |
| GET | `/api/collections` | 200 |
| POST | `/api/collections` | 201 |
| POST | `/api/collections/{id}/items` | 201 |
| GET | `/api/notifications` | 200 |
| GET | `/api/admin/statistics` | 200 |
| GET | `/api/admin/users` | 200 |
| PATCH | `/api/admin/users/{id}` | 200 |
| POST | `/api/admin/reminders` | 200 |
| POST | `/api/feedback` | 201 |
| POST | `/api/auth/logout` | 200 |
| POST | `/api/documents` | 201 |
| GET | `/api/documents/{id}/file` | 200 |

## Principaux corps JSON

```json
{"name":"Adnane Edrissi","email":"adnane@example.edu","password":"mot-de-passe-personnel"}
```

Connexion : `email`, `password`.
Livre : `title`, `author`, `category`, `description` (optionnelle).
Exemplaire : `code`.
Emprunt (personnel uniquement) : `copy_id`, `student_id`. Ce dernier est la personne emprunteuse, choisie par le personnel ; il ne remplace pas l’identité authentifiée.
Réservation ou favori : `book_id`.
Collection : `name` ; ajout d’un élément : `book_id`.
Question : `question`, `document_id` (optionnel ou null).
Résumé/notions clés : `document_id`.
Comparaison : `document_ids` (liste de 2 à 5 identifiants distincts).
Évaluation : `interaction_id`, `rating` (1 à 5), `comment` (optionnel).
Modification utilisateur : `role` et/ou `active` (booléen).

Import PDF : formulaire multipart avec `title`, `visibility` (public/private) et `file`.
Recherche catalogue : query `q`, `category`. Recommandations : query `interests`.

Les erreurs contiennent `detail` ; 401 non authentifié, 403 interdit, 404 introuvable, 409 conflit, 422 entrée invalide, 503 moteur IA indisponible. FastAPI limite les tentatives d’inscription/connexion et retourne 429 en cas de dépassement.