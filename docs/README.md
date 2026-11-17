# LifeLane Documentation Index

Welcome to the **LifeLane** project documentation folder. This directory contains detailed architectural specifications, data flows, machine learning pipeline definitions, and defense notes for presentations and evaluations.

---

### Available Documents

1. [**SYSTEM_ARCHITECTURE.md**](./SYSTEM_ARCHITECTURE.md)
   * **Executive Summary:** Plain-English explanation of what LifeLane is and why it exists.
   * **End-to-End Architecture Diagrams:** Complete Mermaid workflows showing how audio, dispatch, routing, and signal simulation interconnect.
   * **The 5 Core Pillars:**
     1. Machine Learning & Acoustic Sensing (YAMNet + Logistic Regression + XGBoost ETA).
     2. Dynamic Route Planning (Dijkstra / A* pathfinding).
     3. Three-Tier Verification & Safety State Machine (`NORMAL` $\rightarrow$ `PREPARING` $\rightarrow$ `SERVING` $\rightarrow$ `RECOVERING`).
     4. Database Architecture (SQLAlchemy async, schema models, SQLite/PostgreSQL transition).
     5. Full-Stack Integration (FastAPI REST APIs + React.js & Tailwind CSS UI).
   * **Incident Walkthrough:** Step-by-step story of an emergency run from dispatch to hospital arrival.
   * **FYP Viva & Presentation Defense Cheatsheet:** Expected questions and academic answers for evaluators.

---

### How to Run the Project Quick Reference

From the project root (`C:\Users\hp\Desktop\LifeLane\LifeLane`):

```powershell
# Automated launcher (opens backend and frontend in separate windows)
.\start-dev.ps1
```

* **Frontend Dashboard:** [http://localhost:5173](http://localhost:5173)
* **Backend API Documentation (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
