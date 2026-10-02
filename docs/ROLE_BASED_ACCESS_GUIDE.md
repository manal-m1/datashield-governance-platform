# 📋 DataShield - Role-Based Access Control (RBAC) Guide

## 📌 Complete System Documentation for User Roles & Workflows

> **Document Version:** 1.0  
> **Last Updated:** December 2024  
> **Reference:** Cahier des Charges - Projet Fédérateur 2024-2025

---

## 🏗️ Table of Contents

1. [System Overview](#1-system-overview)
2. [User Roles Hierarchy](#2-user-roles-hierarchy)
3. [Detailed Role Descriptions](#3-detailed-role-descriptions)
4. [Frontend Access Matrix](#4-frontend-access-matrix)
5. [Data Masking by Role (EthiMask)](#5-data-masking-by-role-ethimask)
6. [Workflow & Inter-Role Communication](#6-workflow--inter-role-communication)
7. [Test Users Reference](#7-test-users-reference)
8. [API Endpoints by Role](#8-api-endpoints-by-role)

---

## 1. System Overview

The DataShield platform implements a **hierarchical role-based access control system** for data governance and sensitive data protection. The system ensures:

- **GDPR & Law 09-08 (Morocco) Compliance**
- **ISO 25012 Data Quality Standards**
- **Principle of Least Privilege**
- **Contextual Data Masking based on Role**

### 🔐 Authentication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER LOGIN                                │
│                            ↓                                     │
│    ┌──────────────────────────────────────────────────────┐     │
│    │  1. User enters credentials (username/password)      │     │
│    │  2. Backend validates against MongoDB                │     │
│    │  3. JWT Token generated with role embedded           │     │
│    │  4. Token stored in localStorage                     │     │
│    │  5. Frontend filters navigation based on role        │     │
│    └──────────────────────────────────────────────────────┘     │
│                            ↓                                     │
│              USER REDIRECTED TO DASHBOARD                        │
│           (With role-specific menu visibility)                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. User Roles Hierarchy

```
                    ┌─────────────┐
                    │    ADMIN    │  ← Full System Control
                    │  (Level 4)  │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
       ┌──────┴──────┐          ┌──────┴──────┐
       │   STEWARD   │          │   ANALYST   │  ← Governance & Reports
       │  (Level 3)  │          │  (Level 3)  │
       └──────┬──────┘          └─────────────┘
              │
       ┌──────┴──────┐
       │  ANNOTATOR  │  ← Validation & Correction
       │  (Level 2)  │
       └──────┬──────┘
              │
       ┌──────┴──────┐
       │   LABELER   │  ← Basic Annotation Tasks
       │  (Level 1)  │
       └─────────────┘
```

### Role Priority (Highest to Lowest)

| Level | Role          | Trust Score | Primary Function             |
| ----- | ------------- | ----------- | ---------------------------- |
| 4     | **Admin**     | 1.0         | Full system administration   |
| 3     | **Steward**   | 0.85        | Data governance & approval   |
| 3     | **Analyst**   | 0.75        | Reports & analysis           |
| 2     | **Annotator** | 0.65        | Data validation & correction |
| 1     | **Labeler**   | 0.50        | Basic annotation tasks       |

---

## 3. Detailed Role Descriptions

### 👑 Admin (Administrateur)

**Purpose:** Full platform control and user management

| Aspect               | Details                                                                                                                                                                      |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Responsibilities** | - Manage all users (create, edit, delete)<br>- Configure EthiMask masking rules<br>- Define taxonomy categories<br>- Access all audit logs<br>- Approve system-level changes |
| **Data Access**      | 🔓 **FULL ACCESS** - All data unmasked                                                                                                                                       |
| **Can Assign Tasks** | ✅ Yes - to all roles                                                                                                                                                        |
| **Reports To**       | Nobody (Top-level)                                                                                                                                                           |
| **Typical Actions**  | Create users, configure policies, review audit logs                                                                                                                          |

**Admin-Only Features:**

- User Management (Create/Edit/Delete users)
- EthiMask Configuration (Set masking weights)
- Audit Logs Access
- System Configuration

---

### 🛡️ Steward (Data Steward)

**Purpose:** Data governance, quality control, and approval authority

| Aspect               | Details                                                                                                                                               |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Responsibilities** | - Approve/reject major corrections<br>- Define quality rules<br>- Manage taxonomy<br>- Review annotation quality<br>- Supervise annotators & labelers |
| **Data Access**      | 🔒 **PARTIAL** - Sensitive data partially masked                                                                                                      |
| **Can Assign Tasks** | ✅ Yes - to Annotators and Labelers                                                                                                                   |
| **Reports To**       | Admin                                                                                                                                                 |
| **Typical Actions**  | Review pending approvals, validate classifications, manage rules                                                                                      |

**Steward-Specific Features:**

- Taxonomy Manager
- Approval Queue
- Correction Rules Definition
- Quality Metrics Dashboard (ISO 25012)
- Classification Validation
- False Positives Review

---

### ✏️ Annotator (Data Annotator)

**Purpose:** Validate classifications and correct detected anomalies

| Aspect               | Details                                                                                                                                                   |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Responsibilities** | - Validate automatic classifications<br>- Enrich metadata<br>- Correct detected anomalies<br>- Review PII detections<br>- Submit corrections for approval |
| **Data Access**      | 🔒 **LIMITED** - Most PII masked with tokens                                                                                                              |
| **Can Assign Tasks** | ❌ No                                                                                                                                                     |
| **Reports To**       | Steward                                                                                                                                                   |
| **Typical Actions**  | Validate classifications, correct data issues, review detections                                                                                          |

**Annotator-Specific Features:**

- Data Cleaning
- Classification Validation
- False Positives Reporting
- Correction Submission
- My Statistics

---

### 🏷️ Labeler (Data Labeler)

**Purpose:** Annotate raw data and confirm/correct PII detections

| Aspect               | Details                                                                                                       |
| -------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Responsibilities** | - Annotate raw data<br>- Confirm/correct PII detections<br>- Label data sensitivity<br>- Basic quality checks |
| **Data Access**      | 🔒 **MINIMAL** - All PII replaced with tokens [NAME], [CIN], etc.                                             |
| **Can Assign Tasks** | ❌ No                                                                                                         |
| **Reports To**       | Annotator → Steward                                                                                           |
| **Typical Actions**  | Label entities, confirm detections, basic annotations                                                         |

**Labeler-Specific Features:**

- Dashboard
- Upload Data
- PII Detection
- Annotation Tasks
- My Statistics

---

## 4. Frontend Access Matrix

### Navigation Menu Visibility by Role

| Menu Item                 | Admin | Steward | Annotator | Labeler |
| ------------------------- | :---: | :-----: | :-------: | :-----: |
| **Main Section**          |
| Dashboard                 |  ✅   |   ✅    |    ✅     |   ✅    |
| Upload Data               |  ✅   |   ✅    |    ✅     |   ✅    |
| **Data Pipeline**         |
| Data Cleaning             |  ✅   |   ✅    |    ✅     |   ❌    |
| Quality Metrics (ISO)     |  ✅   |   ✅    |    ❌     |   ❌    |
| PII Detection             |  ✅   |   ✅    |    ✅     |   ✅    |
| EthiMask                  |  ✅   |   ✅    |    ❌     |   ❌    |
| **Workflow**              |
| Annotation Tasks          |  ✅   |   ✅    |    ✅     |   ✅    |
| Corrections               |  ✅   |   ✅    |    ✅     |   ❌    |
| **Administration**        |
| User Management           |  ✅   |   ❌    |    ❌     |   ❌    |
| EthiMask Config           |  ✅   |   ❌    |    ❌     |   ❌    |
| **Governance**            |
| Taxonomy Manager          |  ✅   |   ✅    |    ❌     |   ❌    |
| Approval Queue            |  ✅   |   ✅    |    ❌     |   ❌    |
| Classification Validation |  ✅   |   ✅    |    ✅     |   ❌    |
| False Positives           |  ✅   |   ✅    |    ✅     |   ❌    |
| Correction Rules          |  ✅   |   ✅    |    ❌     |   ❌    |
| My Statistics             |  ✅   |   ✅    |    ✅     |   ✅    |
| Audit Logs                |  ✅   |   ❌    |    ❌     |   ❌    |

### Frontend Role Filter Implementation

```javascript
// In index.html - Role-based navigation filtering
const userRole = localStorage.getItem("userRole") || "labeler";

// Filter nav items based on data-roles attribute
document.querySelectorAll(".nav-item[data-roles]").forEach((item) => {
  const allowedRoles = item.dataset.roles.split(",");
  if (!allowedRoles.includes(userRole)) {
    item.style.display = "none";
  }
});
```

---

## 5. Data Masking by Role (EthiMask)

### EthiMask - Contextual Masking System

EthiMask applies different masking levels based on user role and data sensitivity.

### Masking Levels

| Level | Name                 | Score Range  | Action                       |
| ----- | -------------------- | ------------ | ---------------------------- |
| 0     | Full Access          | [0.85, 1.0]  | Data completely visible      |
| 1     | Anonymization        | [0.65, 0.85) | Encrypted identifiers (HE)   |
| 2     | Generalization       | [0.45, 0.65) | Aggregated values            |
| 3     | Differential Privacy | [0.25, 0.45) | Controlled noise added       |
| 4     | Suppression          | [0, 0.25)    | Replaced with NULL or \*\*\* |

### Masking Examples by Role

| Data Field | Original Value               | Admin          | Steward                 | Annotator            | Labeler  |
| ---------- | ---------------------------- | -------------- | ----------------------- | -------------------- | -------- |
| **Name**   | Mohammed Alami               | Mohammed Alami | Mohammed A.             | M**\*\*\***          | [NAME]   |
| **CIN**    | AB123456                     | AB123456       | AB\*\*\*\*56            | [CIN]                | [CIN]    |
| **Phone**  | +212 612345678               | +212 612345678 | +212 6\***\* \*\***     | +212 6** \*** \*\*\* | [PHONE]  |
| **IBAN**   | MA64211234567891234567891234 | Full IBAN      | MA64\***\*...\*\***1234 | [IBAN_MA]            | [IBAN]   |
| **Salary** | 15,000 MAD                   | 15,000 MAD     | 10K-20K MAD             | [SALARY]             | [SALARY] |
| **CNSS**   | 123456789                    | 123456789      | 123\*\*\*789            | [CNSS]               | [CNSS]   |

### Trust Score Formula (Perceptron V0.1)

```
T'(u,p,s,h) = σ(w_r·R(u) + w_p·P(p) + w_s·S(s) + w_hc·H_c(u) + w_hf·H_f(u) + w_hv·H_v(u) + b_T)
```

Where:

- **R(u)**: User role score [0,1]
- **P(p)**: Access purpose legitimacy [0,1]
- **S(s)**: Data sensitivity [0,1]
- **H_c(u)**: Historical compliance [0,1]
- **H_f(u)**: Access frequency (normalized) [0,1]
- **H_v(u)**: Violation penalty [0,1]
- **σ**: Sigmoid function

---

## 6. Workflow & Inter-Role Communication

### 6.1 Data Processing Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE DATA PROCESSING PIPELINE                    │
│                                                                              │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐          │
│  │  Upload   │───▶│  Profile  │───▶│   Clean   │───▶│ Detect PII│          │
│  │  Dataset  │    │   Data    │    │   Data    │    │ (Presidio)│          │
│  └───────────┘    └───────────┘    └───────────┘    └─────┬─────┘          │
│                                                            │                 │
│                                                            ▼                 │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐          │
│  │  Store in │◀───│   Apply   │◀───│  Quality  │◀───│ Classify  │          │
│  │  MongoDB  │    │ EthiMask  │    │Assessment │    │Sensitivity│          │
│  └───────────┘    └───────────┘    └───────────┘    └───────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Human Validation Workflow

```
                              TASK CREATED
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │   Auto-Assign Task  │
                        │    Based on Role    │
                        └──────────┬──────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
   ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
   │   LABELER    │        │  ANNOTATOR   │        │   STEWARD    │
   │  Basic Tasks │        │  Validation  │        │   Approval   │
   └──────┬───────┘        └──────┬───────┘        └──────┬───────┘
          │                       │                       │
          │                       │                       │
          ▼                       ▼                       ▼
   ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
   │  Annotate &  │        │  Review &    │        │  Approve or  │
   │   Label      │───────▶│  Validate    │───────▶│   Reject     │
   └──────────────┘        └──────────────┘        └──────┬───────┘
                                                          │
                              ┌────────────────┬──────────┘
                              │                │
                              ▼                ▼
                        ┌──────────┐    ┌──────────────┐
                        │ APPROVED │    │   REJECTED   │
                        │ Update DB│    │ Reassign OR  │
                        └──────────┘    │   Escalate   │
                                        └──────────────┘
```

### 6.3 Role Interaction Matrix

| Action                      | Who Initiates | Who Processes | Who Approves | Who Audits |
| --------------------------- | ------------- | ------------- | ------------ | ---------- |
| **Upload Dataset**          | Any User      | System        | -            | Admin      |
| **Add Annotation**          | Labeler       | Annotator     | Steward      | Admin      |
| **Validate Classification** | System        | Annotator     | Steward      | Admin      |
| **Correct Data**            | Annotator     | Annotator     | Steward      | Admin      |
| **Approve Correction**      | Annotator     | Steward       | Steward      | Admin      |
| **Modify Taxonomy**         | Steward       | Steward       | Admin        | Admin      |
| **Create User**             | Admin         | Admin         | -            | Admin      |
| **Configure Masking**       | Admin         | Admin         | -            | Admin      |

### 6.4 Task Assignment Algorithm

```
Algorithm: Optimal Task Assignment

Input: Task T, Users U, Workload W, Skills S
Output: Assigned User

1. candidates ← FilterByRole(U, T.required_role)
2. scores ← []
3. FOR each user IN candidates:
4.     score ← 0
5.     // Workload balance (lower is better)
6.     score ← score - 0.4 × (W[user] / max(W))
7.     // Skill match
8.     skill_match ← S[user] ∩ T.required_skills
9.     score ← score + 0.3 × (|skill_match| / |T.required_skills|)
10.    // Historical performance
11.    perf ← GetPerformance(user, T.type)
12.    score ← score + 0.3 × perf
13.    scores.append({user, score})
14. best_user ← argmax(scores, key=score)
15. W[best_user] ← W[best_user] + 1
16. RETURN best_user
```

---

## 7. Test Users Reference

### Created Test Users

| Username           | Password     | Role      | Access Level |
| ------------------ | ------------ | --------- | ------------ |
| **admin**          | Admin123     | Admin     | Full Access  |
| **labeler_user**   | Labeler123   | Labeler   | Basic        |
| **annotator_user** | Annotator123 | Annotator | Intermediate |
| **steward_user**   | Steward123   | Steward   | Advanced     |

### Testing Checklist by Role

#### 🏷️ Labeler User Test

1. Login with `labeler_user / Labeler123`
2. **Expected visible menus:**
   - Dashboard ✅
   - Upload Data ✅
   - PII Detection ✅
   - Annotation Tasks ✅
   - My Statistics ✅
3. **Expected hidden menus:**
   - Data Cleaning ❌
   - Quality Metrics ❌
   - EthiMask ❌
   - All Administration ❌
   - All Governance (except My Stats) ❌

#### ✏️ Annotator User Test

1. Login with `annotator_user / Annotator123`
2. **Expected visible menus:**
   - All Labeler menus ✅
   - Data Cleaning ✅
   - Corrections ✅
   - Classification Validation ✅
   - False Positives ✅
3. **Expected hidden menus:**
   - Quality Metrics ❌
   - EthiMask ❌
   - All Administration ❌
   - Taxonomy Manager ❌
   - Approval Queue ❌
   - Correction Rules ❌

#### 🛡️ Steward User Test

1. Login with `steward_user / Steward123`
2. **Expected visible menus:**
   - All Annotator menus ✅
   - Quality Metrics (ISO) ✅
   - EthiMask ✅
   - Taxonomy Manager ✅
   - Approval Queue ✅
   - Correction Rules ✅
3. **Expected hidden menus:**
   - User Management ❌
   - EthiMask Config ❌
   - Audit Logs ❌

---

## 8. API Endpoints by Role

### Authentication Service

| Endpoint         | Method | Roles Allowed | Description       |
| ---------------- | ------ | ------------- | ----------------- |
| `/auth/login`    | POST   | Public        | User login        |
| `/auth/register` | POST   | Public        | User registration |
| `/users/`        | GET    | Admin         | List all users    |
| `/users/{id}`    | PUT    | Admin         | Update user       |
| `/users/{id}`    | DELETE | Admin         | Delete user       |

### Annotation Service

| Endpoint              | Method | Roles Allowed      | Description        |
| --------------------- | ------ | ------------------ | ------------------ |
| `/tasks`              | GET    | All                | Get task list      |
| `/tasks`              | POST   | Steward, Admin     | Create tasks       |
| `/assign`             | POST   | Steward, Admin     | Assign tasks       |
| `/tasks/{id}/submit`  | POST   | Labeler, Annotator | Submit annotations |
| `/tasks/{id}/approve` | POST   | Steward, Admin     | Approve task       |
| `/tasks/{id}/reject`  | POST   | Steward, Admin     | Reject task        |
| `/metrics`            | GET    | Steward, Admin     | View metrics       |

### Other Services

| Service      | Restricted Endpoints   | Allowed Roles             |
| ------------ | ---------------------- | ------------------------- |
| **Cleaning** | All endpoints          | Admin, Steward, Annotator |
| **Quality**  | `/evaluate`, `/report` | Admin, Steward            |
| **EthiMask** | `/mask`, `/unmask`     | Based on trust score      |
| **Taxonomy** | CRUD operations        | Admin, Steward            |

---

## 📊 Quality Metrics for Annotators

### Performance Scoring Formula

```
Quality Score = 0.5 × Accuracy + 0.3 × Kappa + 0.2 × Speed
```

| Metric                        | Formula                 | Target    |
| ----------------------------- | ----------------------- | --------- |
| **Inter-Annotator Agreement** | Concordant / Total      | > 0.85    |
| **Cohen's Kappa**             | (P_o - P_e) / (1 - P_e) | > 0.80    |
| **Throughput**                | Tasks Completed / Time  | > 20/hour |
| **Accuracy**                  | Correct / Total         | > 90%     |

---

## 📝 Summary

The DataShield RBAC system ensures:

1. **Principle of Least Privilege**: Users only access what they need
2. **Defense in Depth**: Multiple layers of access control
3. **Auditability**: All actions logged for Admin review
4. **Contextual Masking**: Data exposure based on role + context
5. **Workflow Integrity**: Clear escalation and approval paths

---

> **Contact:** For technical questions, refer to the Cahier des Charges or contact the development team.
