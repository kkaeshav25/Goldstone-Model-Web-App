# 🚀 Quick Deployment Checklist

## Pre-Deployment (5 minutes)

### ✅ Local Testing
- [ ] `npm run dev` works
- [ ] `uvicorn api:app --reload --port 8000` works
- [ ] All tabs load without errors (F12 → Console)
- [ ] /health endpoint responds: `GET http://localhost:8000/health`
- [ ] Present-Day tab loads data successfully

### ✅ Code Cleanup
- [ ] Remove console.log statements
- [ ] Check for unused imports
- [ ] Verify no hardcoded localhost URLs (except fallback)
- [ ] All API endpoints documented in DEPLOYMENT_GUIDE.md

### ✅ Git Preparation
```bash
git status  # Check what changed
git add .
git commit -m "Prepare for deployment: add Dockerfile, requirements.txt, env config"
git push origin main
```

---

## Deployment (5 minutes on Railway)

### Step 1: Create Railway Account
- Go to https://railway.app
- Sign up with GitHub
- Create new project

### Step 2: Deploy from GitHub
```
1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Authorize & select "Goldstone-Model-Web-App"
4. Railway auto-detects Docker, builds and deploys
5. Wait for green "✓ Deployment successful"
```

### Step 3: Get Your URLs
After deployment completes:
- Backend API: `https://goldstone-api-prod-xxxxx.railway.app` (shown in Deployments tab)
- Frontend: Same URL (built into Docker image)

### Step 4: Set Environment Variables (if needed)
In Railway Project → Variables:
```
VITE_API_URL=https://your-railway-backend.railway.app
```
(Usually not needed if using single deployment)

### Step 5: Test Live Deployment
```bash
curl https://your-railway-url/health
# Should return: {"status": "ok", "model": "Goldstone et al. 2010", "version": "1.0.0"}
```

---

## Post-Deployment (Verification)

### ✅ Frontend Testing
- [ ] Open deployed URL in browser
- [ ] All tabs load and are responsive
- [ ] Network tab shows API calls to correct domain
- [ ] No CORS errors in console
- [ ] Present-Day tab loads 2007/2024 data

### ✅ Backend Testing
- [ ] `/health` endpoint responds
- [ ] `/regime-types` returns regime data
- [ ] `/pipeline/countries` returns country list (62 countries)
- [ ] `/present-day` endpoint returns forecasts
- [ ] No 500 errors in logs

### ✅ Performance Check
- [ ] Page loads in < 3 seconds
- [ ] Charts render smoothly
- [ ] No memory warnings in browser

### ✅ Error Handling
- [ ] Try invalid forecast request → returns proper error
- [ ] Try offline mode → displays API offline message
- [ ] Check Railway logs for any warnings/errors

---

## Common Issues & Solutions

### "API offline" on live deployment
```
Issue: Frontend can't reach backend
Fix: Check CORS origin in API.py matches deployed URL
     Verify VITE_API_URL environment variable
     Check Railway deployment logs
```

### Slow first request (10+ seconds)
```
Normal! Free tier has "cold starts"
Fix: Keep backend awake with uptime monitor
     Or upgrade to paid Railway plan
```

### Deployment stuck/failed
```
Check: Railway deployment logs for errors
       Git repo is properly connected
       Dockerfile syntax is correct
       requirements.txt has no typos
Retry: Delete deployment and redeploy
```

### API works locally but not on Railway
```
Check: CORS configuration in API.py
       Environment variables set correctly
       Port is 8000 (Railway expects this)
       No hardcoded localhost URLs
```

---

## After Successful Deployment

### 🎉 Share Your App
- Share deployed URL: `https://your-railway-app.railway.app`
- Add to GitHub repo description
- Add to portfolio/resume

### 📊 Monitor
- Set up Railway alerts for errors
- Enable Railway metrics dashboard
- Check error logs weekly

### 🔄 Make Updates
```bash
# Make code changes locally
git commit -am "Update forecast logic"
git push origin main
# Railway auto-deploys within 1-2 minutes
```

### 🆘 Troubleshooting Dashboard
- Railway Project → Logs tab (real-time logs)
- Railway Project → Metrics tab (CPU, memory, requests)
- Browser DevTools → Network tab (API response times)

---

## Alternative: Separate Deployment (Vercel + Render)

If Railway doesn't work for you:

### Frontend on Vercel
```bash
1. Go to vercel.com
2. Import GitHub repo
3. Set VITE_API_URL = https://your-render-api.onrender.com
4. Deploy
```

### Backend on Render
```bash
1. Go to render.com
2. New Web Service from GitHub
3. Select repo
4. Set Start Command: uvicorn api:app --host 0.0.0.0 --port 8000
5. Deploy
```

**Result**: Frontend on `your-app.vercel.app`, API on `your-api.onrender.com`

---

## Support & Resources

- Railway Status: https://status.railway.app
- Railway Docs: https://docs.railway.app
- FastAPI Deployment: https://fastapi.tiangolo.com/deployment/
- Vite Build Guide: https://vitejs.dev/guide/build.html
- Docker Reference: https://docs.docker.com/reference/

---

## Quick Reference Commands

```bash
# Local development
npm run dev & uvicorn api:app --reload

# Build for production
npm run build
docker build -t goldstone .
docker run -p 8000:8000 goldstone

# Test API locally
curl http://localhost:8000/health
curl http://localhost:8000/regime-types
curl http://localhost:8000/present-day

# Push changes to trigger Railway redeploy
git push origin main
```

---

## Deployment Status

- [ ] **Pre-deployment**: Code ready, files created
- [ ] **Railway**: Deployed and live
- [ ] **Testing**: All endpoints verified
- [ ] **Monitoring**: Set up error tracking
- [ ] **Sharing**: URL published

**Target Completion**: ~15 minutes from now ✨
