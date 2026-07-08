# ☁️ Cloud AI Monitor: Architecture Benchmark

<div align="center">
  <img src="frontend/public/cireslogo.png" alt="CIRES Technologies Logo" width="50" />

  **Towards an AI-Augmented Cloud Monitoring Overview Platform**
  
  [![Internship](https://img.shields.io/badge/Project-Internship_Study-blue.svg)]()
  [![Company](https://img.shields.io/badge/Company-CIRES_Technologies-red.svg)]()
  [![Date](https://img.shields.io/badge/Date-July_2026-success.svg)]()
</div>

---

## 📌 Project Overview

**Cloud AI Monitor** is a technical study and benchmarking project conducted at **CIRES Technologies**. The project evaluates various Cloud Monitoring pipeline architectures and proposes a target architecture augmented by an Artificial Intelligence agent. 

The goal of this platform is to unify metrics, logs, and traces into a cohesive monitoring ecosystem, leveraging an AI-driven decision engine to automate anomaly detection and provide actionable remediation strategies.

---

## 🧠 AI Agent Processing Pipeline

The core of the platform relies on a unified pipeline where the engine evaluates incoming data through three main stages:

1. **Ingestion Layer** 📥
   Aggregates simulated infrastructure metrics (CPU/RAM utilization), log events (categorized as `INFO`, `WARN`, `CRITICAL`), and distributed tracing spans.
   
2. **Reasoning Model** ⚙️
   Processes the ingested data to calculate an anomaly vector:
   <p align="center">
     $\vec{A} = [m, l, t]$
   </p>
   Where $m$, $l$, and $t$ represent the state of metrics, logs, and traces, respectively.

3. **Decision Engine** 🎯
   Continuously monitors the system's *Health Score*. If the score drops below a pre-defined threshold, the decision engine compares the anomaly vector ($\vec{A}$) against an internal knowledge base to generate and propose actionable remediation steps.

---

## 📂 Report Structure

The technical report is structured to guide the reader from the initial context to the final proposed architecture and agent functionalities:

| Chapter | Description |
| :--- | :--- |
| **01. Context** | Introduction to the problem space, CIRES Technologies' operational needs, and the scope of the project. |
| **02. Architectures** | Exploration of existing cloud monitoring pipeline architectures. |
| **03. Comparative Analysis** | A detailed benchmark and comparative study of the explored architectures. |
| **04. Target Architecture** | Presentation of the proposed, optimized architecture for the Cloud AI Monitor. |
| **05. Tasks & Features** | Breakdown of the functionalities and operational tasks required for the platform. |
| **06. Conclusion** | Summary of findings and future perspectives. |
| **07. Appendix: Agents** | Deep dive into the AI agents' mechanics, modeling, and specific use cases. |

---

## 👥 Authors & Acknowledgments

This technical study and the resulting architecture were developed as an internship project under the supervision of **Mr. Ibrahim El Hannaoui**.

* **Redouane Meriche** – Software & Embedded Systems Engineering Student, INPT
* **Farouk Toujgani** – Engineering Student, EMSI

**Company:** CIRES Technologies  
**Date:** July 2026