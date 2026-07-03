# How to Run This App

Follow the steps below to download this project from GitHub, set it up on your computer, and run it using Streamlit.

---

## 1. Prerequisites

Make sure you have the following installed on your PC:

- **Git** – to clone the repository
- **Python 3.9+** – to run the app
- **Node.js (only if the project uses a frontend/JS build step)**

### Install Python (if not installed)
Download and install from the official website:
```
https://www.python.org/downloads/
```
Verify installation:
```bash
python --version
```

### Install Node.js (only if required by this project)
Download and install from:
```
https://nodejs.org/
```
Verify installation:
```bash
node -v
npm -v
```

### Install Git (if not installed)
```
https://git-scm.com/downloads
```
Verify installation:
```bash
git --version
```

---

## 2. Download (Clone) the Project from GitHub

```bash
git clone https://github.com/your-username/your-repo-name.git
```

Move into the project folder:
```bash
cd your-repo-name
```

---

## 3. Open the Project in Your IDE

Example (VS Code):
```bash
code .
```

---

## 4. Create a Virtual Environment (if needed)

Check if a `venv` folder already exists in the project. If not, create one:

```bash
python -m venv venv
```

---

## 5. Activate the Virtual Environment

**Windows (Command Prompt):**
```bash
venv\Scripts\activate
```

**Windows (PowerShell):**
```bash
venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

---

## 6. Install Requirements

```bash
pip install -r requirements.txt
```

---

## 7. Run the App with Streamlit

```bash
streamlit run app.py
```

> Replace `app.py` with the actual entry-point filename of the project if different.

---

## 8. Stopping the App

Press `CTRL + C` in the terminal to stop the running Streamlit server.

---

## 9. Deactivating the Virtual Environment (when done)

```bash
deactivate
```
