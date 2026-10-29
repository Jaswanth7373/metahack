.PHONY: demo test dev-backend dev-frontend
demo:
	scripts/demo.sh
test:
	cd backend && ../.venv/bin/python -m pytest -q
dev-backend:
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8010
dev-frontend:
	cd frontend && PAPERPILOT_API_URL=http://127.0.0.1:8010 npm run dev
