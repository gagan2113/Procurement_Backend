# Backend Procurement System

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   ```

2. Navigate to the project directory:
   ```bash
   cd Backend_Procurement
   ```

3. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```

4. Activate the virtual environment:
   - On Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```

5. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Commands

- Run the application:
  ```bash
  python backend/main.py
  ```
  uvicorn backend.main:app --reload 

- Run tests:
  ```bash
  pytest
  ```

- Format code:
  ```bash
  black .
  ```

- Lint code:
  ```bash
  flake8
  ```
