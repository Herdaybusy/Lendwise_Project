# LendWise Financials Data Pipeline 📊
## 🏦 Project Overview

**LendWise Financials** is a comprehensive cloud-native data engineering solution designed to automate the extraction, transformation, and loading (ETL) of loan-related data. This project empowers financial institutions with data-driven insights for improved lending decisions and risk assessment.

### 🎯 Mission
Empowering individuals and businesses with tailored financial solutions through advanced data engineering and automated loan processing workflows.

## 🚀 Problem Statement

LendWise Financials previously lacked a streamlined, automated process for handling large volumes of loan-related data. The manual workflow resulted in:
- ⏰ Processing delays and inefficiencies
- ❌ Data inconsistencies and errors
- 📊 Limited real-time insights into loan performance
- 🔍 Inadequate risk assessment capabilities

## ✨ Solution Architecture

This project implements a **cloud-native data pipeline** that:
- ✅ Automates loan data processing in real-time
- 🧹 Maintains data quality through automated cleansing
- 📈 Provides accurate, timely loan performance insights
- 🔄 Enables scalable data transformation processes

### 🏗️ Architecture Components

1. **Data Sources** → Raw CSV files (Loan Applications, Repayments, Credit Bureau Data)
2. **Processing Engine** → Python ETL scripts with automated data cleaning
3. **Cloud Storage** → Google Cloud Storage for raw and processed data
4. **Orchestration** → Google Cloud Functions with scheduled triggers
5. **Data Warehouse** → BigQuery for analytics and reporting

## 🛠️ Technology Stack
- **Processing**: Python, Pandas, NumPy - Data transformation and cleaning
- **Cloud Platform**: Google Cloud Platform (GCP) - Infrastructure and services
- **Storage**: Google Cloud Storage - Raw and processed data storage
- **Data Warehouse**: BigQuery - Analytics and reporting
- **Orchestration**: Cloud Functions, Cloud Scheduler - Automated pipeline execution
- **Framework**: Functions Framework, Flask - HTTP-triggered cloud functions


## 📊 Data Transformation Process

### 1. **Data Extraction**
- Automated retrieval from Google Cloud Storage
- Support for multiple CSV data sources
- Error handling and data validation

### 2. **Data Cleaning & Transformation**
- **Duplicate Removal**: Eliminates redundant records
- **Missing Value Handling**: Drops incomplete records
- **Column Standardization**: Normalizes naming conventions
- **Data Type Conversion**: Ensures proper datetime and numeric formats
- **Phone Number Cleaning**: Standardizes contact information

### 3. **Dimensional Modeling**
Creates normalized table structure:

- Applicant Table - Customer demographics including SSN, name, DOB, education
- Employment Table - Employment details including type, employer, income, duration
- Contact Info Table - Address and contact data including address, phone, email
- Next of Kin Table - Emergency contacts including name, relationship, contact
- Loan Application Fact Table - Core loan data including application ID, amount, type, terms
- Loan Repayments Table - Payment tracking including payment dates, amounts, status
- Credit Bureau Table - Credit assessment including credit scores, account history

## 🚀 Getting Started

### Prerequisites
- Google Cloud Platform account
- Python 3.8+
- Required Python packages (see `requirements.txt`)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/herdaybusy/lendwise_project.git
   cd lendwise_project
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Google Cloud credentials**
   ```bash
   # Set up service account and download credentials
   export GOOGLE_APPLICATION_CREDENTIALS="****/***"
   ```

4. **Configure environment variables**
   ```bash
   cp .env
   ```

### Configuration

Create a `.env` file with the following variables:
```env
GCP_PROJECT=***
BUCKET_NAME=***
DATASET_ID=***
```

## 🔧 Deployment

### Google Cloud Function Deployment

1. **Deploy the ETL function**
   ```bash
   gcloud functions deploy lendwise-etl-function \
     --runtime python39 \
     --trigger-http \
     --allow-unauthenticated \
     --source lendwise-etl-function/
   ```

2. **Set up Cloud Scheduler** (Optional)
   ```bash
   gcloud scheduler jobs create http lendwise-etl-job \
     --schedule="0 2 * * *" \
     --uri="https://function-url" \
     --http-method=GET
   ```

### BigQuery Setup

1. **Create dataset**
   ```sql
   CREATE SCHEMA `project-id.lendwise_data`
   ```

2. **Run aggregation queries**
   ```bash
   bq query --use_legacy_sql=false < sql/lendwise-Aggregation.sql
   ```

## 📈 Usage

### Manual Trigger
Send HTTP request to the Cloud Function endpoint:
```bash
curl -X GET https://function-url
```

### Scheduled Execution
The pipeline runs automatically via Cloud Scheduler at configured intervals.

### Monitoring
- View logs in Google Cloud Console
- Monitor function execution metrics
- Check BigQuery for data availability

## 📊 Data Pipeline Flow

```
Raw CSV Data → Cloud Storage → Cloud Function (ETL) → Cleaned Data → BigQuery → Analytics
```

1. **Raw data** uploaded to Cloud Storage buckets
2. **Cloud Function** triggered (HTTP/Scheduler)
3. **ETL process** cleans and transforms data
4. **Cleaned data** stored back to Cloud Storage
5. **Processed data** loaded to BigQuery tables
6. **Analytics and reporting** available for stakeholders

## 🔍 Data Quality Features

- **Automated duplicate detection and removal**
- **Missing value handling with configurable strategies**
- **Data type validation and conversion**
- **Column name standardization**
- **Error logging and monitoring**
- **Data lineage tracking**

## 📁 Project Structure

```
lendwise-financials-data-pipeline/
├── README.md                         # Project documentation
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment variables template
├── .gitignore                        # Git ignore rules
├── lendwise-etl-function/            # Cloud Function source code
│   └── lendwise_etl.py               # ETL pipeline implementation
├── Raw_Data/                         # Sample raw data files
├── Cleaned_Data/                     # Processed data output
├── images/                           # Architecture diagrams
├── sql/                              # BigQuery schemas and queries
│   └── lendwise-Aggregation.sql      # Data aggregation queries
└── docs/                             # Additional documentation
```

## 🔒 Security & Best Practices

- **Service Account Authentication**: Secure GCP resource access
- **Environment Variables**: Sensitive data stored securely
- **IAM Permissions**: Principle of least privilege
- **Data Encryption**: At-rest and in-transit encryption
- **Error Handling**: Comprehensive exception management
- **Logging**: Detailed execution logs for monitoring



## 📞 Support

For questions, issues, or contributions:
- 📧 **Email**: Herdaybusy@gmail.com.com


## 🙏 Acknowledgments

- **Google Cloud Platform** for robust cloud infrastructure
- **Python Data Science Community** for excellent libraries
- **LendWise Financials** for the inspiring use case

---
