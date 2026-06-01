# 🚀 Goldstone Model Web App — Deployment Guide

## Quick Start (Railway)

Railway is the fastest way to deploy your full-stack app: free tier, GitHub integration, automatic deployments.

### Prerequisites
- GitHub account (already done ✓)
- Railway account (free at railway.app)

---

## Option 1: Railway (Recommended) ⭐

### Step 1: Prepare Your Repository

1. **Create `.env.production` for frontend** (so Vite knows the backend URL):
   ```bash
   # frontend/.env.production (or in project root)
   VITE_API_URL=https://YOUR_RAILWAY_API_DOMAIN/
   ```

2. **Update API CORS origin** in `API.py`:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://*.railway.app", "http://localhost:5173"],
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

3. **Commit and push to GitHub**:
   ```bash
   git add .
   git commit -m "Prepare for deployment"
   git push origin main
   ```

### Step 2: Create Dockerfile & Build Config

Create `Dockerfile` in project root:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Node.js
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# Copy everything
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Build frontend
RUN npm install && npm run build

# Expose ports
EXPOSE 8000 5173

# Start API server
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Create `requirements.txt` (if not exists):
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
requests==2.31.0
```

### Step 3: Deploy to Railway

1. Go to [railway.app](https://railway.app)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Authorize & select your `Goldstone-Model-Web-App` repo
4. Railway auto-detects and deploys
5. Once deployment is live:
   - API URL: `https://goldstone-api-prod-xxxxx.railway.app` (or assigned domain)
   - Frontend auto-builds and serves

### Step 4: Update Frontend for Production

After deployment, update `src/App.jsx` API constant:
```javascript
const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
```

Railway will automatically inject `VITE_API_URL` environment variable.

### Step 5: Configure Environment Variables

In Railway dashboard → Project Settings → Variables:
```
VITE_API_URL=https://your-railway-api.railway.app/
```

---

## Option 2: Vercel (Frontend) + Render (Backend)

If you prefer separate platforms:

### Deploy Backend to Render

1. Go to [render.com](https://render.com)
2. Click **New +** → **Web Service**
3. Connect GitHub repo
4. Configure:
   - **Name**: `goldstone-api`
   - **Runtime**: Python 3.11
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn api:app --host 0.0.0.0 --port 8000`
5. Deploy

Your backend URL: `https://goldstone-api.onrender.com`

### Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com)
2. Click **Add New** → **Project** → Connect GitHub repo
3. Configure:
   - **Framework**: Vite
   - **Root Directory**: `.` (or `./` if at root)
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. Environment Variables:
   ```
   VITE_API_URL=https://goldstone-api.onrender.com/
   ```
5. Deploy

Your frontend URL: `https://goldstone-model.vercel.app`

---

## Option 3: Docker + Any Cloud Provider

If you want maximum control:

### Build Locally
```bash
docker build -t goldstone-model .
docker run -p 8000:8000 -p 5173:5173 goldstone-model
```

### Deploy to Azure Container Instances
```bash
az login
az acr build --registry myregistry --image goldstone:latest .
az container create \
  --resource-group mygroup \
  --name goldstone \
  --image myregistry.azurecr.io/goldstone:latest \
  --ports 8000 5173 \
  --environment-variables API_URL=https://goldstone.azurecontainers.io
```

---

## Deployment Comparison

| Option | Cost | Setup Time | Best For |
|--------|------|-----------|----------|
| **Railway** | Free ($5/mo) | 5 mins | Full-stack, single platform |
| **Vercel + Render** | Free | 10 mins | Separation of concerns |
| **Docker + Cloud** | $10-50/mo | 20 mins | Production scaling |
| **GitHub Pages + Lambda** | Free | 15 mins | Minimal backend |

---

## Post-Deployment Checklist

- [ ] Test API health: `GET /health`
- [ ] Verify CORS working from frontend
- [ ] Test /present-day endpoint
- [ ] Configure custom domain (if needed)
- [ ] Set up error logging (Sentry, LogRocket)
- [ ] Monitor backend performance

---

## Troubleshooting Deployment

### "API offline" in frontend
**Problem**: Frontend can't reach backend
```
Solution 1: Check CORS origin in API.py matches deployed frontend URL
Solution 2: Verify VITE_API_URL environment variable is set
Solution 3: Check backend logs: railway logs command
```

### Slow initial load
**Problem**: Cold start on free tier
```
Solution: Normal for free tier. Use paid tier or keep-alive pings.
```

### GitHub push not triggering deploy
**Problem**: Railway not detecting changes
```
Solution: Disconnect and reconnect GitHub integration in Railway dashboard
```

---

## Environment Variables Reference

### Backend (API.py)
```
PORT=8000                    # default
VITE_API_URL=http://localhost:8000  # for frontend
```

### Frontend (Vite)
```
VITE_API_URL=https://your-backend.railway.app/
VITE_ENV=production
```

---

## Next Steps

1. **Choose platform**: Railway (easiest) or Vercel+Render (separation)
2. **Set up files**: Add Dockerfile, requirements.txt, .env files
3. **Push to GitHub**: Final commit and push
4. **Deploy**: Follow platform-specific steps above
5. **Monitor**: Check logs and performance

**Railway Recommendation**: Deploy in ~5 minutes, everything handled automatically.

---

## Cost Breakdown

| Component | Free Tier | Cost |
|-----------|-----------|------|
| Frontend (Vercel) | Unlimited builds | Free |
| Backend API (Railway) | 500 hours/month | $5-20 (as needed) |
| Database | N/A (stateless) | N/A |
| Custom Domain | — | +$1-3/year |
| **Total** | **Free** | **$0-25/month** |

---

## Maintenance & Updates

### Push updates
```bash
git commit -am "Update model data"
git push origin main
# Railway/Vercel auto-deploys within 1-2 minutes
```

### Rollback if needed
```bash
git revert HEAD
git push origin main
# Platform automatically redeploys previous version
```

### Monitor health
- Railway Dashboard: Real-time logs and metrics
- Vercel Analytics: Frontend performance
- Render Metrics: Backend CPU/memory usage

---

## Advanced: Custom Domain

Once deployed, add your custom domain:

**Railway**:
1. Project Settings → Domains
2. Add domain (CNAME to railway.app)
3. SSL auto-configured

**Vercel**:
1. Project Settings → Domains
2. Add domain and update DNS records

---

## Support Resources

- Railway Docs: https://docs.railway.app
- Vercel Docs: https://vercel.com/docs
- Render Docs: https://render.com/docs
- Docker Best Practices: https://docs.docker.com/develop/dev-best-practices/
