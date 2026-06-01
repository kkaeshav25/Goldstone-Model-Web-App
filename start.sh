#!/bin/sh
echo "PWD: $(pwd)"
echo '--- /app listing ---'
ls -la /app || true
echo '--- ENV PYTHONPATH ---'
echo "$PYTHONPATH"
echo '--- python sys.path and /app contents ---'
python -c "import sys,os; print('EXE:', sys.executable); print('SYSPATH:', sys.path); print('LS_APP:', os.listdir('/app'))" || true
python - <<'PY'
import importlib,traceback,sys
try:
    importlib.import_module('api')
    print('API_IMPORT_OK')
except Exception:
    traceback.print_exc()
    sys.exit(1)
PY
exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
