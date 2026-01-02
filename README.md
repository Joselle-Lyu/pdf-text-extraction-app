# PDF Text Extraction App
A containerized web app that extracts text from PDFs using an async worker-based architecture.

This project allows users to sign in with GitHub, upload a PDF, choose an extraction engine, 
and view the extracted text in a web dashboard.

It was built to demonstrate end-to-end system design, including async job processing 
and containerized services.

## Features

- GitHub OAuth authentication
- PDF upload with validation
- Multiple extraction engines (markitdown implemented)
- Asynchronous job processing with Redis
- Job status tracking and result display
- Fully containerized with Docker Compose

> Note: Only the `markitdown` (pypdf-based) extraction path is fully implemented.
> OCR-based engines are included as placeholders to demonstrate async job handling
> and engine selection within the given take-home scope.

## Architecture

The system is composed of four services:

- **Frontend**: React UI for authentication, uploads, and job tracking
- **Backend**: FastAPI service that handles auth, uploads, and job creation
- **Worker**: A separate service that consumes jobs from Redis and performs extraction
- **Redis**: Used as a job queue and lightweight state store

The backend never performs extraction directly. 
All extraction work is handled asynchronously by the worker.

## Data Flow

1. User signs in via GitHub OAuth
2. User uploads a PDF
3. Backend stores the file and metadata
4. A job is created and pushed to Redis
5. Worker consumes the job and reads the shared file
6. Extracted text is written back to Redis
7. Frontend polls and displays the result

## Running Locally

### Prerequisites
- Docker
- Docker Compose

### Setup

Create a `.env` file in the project root:

```env
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
GITHUB_REDIRECT_URI=http://localhost:8000/auth/github/callback
FRONTEND_URL=http://localhost:5173
JWT_SECRET=...
