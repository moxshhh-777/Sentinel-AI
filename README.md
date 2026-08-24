# Sentinel AI

Sentinel AI is an agentic financial decision-intelligence platform designed to automate financial analysis, news monitoring, and investment decision-making. By leveraging advanced language models and agentic workflows, the platform processes real-time market data, sentiment signals, and macroeconomic  indicators. It features a modular Python FastAPI backend powered by LangGraph orchestration and a responsive, modern Next.js frontend.

## Getting Started

### Prerequisites
- [Docker](https://www.docker.com/get-started) and Docker Compose installed.
- Python 3.10+ and Node.js 18+ (for local development outside of Docker).

### Running Local Infrastructure
To spin up the Postgres database (with `pgvector` support) and Redis cache:

```bash
docker compose up -d
```
  
This starts:
- **Postgres** on `localhost:5432` (database: `sentinel`, user: `sentinel`)
- **Redis** on `localhost:6379`
