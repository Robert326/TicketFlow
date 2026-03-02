# TicketFlow - Sistem Distribuit de Management al Evenimentelor

**Student:** Bolfa Robert-Ion
**Grupa:** 344 C3
**Materie:** Sisteme Concurente si Distribuite (SCD)

## 1. Descriere Generala
TicketFlow este o platforma web distribuita destinata gestionarii evenimentelor si achizitionarii de bilete online. Arhitectura este bazata pe microservicii rulate intr-un cluster Docker Swarm.

Principala problema rezolvata este **concurenta ridicata** (High Concurrency). Sistemul implementeaza:
1. **Distributed Locking** folosind Redis pentru a preveni "double-booking"
2. **Procesare Asincrona** folosind RabbitMQ pentru generarea PDF-urilor

## 2. Arhitectura Tehnica
Sistemul este compus din urmatoarele servicii (definite in `docker-compose.yml`):

| # | Serviciu | Tehnologie | Rol |
|---|----------|------------|-----|
| 1 | **API Gateway** | Flask (Python) | Punct central de intrare, logica de business |
| 2 | **Identity Provider** | Keycloak | SSO, autentificare, RBAC |
| 3 | **Database** | PostgreSQL | Stocare persistenta |
| 4 | **Cache & Locking** | Redis | Rezervari temporare (10 min) |
| 5 | **Message Broker** | RabbitMQ | Coada pentru procesare asincrona |
| 6 | **PDF Workers** | Python (3 replici) | Generare PDF + trimitere email |
| 7 | **Email Service** | MailHog | SMTP mock pentru testare |
| 8 | **Dynamic Pricing Engine** | Python | Calcul preturi in timp real |

### Retele Docker (Overlay)
* `public_net`: Acces extern catre Gateway si Keycloak.
* `app_net`: Comunicare interna intre Gateway, Keycloak si RabbitMQ.
* `data_net`: Retea izolata pentru persistenta (DB, Redis, Workers).

## 3. Rulare

```bash
# Start all services
cd scd-proiect
docker-compose up --build -d

# Check services
docker-compose ps

# Scale workers
docker service scale scd-proiect_worker=5

# Stop
docker-compose down
```

## 4. Acces Servicii (Link-uri)

| Serviciu | URL | User / Parola (Default) |
|----------|-----|-------------------------|
| **Web App (TicketFlow)** | [http://localhost:8001](http://localhost:8001) | `user1` / `1234` |
| **Keycloak Admin** | [http://localhost:8080](http://localhost:8080) | `admin` / `admin` |
| **RabbitMQ Dashboard** | [http://localhost:15672](http://localhost:15672) | `guest` / `guest` |
| **MailHog (Email)** | [http://localhost:8025](http://localhost:8025) | _(Fara autentificare)_ |

## 5. Endpoints

| Endpoint | Method | Descriere |
|----------|--------|-----------|
| `/` | GET | Frontend |
| `/login` | POST | Autentificare Keycloak |
| `/events` | GET | Lista evenimente |
| `/events` | POST | Creare eveniment (Admin) |
| `/reserve` | POST | Rezervare loc (Redis lock) |
| `/buy` | POST | Achizitie bilet + trimitere la coada |
| `/orders/<id>` | GET | Status comanda |

## 6. Modificare Workeri (N workeri)

```bash
docker service scale ticketflow_worker= N
```

```bash
docker service logs -f ticketflow_worker
```