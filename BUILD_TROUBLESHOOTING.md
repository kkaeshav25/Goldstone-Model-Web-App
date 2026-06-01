# 🔧 Build Troubleshooting Guide

## Common Build Errors & Solutions

### ❌ Error: "npm: command not found"
**Cause**: Node.js not installed in container  
**Fix**: Already in Dockerfile. Verify locally:
```bash
npm --version  # Should be 20+
node --version # Should be 20.x
```

---

### ❌ Error: "ENOENT: no such file or directory, open 'package.json'"
**Cause**: package.json not being copied correctly  
**Solution**: 
```bash
# Verify package.json exists in root
ls package.json
git status  # Make sure it's tracked
git add package.json  # If missing
git push origin main
```

---

### ❌ Error: "Cannot find module 'vite' or 'react'"
**Cause**: node_modules not properly installed  
**Fix**: 
```bash
# Clean and reinstall
rm -r node_modules package-lock.json
npm install
```

---

### ❌ Error: "pip: command not found" or "requirements.txt not found"
**Cause**: requirements.txt missing or Python not installed  
**Fix**: Verify file exists:
```bash
ls requirements.txt
git add requirements.txt
git push origin main
```

---

### ❌ Error: Build takes > 5 minutes or times out
**Cause**: Network issues or large dependencies  
**Fix**: 
- Retry deployment (often transient network issue)
- Check platform logs for specific error
- Try different platform (Railway vs Render vs Vercel)

---

## 🧪 Test Locally First

Before deploying to cloud, verify the Docker build works locally:

```bash
cd "c:\Kaeshav\Python Codes\Goldstone Model"

# Build Docker image
docker build -t goldstone-test .

# Run container
docker run -p 8000:8000 goldstone-test

# Test in browser
open http://localhost:8000
# Should see the app!

# Test API
curl http://localhost:8000/health
# Should return: {"status":"ok","model":"Goldstone et al. 2010","version":"1.0.0"}
```

**If local build fails**, you've found the issue. Share the error output and I can help fix it.

---

## 📋 Step-by-Step Debugging

### Step 1: Verify All Files Exist
```bash
cd "c:\Kaeshav\Python Codes\Goldstone Model"

# Check these files exist:
ls package.json           # ✅ Frontend config
ls src/App.jsx           # ✅ Frontend code
ls Dockerfile            # ✅ Container config
ls requirements.txt      # ✅ Python dependencies
ls API.py               # ✅ Backend code
ls model.py             # ✅ Model logic
ls pipeline.py          # ✅ Data pipeline
ls present_day.py       # ✅ Present-day data
```

If any are missing:
```bash
git add .
git push origin main
```

---

### Step 2: Test Build Locally

```bash
# Build step by step to find exact error
docker build -t goldstone-test --progress=plain .
```

Watch output carefully. Build stops at first error.

---

### Step 3: Check Node & Python Versions

```bash
# Your versions must match Docker:
node --version   # Should be v20.x
npm --version    # Should be 20.x or 9.x+
python --version # Should be 3.11.x
```

---

### Step 4: Verify npm run build works

```bash
# This is what Docker will run
npm run build

# If fails, try:
npm install
npm run build
```

Expected output:
```
vite v8.0.12 building for production...
✓ 487 modules transformed...
dist/index.html    10.45 kB │ gzip:  4.12 kB
dist/index-xxx.js  125.67 kB │ gzip: 37.89 kB
✓ built in 15.23s
```

---

### Step 5: Verify requirements.txt

```bash
# This is what Docker will run
pip install -r requirements.txt

# If fails, the error message will tell you which package
# Common fixes:
pip install --upgrade setuptools
pip install -r requirements.txt --no-cache-dir
```

---

## 🐳 Alternative: Simpler Dockerfile for Testing

If the multi-stage build is causing issues, try this simpler version (`Dockerfile.simple`):

