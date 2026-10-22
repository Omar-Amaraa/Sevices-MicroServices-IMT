# UE-AD-A1-REST

## Lancer l'application

Prérequis : Docker Desktop installé et démarré.

Depuis la racine du projet, lancez les services avec :

```bash
docker compose up --build
```

Les API sont alors disponibles sur :

- Movie : http://localhost:3200
- Booking : http://localhost:3201
- Schedule : http://localhost:3202
- User : http://localhost:3203
- Mongo Express : http://localhost:8081

Pour arrêter les services, utilisez `Ctrl+C`, puis exécutez :

```bash
docker compose down
```

## Scénario de test avec Insomnia

Les exemples utilisent les ports publiés sur `localhost`. Dans Insomnia, choisissez **Body > GraphQL** pour les requêtes GraphQL et collez directement la requête ci-dessous, sans l'envelopper dans un objet JSON. Les valeurs entre guillemets comme `USER_ID` sont à remplacer par les valeurs reçues dans vos réponses.

### 1. Créer un utilisateur et obtenir un jeton

Créer un compte :

```http
POST http://localhost:3203/signup
Content-Type: application/json
```

```json
{
	"name": "Alex User",
	"email": "alex@example.com",
	"password": "password123"
}
```

Conservez le champ `user.id` de la réponse. Connectez-vous ensuite :

```http
POST http://localhost:3203/login
Content-Type: application/json
```

```json
{
	"email": "alex@example.com",
	"password": "password123"
}
```

Copiez `access_token`. Pour les requêtes Booking, configurez **Auth > Bearer Token** avec ce jeton. Le champ `_id` doit être l'identifiant du compte connecté.

### 2. Vérifier le planning

Requête Insomnia **GET** :

```http
http://localhost:3202/schedules/20151201
```

La réponse contient les identifiants des films prévus à cette date. Choisissez un identifiant dans la liste `movies` pour les requêtes suivantes.

### 3. Look up a movie

Requête **GraphQL** vers `http://localhost:3200/graphql` :

```graphql
{
	movie_with_id(_id: "267eedb8-0f5d-42d5-8f43-72426b9fb3e6") {
		id
		title
		director
		rating
	}
}
```

Cet exemple recherche *Creed*. Remplacez l'identifiant par un film renvoyé par le planning si nécessaire.

### 4. Look up movie actors

Requête **GraphQL** vers `http://localhost:3200/graphql` :

```graphql
{
	movie_with_id(_id: "a8034f44-aee4-44cf-b32c-74cf452aaaae") {
		id
		title
		actors {
			id
			firstname
			lastname
			birthyear
		}
	}
}
```

Cet exemple recherche les acteurs associés à *The Martian*.

### 5. Book the movie

Requête **GraphQL** vers `http://localhost:3201/graphql`, avec le jeton de l'utilisateur en Bearer Token :

```graphql
mutation {
	add_booking(
		_id: "USER_ID"
		date: "20151201"
		movieid: "267eedb8-0f5d-42d5-8f43-72426b9fb3e6"
	) {
		userid
		dates {
			date
			movies
		}
	}
}
```

Remplacez `USER_ID` par `user.id` obtenu à l'étape 1. Booking vérifie le planning auprès de Schedule en REST avant d'enregistrer la réservation dans MongoDB.

### 6. See bookings

Pour consulter la réservation avec les titres des films, envoyez cette requête **GraphQL** à `http://localhost:3201/graphql`, avec le même jeton :

```graphql
{
	get_detailed_user_bookings(_id: "USER_ID") {
		userid
		dates {
			date
			movies
		}
	}
}
```

Booking récupère les titres auprès de Movie en GraphQL.

### 7. Vérifier les accès user et admin

Requête **GET** `http://localhost:3203/me` avec le jeton utilisateur : elle renvoie son profil.

Requête **GET** `http://localhost:3203/users` avec un jeton admin : elle renvoie la liste des utilisateurs. Un jeton utilisateur standard doit recevoir `403`.

Pour préparer un compte admin local, connectez-vous à MongoDB puis donnez le rôle `admin` à un compte de confiance :

```bash
docker compose exec mongo mongosh -u root -p example --authenticationDatabase admin
```

Dans `mongosh` :

```javascript
db.getSiblingDB("user_service").users.updateOne(
	{ email: "admin@example.com" },
	{ $set: { role: "admin" } }
)
```

Reconnectez ce compte pour obtenir un jeton contenant le rôle admin. Les identifiants Mongo ci-dessus sont réservés au développement local.

### 8. Nettoyer la réservation de test

Requête **GraphQL** vers `http://localhost:3201/graphql`, avec le jeton du propriétaire :

```graphql
mutation {
	del_booking(
		_id: "USER_ID"
		date: "20151201"
		movieid: "267eedb8-0f5d-42d5-8f43-72426b9fb3e6"
	) {
		userid
		dates {
			date
			movies
		}
	}
}
```

Dans Insomnia, vérifiez aussi le champ `errors` de la réponse GraphQL : une erreur GraphQL peut être renvoyée avec un statut HTTP `200`.
