To run it again later:

kill $(lsof -t -i:3000) 2>/dev/null
kill $(lsof -t -i:8000) 2>/dev/null

1. Open the Codespace (or clone the repo)
2. Run "npm install" (frontend)
3. Run "cd backend && uvicorn main:app --reload --port 8000" (backend)
4. Run "npm start" (frontend)
5. Make port 8000 Public