```dockerfile
FROM node:20-alpine

WORKDIR /app

# Install Python
RUN apk add --no-cache python3 py3-pip curl

# Copy files
COPY . .

# Install Node dependencies
RUN npm ci

# Build frontend
RUN npm run build

# Install Python dependencies
RUN pip install -r requirements.txt

# Expose and run
EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Test with:
```bash
docker build -f Dockerfile.simple -t goldstone-test .
docker run -p 8000:8000 goldstone-test
```

---

## 🚀 Platform-Specific Debugging

### Railway
1. Go to your project
2. Click **"Deployments"** tab
3. Click failed deployment
4. Scroll to **"Build Logs"**
5. Look for the line with red error

Common Railway fixes:
```bash
# Add railway.json to root:
{
  "build": {
    "builder": "dockerfile"
  }
}

# Ensure Dockerfile is named correctly
git add Dockerfile railway.json
git push origin main
```

### Vercel
1. Go to your project
2. Click **"Deployments"** tab
3. Click failed deployment
4. Expand **"Errors"** section

Common Vercel fixes:
- Vercel doesn't support Dockerfile by default
- Use Vercel + Render combo (Vercel for frontend, Render for backend)
- Or add build config to vercel.json

### Render
1. Go to your service
2. Click **"Logs"** tab
3. Look at live logs while build happens

Common Render fixes:
```bash
# Ensure requirements.txt properly formatted:
cat requirements.txt
# Each line should be: package==version
```

---

## ✅ Pre-Build Checklist

Before each deployment attempt:

```bash
# 1. All files committed and pushed
git status              # Should say "nothing to commit"
git log --oneline       # Should show recent commits

# 2. package.json valid
cat package.json        # Should be valid JSON (no syntax errors)

# 3. requirements.txt valid  
cat requirements.txt    # Each line: package==version

# 4. Local build works
npm run build           # Should succeed
ls dist/               # Should have files

# 5. Local test works
npm run dev &
uvicorn api:app --reload --port 8000
# Open http://localhost:5173 in browser - should work

# 6. Push final version
git add .
git commit -m "Ready for deployment"
git push origin main
```

---

## 🆘 Get Exact Error Message

To help you faster, share:

1. **Platform**: Railway / Vercel / Render / Docker
2. **Error message**: Paste the full error text (even partial helps!)
3. **Build logs**: Screenshot or copy from platform dashboard
4. **When it fails**: During npm install / Python install / Build / Runtime

---

## 🔄 Quick Retry Steps

If unsure, try these in order:

### Attempt 1: Clean rebuild
```bash
git push origin main
# Platform auto-rebuilds - might work second time
```

### Attempt 2: Full clean
```bash
rm -rf node_modules dist
npm install
npm run build
git add .
git commit -m "Rebuild"
git push origin main
```

### Attempt 3: Use different platform
- If Railway fails → Try Render
- If Docker fails → Try Vercel + Render combo
- All fail → Try local Docker test first

### Attempt 4: Simplify Dockerfile
```bash
# Use the simpler Dockerfile
docker build -f Dockerfile.simple -t test .
# If this works, swap the files
cp Dockerfile.simple Dockerfile
git push origin main
```

---

## 📞 What to Share When Asking for Help

To get faster help, provide:

```
Platform: [Railway/Vercel/Render/Docker]
Error Type: [npm install / Python install / Build / Runtime]
Error Message:
---
[Paste full error text here]
---

Steps I've tried:
- [Step 1]
- [Step 2]
```

---

## 🎯 If All Else Fails

Deploy backend and frontend separately:

```bash
# PLAN B: Vercel + Render

# 1. Deploy just React frontend to Vercel
#    (No Python needed, much simpler)
#    Set VITE_API_URL=https://your-render-api.onrender.com

# 2. Deploy just Python backend to Render
#    (No Node.js needed)
#    Start Command: uvicorn api:app --host 0.0.0.0 --port 8000
```

This is often **easier and more flexible** than single-container deployment!

---

## 💡 What Changed in This Fix

1. **Dockerfile** - Simplified file copying logic
2. **API.py** - Added static file serving for frontend
3. **Added Path import** - To safely check for dist folder

These changes should fix most build issues!

---

## Next Steps

1. **Test locally**:
   ```bash
   docker build -t goldstone-test .
   docker run -p 8000:8000 goldstone-test
   ```

2. **If that works** → Try cloud deployment again
3. **If that fails** → Share the error output and I'll help

Good luck! 🚀
