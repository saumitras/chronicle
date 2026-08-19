.PHONY: up down build logs ps alert replay smoke

# Start all services
up:
	docker compose up -d

# Stop all services
down:
	docker compose down

# Rebuild and restart all services
build:
	docker compose up -d --build

# Tail logs for a service: make logs s=gateway
logs:
	docker logs -f chronicle-$(s) 2>&1

# Status
ps:
	docker compose ps

# Generate an alert: make alert r=high
alert:
	curl -s -X POST "http://localhost:8001/alerts/generate?risk_profile=$(or $(r),random)"

# Trigger replay
replay:
	curl -s -X POST "http://localhost:8000/admin/replay" | python3 -m json.tool

# Run smoke tests against the local stack
# (needs: pip install pytest pytest-asyncio pytest-timeout httpx)
smoke:
	python3 -m pytest tests/smoke/ -v --timeout=120
