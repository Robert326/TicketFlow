# TicketFlow - Sistem Distribuit de Management al Evenimentelor

**Student:** Bolfa Robert-Ion
**Grupa:** 344 C3
**Materie:** Sisteme Concurente si Distribuite (SCD)

## 1. Descriere Generala
TicketFlow este o platforma web distribuita destinata gestionarii evenimentelor si achizitionarii de bilete online. Arhitectura este bazata pe microservicii rulate intr-un cluster Docker Swarm.

Principala problema rezolvata este **concurenta ridicata** (High Concurrency). Sistemul implementeaza un mecanism de **Distributed Locking** folosind Redis pentru a preveni "double-booking" (vanzarea aceluiasi loc catre doua persoane simultan).

## 2. Arhitectura Tehnica
Sistemul este compus din urmatoarele servicii (definite in `docker-compose.yml`):

* **API Gateway (Flask):** Punctul central de intrare. Gestioneaza logica de business si verifica token-urile JWT.
* **Identity Provider (Keycloak):** Asigura autentificarea (SSO) si managementul rolurilor (RBAC).
* **Database (PostgreSQL):** Stocarea persistenta a evenimentelor si comenzilor.
* **Distributed Cache (Redis):** Folosit pentru mecanismul de locking temporar (rezervari de 10 minute).

### Retele Docker (Overlay)
* `public_net`: Acces extern catre Gateway si Keycloak.
* `app_net`: Comunicare interna intre Gateway si Keycloak.
* `data_net`: Retea izolata pentru persistenta (DB, Redis), inaccesibila din exterior.