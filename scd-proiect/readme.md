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

## 4. Endpoints

| Endpoint | Method | Descriere |
|----------|--------|-----------|
| `/` | GET | Frontend |
| `/login` | POST | Autentificare Keycloak |
| `/events` | GET | Lista evenimente |
| `/events` | POST | Creare eveniment (Admin) |
| `/reserve` | POST | Rezervare loc (Redis lock) |
| `/buy` | POST | Achizitie bilet + trimitere la coada |
| `/orders/<id>` | GET | Status comanda |

## 6. Diagrama Arhitectură (Milestone 3)
Pentru o vizualizare completă a rețelelor și containerelor, consultați fișierul `M3_344_Bolfa_RobertIon.pdf` din acest director. Diagrama include:
- Worker Swarm (3 noduri)
- RabbitMQ & MailHog
- Organizarea pe rețele (public_net, app_net, data_net)

## 7. Testare & Load Testing (Demo)

### 7.1. Script de Load Testing
Am implementat un script Python (`load_test.py`) care simulează **40 de utilizatori concurenți**. Scriptul rulează în containerul `api-gateway` pentru acces direct la rețeaua internă.

**Rulare (One-Liner):**
```bash
GATEWAY=$(docker ps -qf "name=ticketflow_gateway" | head -n1) && docker cp load_test.py $GATEWAY:/app/load_test.py && docker exec $GATEWAY python /app/load_test.py
```

### 7.2. Testare Manuală
1. **Frontend:** Selectează un loc si apasă "Reserve" (Locul devine `Reserved`).
2. **Buy:** Apasă "Confirm & Pay" (Locul devine `Processing` -> `Sold`).
3. **MailHog:** Verifică email-ul primit cu biletul PDF atașat (http://localhost:8025).